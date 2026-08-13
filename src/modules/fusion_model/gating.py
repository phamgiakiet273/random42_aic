"""Learned gating fusion — self-contained copy of the research module.

Combines Expert A (SigLIP2) and Expert B (jina-clip-v2) ranked lists with a
per-query weight w_B learned by a small MLP:
    final = (1 - blend) * (w_A * norm(score_A) + w_B * norm(score_B))
            + blend * norm(RRF)

The MLP maps 5 lexical query features + 6 confidence features -> w_B.
Confidence features are min-max scaled with a dataset-wide scale baked into
the checkpoint (identical scaling at train and inference time).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn

_EN_WORDS = set(
    "the a an is are was were be been being have has had do does did will would "
    "can could should may might must of in on at to for with by from as about into "
    "over under again further then once here there when where why how all any both "
    "each few more most other some such no nor not only own same so than too very "
    "just but and or if because while man woman people food city street house car "
    "boat river bird tiger goat cook chef show tv news interview garden forest tree "
    "red blue green white black yellow pink".split()
)

_VI_DIACRITICS = (
    "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
)
_VI_MARKS = (
    "ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳýỷỹỵ"
)


def extract_query_features(text: str) -> np.ndarray:
    """Lexical query features for the gating MLP: [n_tokens, chars/100,
    diacritic_ratio, en_ratio, has_vi] (float32, 5-d)."""
    tokens = text.split()
    n_tokens = len(tokens)
    n_chars = len(text)
    diacritics = sum(1 for c in text if c in _VI_DIACRITICS)
    diacritic_ratio = diacritics / max(n_chars, 1)
    en_words = sum(1 for t in tokens if t.lower().strip(".,!?") in _EN_WORDS)
    en_ratio = en_words / max(n_tokens, 1)
    has_vi = 1.0 if any(c in _VI_MARKS for c in text) else 0.0
    return np.array(
        [n_tokens, n_chars / 100.0, diacritic_ratio, en_ratio, has_vi],
        dtype="float32",
    )


class GatingMLP(nn.Module):
    """Small MLP: query features + expert confidences -> (w_A, w_B)."""

    def __init__(self, n_features: int = 5, n_conf: int = 2, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features + n_conf, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),  # logit for jina weight
        )

    def forward(self, x: torch.Tensor, conf: torch.Tensor) -> torch.Tensor:
        inp = torch.cat([x, conf], dim=-1)
        logit = self.net(inp).squeeze(-1)
        w_b = torch.sigmoid(logit)
        return torch.stack([1.0 - w_b, w_b], dim=-1)  # [n, 2]


def load_gating(ckpt_path: str, device: str = "cpu") -> tuple[GatingMLP, np.ndarray]:
    """Load the trained gating MLP + its confidence min-max scale."""
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model = GatingMLP(
        n_features=ckpt.get("n_features", 5),
        n_conf=ckpt.get("n_conf", 6),
        hidden=ckpt.get("hidden", 64),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval().to(device)
    scale = np.asarray(ckpt["scale"], dtype="float32")
    return model, scale


def conf_from_results(r_a: list[dict], r_b: list[dict]) -> np.ndarray:
    """Raw confidence row from two ranked result lists (service format):
    [top1_A, top2_A, top1_B, top2_B, agree_top1, jaccard]."""
    top1_a = float(r_a[0]["score"]) if r_a else 0.0
    top2_a = float(r_a[1]["score"]) if len(r_a) > 1 else 0.0
    top1_b = float(r_b[0]["score"]) if r_b else 0.0
    top2_b = float(r_b[1]["score"]) if len(r_b) > 1 else 0.0
    topv_a = r_a[0]["video_name"] if r_a else None
    topv_b = r_b[0]["video_name"] if r_b else None
    agree_top1 = 1.0 if (topv_a and topv_a == topv_b) else 0.0
    set_a = {x["video_name"] for x in r_a[:10]}
    set_b = {x["video_name"] for x in r_b[:10]}
    jaccard = len(set_a & set_b) / max(len(set_a | set_b), 1)
    return np.array(
        [top1_a, top2_a, top1_b, top2_b, agree_top1, jaccard], dtype="float32"
    )


def make_conf_features(conf_raw: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """[top1A, top2A, top1B, top2B, agree, jacc] ->
    [top1A, marginA, top1B, marginB, agree, jacc], min-max scaled."""
    agree = conf_raw[:, 4] if conf_raw.shape[1] > 4 else np.zeros(len(conf_raw))
    jaccard = conf_raw[:, 5] if conf_raw.shape[1] > 5 else np.zeros(len(conf_raw))
    feats = np.stack(
        [
            conf_raw[:, 0],
            conf_raw[:, 0] - conf_raw[:, 1],
            conf_raw[:, 2],
            conf_raw[:, 2] - conf_raw[:, 3],
            agree,
            jaccard,
        ],
        axis=1,
    )
    lo, hi = scale[:, 0], scale[:, 1]
    span = np.where(hi - lo < 1e-12, 1.0, hi - lo)
    return (feats - lo) / span


def _minmax_norm(scores: list[float]) -> np.ndarray:
    arr = np.asarray(scores, dtype="float64")
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-12:
        return np.ones_like(arr)
    return (arr - lo) / (hi - lo)


def context_rule_wb(
    r_a: list[dict],
    r_b: list[dict],
    wb_jina: float = 0.55,
    wb_boosted: float = 0.30,
    wb_agree: float = 0.50,
) -> float:
    """Overlap-aware per-query w_B (no MLP, transparent).

    Classifies the two expert lists by how their top-1s relate to each other:

      * JINA    — jina#1 is absent from siglip's top-k        -> trust jina
                 (jina found a frame siglip never retrieved).   w_B = wb_jina
      * BOOSTED — jina#1 IS in siglip's top-k but != siglip#1  -> trust siglip#1
                 (both experts agree on the candidate pool,    w_B = wb_boosted
                  so siglip's own top deserves more weight)
      * SIGLIP  — both top-1s are the same frame (consensus)   -> balanced
                                                                 w_B = wb_agree

    Empirical calibration on the 200-query live eval (see
    research/expert_fusion/FINAL_RESULTS.md, section on context-rule):
    wb_jina=0.55 / wb_boosted=0.30 / wb_agree=0.50 gives hit@1 10.0% vs 9.0%
    for the collapsed MLP, with identical hit@5.
    """
    if not r_a or not r_b:
        return wb_agree
    a1 = (r_a[0]["video_name"], r_a[0]["keyframe_id"])
    b1 = (r_b[0]["video_name"], r_b[0]["keyframe_id"])
    if a1 == b1:
        return wb_agree
    a_keys = {(x["video_name"], x["keyframe_id"]) for x in r_a}
    if b1 in a_keys:
        return wb_boosted
    return wb_jina


def gating_fuse(
    r_a: list[dict],
    r_b: list[dict],
    w_a: float,
    w_b: float,
    rrf_blend: float = 0.0,
    rrf_k: int = 60,
) -> list[dict]:
    """Hybrid fusion over service-format result dicts.

    final = blend * norm(RRF) + (1 - blend) * (w_A * norm(score_A) + w_B * norm(score_B))
    rrf_blend=0.0 -> pure gating score fusion (best hit@1); 1.0 -> pure RRF.
    Mutates `score` of the returned records in place; order reflects fusion.
    """
    acc: dict[tuple, float] = defaultdict(float)
    meta: dict[tuple, dict] = {}

    sa = _minmax_norm([float(x["score"]) for x in r_a])
    sb = _minmax_norm([float(x["score"]) for x in r_b])
    for x, s in zip(r_a, sa):
        key = (x["video_name"], x["keyframe_id"])
        acc[key] += w_a * float(s)
        meta.setdefault(key, x)
    for x, s in zip(r_b, sb):
        key = (x["video_name"], x["keyframe_id"])
        acc[key] += w_b * float(s)
        meta.setdefault(key, x)

    gating_scores = {k: acc[k] for k in acc}

    rrf_scores: dict[tuple, float] = defaultdict(float)
    for i, x in enumerate(r_a):
        rrf_scores[(x["video_name"], x["keyframe_id"])] += 1.0 / (rrf_k + i + 1)
    for i, x in enumerate(r_b):
        rrf_scores[(x["video_name"], x["keyframe_id"])] += 1.0 / (rrf_k + i + 1)

    rrf_arr = np.array([rrf_scores[k] for k in acc], dtype="float64")
    rrf_norm = _minmax_norm(rrf_arr.tolist())

    out = [meta[k] for k in acc]
    for x, gs, rs in zip(out, gating_scores.values(), rrf_norm):
        x["score"] = float(rrf_blend * rs + (1.0 - rrf_blend) * gs)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out
