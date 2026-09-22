"""Region-crop channel fusion for CCTV (N) content.

At preprocess we embedded object crops of the N frames into a sibling collection
(PUMPKING_SIGLIP_REGIONS); each region point stores `parent_id` = the id its
frame carries in the main collection, plus the crop's bbox/label/conf.

Live path: search the region collection with the SAME text/image vector, group
hits by parent frame, pull those parent frame records, and fuse them into the
normal frame results. A "red bus" query then matches the bus *crop* even when the
whole-frame embedding missed it. All offline-precomputed; this only adds one
vector search + one batch retrieve, so the live path stays in milliseconds.

Fully defensive: any problem (collection absent, query error) falls back to the
unmodified frame results, so search never breaks. Inert until the collection
exists, so it can ship before ingest.
"""
from __future__ import annotations

import os

from qdrant_client import models

from src.utils.logger import get_logger

logger = get_logger()

REGION_COLLECTION = "PUMPKING_SIGLIP_REGIONS"
MAIN_COLLECTION = "PUMPKING_SIGLIP_V2"

# tunables (env-overridable so we can A/B without a rebuild)
REGION_K = int(os.getenv("REGION_K", "400"))          # region hits to pull
REGION_WEIGHT = float(os.getenv("REGION_WEIGHT", "1.0"))  # region score weight in fusion
REGION_MAX_BOXES = int(os.getenv("REGION_MAX_BOXES", "6"))  # boxes kept per frame for UI
REGION_ENABLED = os.getenv("REGION_ENABLED", "1") != "0"

_state = {"ready": None}  # None = unknown, True/False cached


def _ready(client) -> bool:
    if not REGION_ENABLED:
        return False
    if _state["ready"] is None:
        try:
            _state["ready"] = client.collection_exists(REGION_COLLECTION)
            logger.info(f"region channel {'ENABLED' if _state['ready'] else 'absent'}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"region readiness check failed: {e}")
            _state["ready"] = False
    return _state["ready"]


def _video_only_filter(video_filter):
    """OR-match on video_name only (region points lack s2t/frame_class/is_unique)."""
    if video_filter in ("", None, []):
        return None
    if isinstance(video_filter, str):
        video_filter = video_filter.split(",")
    return models.Filter(should=[
        models.FieldCondition(key="video_name", match=models.MatchText(text=v))
        for v in video_filter
    ])


def _record_from_payload(pid, payload, score):
    s2t = payload.get("s2t") or []
    return {
        "key": str(pid),
        "idx_folder": int(payload["idx_folder"]),
        "video_name": str(payload["video_name"]),
        "keyframe_id": str(payload["frame_name"]).zfill(5),
        "fps": float(payload["fps"]),
        "score": float(score),
        "frame_class": int(payload["frame_class"]),
        "is_unique": bool(payload["is_unique"]),
        "related_start_frame": int(payload["related_start_frame"]),
        "related_end_frame": int(payload["related_end_frame"]),
        "s2t": list(s2t) if isinstance(s2t, (list, tuple)) else [s2t],
    }


def augment_with_regions(qdrant, feat, frame_result, video_filter, k):
    """Fuse region-crop hits into `frame_result`. Returns a (re-ranked) list.

    `qdrant` is the QdrantSearchClient wrapping the MAIN collection (we reuse its
    raw `.client`). No-op unless the main collection is PUMPKING_SIGLIP_V2 and the
    region collection exists.
    """
    try:
        if getattr(qdrant, "collection_name", None) != MAIN_COLLECTION:
            return frame_result
        client = qdrant.client
        if not _ready(client):
            return frame_result

        query = feat.tolist() if hasattr(feat, "tolist") else list(feat)
        hits = client.query_points(
            collection_name=REGION_COLLECTION,
            query=query,
            query_filter=_video_only_filter(video_filter),
            limit=REGION_K,
        ).points
        if not hits:
            return frame_result  # region added nothing -> leave frame results untouched

        # best region score + boxes per parent frame
        by_parent: dict[int, dict] = {}
        for h in hits:
            p = h.payload
            pid = int(p["parent_id"])
            slot = by_parent.setdefault(pid, {"score": 0.0, "boxes": []})
            if h.score > slot["score"]:
                slot["score"] = float(h.score)
            if len(slot["boxes"]) < REGION_MAX_BOXES:
                slot["boxes"].append({"bbox": p.get("bbox"), "object": p.get("cls"),
                                      "conf": p.get("conf"), "score": float(h.score)})

        parent_ids = list(by_parent)
        recs = client.retrieve(MAIN_COLLECTION, ids=parent_ids, with_payload=True)
        region_records = {}
        for r in recs:
            slot = by_parent[int(r.id)]
            rec = _record_from_payload(r.id, r.payload, REGION_WEIGHT * slot["score"])
            rec["regions"] = slot["boxes"]
            region_records[(rec["video_name"], rec["keyframe_id"])] = rec

        # merge: boost frames found by both, add region-only frames
        fused = {}
        for rec in frame_result:
            rec.setdefault("regions", [])
            fused[(rec["video_name"], rec["keyframe_id"])] = rec
        for key, rrec in region_records.items():
            if key in fused:
                base = fused[key]
                base["regions"] = rrec["regions"]
                if rrec["score"] > base["score"]:
                    base["score"] = rrec["score"]
            else:
                fused[key] = rrec

        out = sorted(fused.values(), key=lambda d: d["score"], reverse=True)
        return out[: int(k)] if k else out
    except Exception as e:  # noqa: BLE001
        logger.warning(f"region fusion skipped ({type(e).__name__}: {e})")
        return frame_result
