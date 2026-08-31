"""SigLIP2 (google/siglip2-giant-opt-patch16-384) image/text feature extractor."""

from __future__ import annotations

import os
import threading

import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor
from transformers import __version__ as _TRANSFORMERS_VERSION

# `from_pretrained(torch_dtype=...)` was renamed to `dtype=` in transformers
# 4.56. requirements.txt pins 4.51.3 (what the Docker image installs) while the
# local conda env has 4.57.1, so passing either name unconditionally breaks one
# of the two environments.
def _dtype_kwarg() -> str:
    try:
        major, minor = (int(part) for part in _TRANSFORMERS_VERSION.split(".")[:2])
    except ValueError:
        return "torch_dtype"
    return "dtype" if (major, minor) >= (4, 56) else "torch_dtype"


_DTYPE_KWARG = _dtype_kwarg()

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
        # Non-deprecated spelling of TRANSFORMERS_CACHE. Note this lands *after*
        # `transformers` was imported at module top, so it cannot move the cache
        # on its own -- .env (loaded by src/main.py before this module) is what
        # actually governs it. Kept as a fallback for direct imports.
        # `cache_dir` is Settings.transformers_cache -- TRANSFORMERS_CACHE is the
        # deprecated alias for HF_HUB_CACHE, i.e. the *hub* directory itself, not
        # its parent. Pointing it one level too high makes huggingface_hub miss
        # an already-populated cache and silently re-download the 7.5GB weights.
        os.environ.setdefault("HF_HUB_CACHE", cache_dir)
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices

        self.device = "cpu" if use_cpu else "cuda"
        self._lock = threading.Lock()

        # No device_map here: the processor is CPU-side tokenising/resizing, so
        # it was never placed on a device, and accelerate (which device_map
        # needs) is not installed in this environment.
        self.processor = AutoProcessor.from_pretrained(
            MODEL_NAME, use_fast=True, token=hf_token
        )
        # fp32 on disk (~7.5GB) but the matmuls already run under autocast, so
        # fp32 weights only cost VRAM. fp16 halves them to ~3.7GB; Turing has no
        # bf16 tensor cores.
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = (
            AutoModel.from_pretrained(
                MODEL_NAME, token=hf_token, **{_DTYPE_KWARG: dtype}
            )
            .eval()
            .to(self.device)
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
