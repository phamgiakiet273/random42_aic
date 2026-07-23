"""MetaCLIP (ViT-H-14 / metaclip_altogether via open_clip) image/text feature extractor."""

from __future__ import annotations

import os
import threading

import numpy as np
import torch
from open_clip.factory import create_model_and_transforms
from open_clip.tokenizer import tokenize
from PIL import Image


class MetaclipModel:
    """Wraps MetaCLIP (ViT-H-14) for L2-normalized image/text embeddings on a dedicated GPU.

    Thread-safe: a lock serializes GPU forward passes so concurrent requests
    don't corrupt CUDA state or OOM.
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

        self.model, _, self.preprocess = create_model_and_transforms(
            "ViT-H-14", pretrained="metaclip_altogether", device=self.device
        )

    def get_image_features(self, image_data: Image.Image) -> np.ndarray:
        """Return the L2-normalized image embedding as a numpy array."""
        inputs = self.preprocess(image_data).unsqueeze(0).to(self.device)
        with self._lock:
            with (
                torch.no_grad(),
                torch.amp.autocast(self.device, enabled=(self.device != "cpu")),
            ):
                image_features = self.model.encode_image(inputs)
                image_features /= image_features.norm(dim=-1, keepdim=True)
        return image_features.cpu().detach().numpy()

    def get_text_features(self, text: str) -> np.ndarray:
        """Return the L2-normalized text embedding as a numpy array."""
        inputs = tokenize([text]).to(self.device)
        with self._lock:
            with (
                torch.no_grad(),
                torch.amp.autocast(self.device, enabled=(self.device != "cpu")),
            ):
                text_features = self.model.encode_text(inputs)
                text_features /= text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().detach().numpy()
