"""Expert-fusion vector search service — SigLIP2 (Expert A) + jina-clip-v2 (Expert B)
+ learned gating MLP, served as a drop-in CLIP variant (same API as ClipSearchService).

Flow for a text query:
  1. Encode text with BOTH experts in parallel (asyncio.to_thread).
  2. Search BOTH Qdrant collections in parallel.
  3. Build confidence features, run the gating MLP -> per-query (w_A, w_B).
  4. Gating-fuse the two ranked lists (rrf_blend=0.0 by default).
  5. Fallback: if the jina expert fails (model / network / qdrant), return
     SigLIP2-alone results so the pipeline never dies on a hard dependency.
"""

from __future__ import annotations

import asyncio
import os
import time
from http import HTTPStatus

import numpy as np
import torch

from src.common.schemas.api import APIResponse
from src.externals.qdrant_client import QdrantSearchClient
from src.modules.fusion_model.gating import (
    conf_from_results,
    context_rule_wb,
    extract_query_features,
    gating_fuse,
    load_gating,
    make_conf_features,
)
from src.utils.logger import get_logger
from src.utils.metadata import get_frame_path, get_video_path
from src.utils.settings import get_settings

logger = get_logger()


class FusionModelSearchService:
    """Text search over two expert collections with learned gating fusion."""

    def __init__(
        self,
        siglip_model,
        jina_model,
        qdrant_a: QdrantSearchClient,
        qdrant_b: QdrantSearchClient,
        gating_ckpt: str = "data/weights/gating_mlp_v3.pt",
        gating_mode: str = "context",
        rrf_blend: float = 0.0,
        top_k: int = 100,
    ) -> None:
        self.siglip = siglip_model
        self.jina = jina_model
        self.qdrant_a = qdrant_a
        self.qdrant_b = qdrant_b
        self.gating_mode = str(gating_mode or "context").lower()
        self.rrf_blend = float(rrf_blend)
        self.top_k = int(top_k)
        self._settings = get_settings()

        if os.path.exists(gating_ckpt):
            self.gating, self.scale = load_gating(gating_ckpt, device="cpu")
            logger.info(
                f"[FUSION] gating MLP loaded from {gating_ckpt} "
                f"(gating_mode={self.gating_mode}, rrf_blend={self.rrf_blend})"
            )
        else:
            self.gating, self.scale = None, None
            logger.warning(
                f"[FUSION] gating checkpoint not found at {gating_ckpt!r} — "
                "falling back to SigLIP2-alone."
            )

    async def ping(self) -> APIResponse:
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="Running (Healthy)",
            data={
                "experts": ["siglip2", "jina-clip-v2"],
                "gating": self.gating is not None,
                "gating_mode": self.gating_mode,
            },
        )

    # ---- fusion internals ----

    def _gating_weights(self, text: str, r_a: list[dict], r_b: list[dict]) -> tuple[float, float]:
        """Per-query (w_A, w_B).

        gating_mode="context" -> transparent overlap-aware rule (no MLP).
        gating_mode="mlp"     -> learned gating MLP (v3 is collapsed, kept for
                                 experiments). Returns (1, 0) if unavailable.
        """
        if self.gating_mode == "context":
            w_b = context_rule_wb(r_a, r_b)
            return 1.0 - w_b, w_b
        if self.gating is None:
            return 1.0, 0.0
        feat = extract_query_features(text)
        # make_conf_features already returns (1, n_conf) for a single query.
        conf = make_conf_features(conf_from_results(r_a, r_b)[np.newaxis, :], self.scale)
        with torch.no_grad():
            w = self.gating(
                torch.from_numpy(feat).unsqueeze(0),
                torch.from_numpy(conf.astype("float32")),
            )[0].numpy()
        return float(w[0]), float(w[1])

    async def debug_raw(self, text: str, k: int = 100) -> APIResponse:
        """Return raw per-expert ranked lists + gating weights (diagnostics only).

        Reuses the same encode/search path as text_search but exposes the
        unfused lists so downstream experiments can study expert behaviour
        (confidence features, oracle ceilings, hit@5 mechanics).
        """
        t0 = time.time()
        feat_a, feat_b = await asyncio.gather(
            asyncio.to_thread(self.siglip.get_text_features, text),
            asyncio.to_thread(self.jina.get_text_features, text),
        )
        feat_a = np.asarray(feat_a).reshape(-1)
        feat_b = np.asarray(feat_b).reshape(-1)
        r_a, r_b = await asyncio.gather(
            asyncio.to_thread(self.qdrant_a.search, query=feat_a, k=k,
                              sort_to_news=False),
            asyncio.to_thread(self.qdrant_b.search, query=feat_b, k=k,
                              sort_to_news=False),
        )
        w_a, w_b = self._gating_weights(text, r_a, r_b)
        conf_raw = conf_from_results(r_a, r_b)
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="debug_raw",
            data={
                "w_a": w_a,
                "w_b": w_b,
                "conf_raw": conf_raw.tolist(),
                "list_a": [
                    {
                        "video_name": x["video_name"],
                        "keyframe_id": x["keyframe_id"],
                        "score": float(x["score"]),
                    }
                    for x in r_a[:k]
                ],
                "list_b": [
                    {
                        "video_name": x["video_name"],
                        "keyframe_id": x["keyframe_id"],
                        "score": float(x["score"]),
                    }
                    for x in r_b[:k]
                ],
                "latency_ms": round((time.time() - t0) * 1000, 1),
            },
        )

    async def text_search(
        self,
        text: str,
        k: int = 10,
        video_filter: str | list[str] | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        logger.info(f"[FUSION] text_search called with text={text!r}, k={k}")
        if not text:
            raise ValueError("Missing text for search")

        # 1. encode both experts in parallel
        t0 = time.time()
        feat_a, feat_b = await asyncio.gather(
            asyncio.to_thread(self.siglip.get_text_features, text),
            asyncio.to_thread(self.jina.get_text_features, text),
        )
        # Siglip2Model returns (1, 1536); Qdrant wants a flat 1-D vector.
        feat_a = np.asarray(feat_a).reshape(-1)
        feat_b = np.asarray(feat_b).reshape(-1)
        logger.debug(f"[FUSION] encode done in {(time.time()-t0)*1000:.0f}ms "
                     f"(A={feat_a.shape} B={feat_b.shape})")

        # 2. search both collections in parallel
        t1 = time.time()
        r_a, r_b = await asyncio.gather(
            asyncio.to_thread(
                self.qdrant_a.search,
                query=feat_a,
                k=k,
                video_filter=video_filter or "",
                s2t_filter=s2t_filter,
                frame_class_filter=frame_class_filter,
                skip_frames=skip_frames or [],
                sort_to_news=False,
                return_s2t=return_s2t,
                return_object=return_object,
            ),
            asyncio.to_thread(
                self.qdrant_b.search,
                query=feat_b,
                k=k,
                video_filter=video_filter or "",
                s2t_filter=s2t_filter,
                frame_class_filter=frame_class_filter,
                skip_frames=skip_frames or [],
                sort_to_news=False,
                return_s2t=return_s2t,
                return_object=return_object,
            ),
        )
        logger.debug(f"[FUSION] search done in {(time.time()-t1)*1000:.0f}ms "
                     f"(A={len(r_a)} B={len(r_b)})")

        # 3. gating fusion with fallback to SigLIP2-alone on jina failure
        try:
            w_a, w_b = self._gating_weights(text, r_a, r_b)
            result = gating_fuse(r_a, r_b, w_a, w_b, rrf_blend=self.rrf_blend)
            if not result:  # both lists empty -> jina list is dead, use A alone
                result = r_a
            logger.info(f"[FUSION] wA={w_a:.2f} wB={w_b:.2f} fused={len(result)}")
        except Exception as exc:  # noqa: BLE001 — degrade gracefully to Expert A
            logger.exception(f"[FUSION] gating failed, falling back to SigLIP2 alone: {exc}")
            result = r_a

        if sort_to_news:
            result = QdrantSearchClient._sort_to_news(result)
        result = self._add_paths(result)
        return APIResponse(status=HTTPStatus.OK.value, message="Success", data=result)

    async def jina_text_search(
        self,
        text: str,
        k: int = 10,
        video_filter: str | None = None,
        s2t_filter: str | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
        frame_class_filter: list[int] | None = None,
        skip_frames: list[dict] | None = None,
        sort_to_news: bool = True,
    ) -> APIResponse:
        """jina-clip-v2 ALONE (Expert B) — no gating, no SigLIP2.

        Exposed so the UI can A/B-test the 3 options side by side:
        siglip_alpha / jina / fusion_model. Served on the same process as
        `text_search` (see /fusion_model/jina_text_search).
        """
        if not text:
            raise ValueError("Missing text for search")

        t0 = time.time()
        feat_b = np.asarray(
            await asyncio.to_thread(self.jina.get_text_features, text)
        ).reshape(-1)
        r_b = await asyncio.to_thread(
            self.qdrant_b.search,
            query=feat_b,
            k=k,
            video_filter=video_filter or "",
            s2t_filter=s2t_filter,
            frame_class_filter=frame_class_filter,
            skip_frames=skip_frames or [],
            sort_to_news=False,
            return_s2t=return_s2t,
            return_object=return_object,
        )
        logger.info(
            f"[JINA-ALONE] search done in {(time.time()-t0)*1000:.0f}ms "
            f"results={len(r_b)}"
        )
        if sort_to_news:
            r_b = QdrantSearchClient._sort_to_news(r_b)
        r_b = self._add_paths(r_b)
        return APIResponse(status=HTTPStatus.OK.value, message="Success", data=r_b)

    # ---- response post-processing (mirrors ClipSearchService) ----

    def _add_paths(self, records: list[dict]) -> list[dict]:
        settings = self._settings
        for idx, record in enumerate(records):
            record["index"] = idx
            batch = int(record["idx_folder"])
            record["video_path"] = os.path.relpath(
                get_video_path(batch=batch, video_name=record["video_name"]),
                settings.dataset_path_origin,
            )
            record["frame_path"] = os.path.relpath(
                get_frame_path(
                    batch=batch,
                    video_name=record["video_name"],
                    frame_name=record["keyframe_id"],
                ),
                settings.dataset_path_team,
            )
        return records
