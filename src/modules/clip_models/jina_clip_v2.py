"""Jina CLIP v2 (multilingual) text/image feature extractor.

Duck-types `Siglip2Model` (`get_text_features(str) -> np.ndarray`,
`get_image_features(PIL.Image) -> np.ndarray`) so it can be swapped into the
same `preprocessing_text`/`preprocessing_image` helpers. Also exposes
`get_text_features_batch` for fast batch encoding.
"""

from __future__ import annotations

import os

import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor


class JinaClipV2Model:
    """jinaai/jina-clip-v2 — XLM-RoBERTa text tower + EVA-02 image tower (1024-d).

    Multilingual (handles Vietnamese + English), which is why it is Expert B
    in the cross-lingual expert-fusion pipeline.
    """

    def __init__(
        self,
        cuda_visible_devices: str = "0",
        cache_dir: str | None = None,
        use_cpu: bool = False,
        model_name: str = "jinaai/jina-clip-v2",
    ) -> None:
        if cuda_visible_devices:
            os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
        self._device = (
            "cpu" if use_cpu else ("cuda:0" if torch.cuda.is_available() else "cpu")
        )

        self.processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True,
            cache_dir=cache_dir,
        )
        self.model = (
            AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
            .eval()
            .to(self._device)
        )

    def get_text_features(self, text: str) -> np.ndarray:
        """Single-text embedding, float32 (1024,)."""
        return self.get_text_features_batch([text])[0]

    def get_text_features_batch(self, texts: list[str]) -> np.ndarray:
        """Batch text embeddings, float32 (n, 1024), L2-normalized."""
        inp = self.processor(
            text=list(texts),
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self._device)
        with torch.no_grad():
            feat = self.model.get_text_features(**inp).float()
        feat = torch.nn.functional.normalize(feat, p=2, dim=-1)
        return feat.cpu().numpy().astype("float32")

    def get_image_features(self, image: Image.Image) -> np.ndarray:
        """Single-image embedding, float32 (1024,)."""
        inp = self.processor(images=[image], return_tensors="pt").to(self._device)
        with torch.no_grad():
            feat = self.model.get_image_features(**inp).float()
        feat = torch.nn.functional.normalize(feat, p=2, dim=-1)
        return feat.cpu().numpy().astype("float32")[0]
