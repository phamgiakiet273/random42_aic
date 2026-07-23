"""SigLIP2 (google/siglip2-giant-opt-patch16-384) image/text feature extractor."""

from __future__ import annotations

import os
import threading

import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

MODEL_NAME = "google/siglip2-giant-opt-patch16-384"


class Siglip2Model:
    """Wraps SigLIP2 for L2-normalized image/text embeddings on a dedicated GPU.

    Thread-safe: a lock serializes GPU forward passes so concurrent requests
    (e.g. 4 users querying simultaneously) don't corrupt CUDA state or OOM.
    """

    def __init__(
        self,
        cuda_visible_devices: str,
        cache_dir: str,
        hf_token: str | None = None,
        use_cpu: bool = False,
    ) -> None:
        os.environ["HF_HOME"] = cache_dir
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices

        self.device = "cpu" if use_cpu else "cuda"
        self._lock = threading.Lock()

        self.processor = AutoProcessor.from_pretrained(
            MODEL_NAME, use_fast=True, token=hf_token
        )
        self.model = (
            AutoModel.from_pretrained(MODEL_NAME, token=hf_token).eval().to(self.device)
        )

    def get_image_features(self, image_data: Image.Image) -> np.ndarray:
        """Return the L2-normalized image embedding as a numpy array."""
        inputs = self.processor(
            images=image_data,
            padding="max_length",
            return_tensors="pt",
            truncation=True,
        ).to(self.device)
        with self._lock:
            with (
                torch.no_grad(),
                torch.amp.autocast(self.device, enabled=(self.device != "cpu")),
            ):
                image_features = self.model.get_image_features(**inputs)
                image_features /= image_features.norm(dim=-1, keepdim=True)
        return image_features.cpu().detach().numpy()

    def get_text_features(self, text: str) -> np.ndarray:
        """Return the L2-normalized text embedding as a numpy array."""
        inputs = self.processor(
            text=text,
            padding="max_length",
            max_length=64,
            return_tensors="pt",
            truncation=True,
        ).to(self.device)
        with self._lock:
            with (
                torch.no_grad(),
                torch.amp.autocast(self.device, enabled=(self.device != "cpu")),
            ):
                text_features = self.model.get_text_features(**inputs)
                text_features /= text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().detach().numpy()
