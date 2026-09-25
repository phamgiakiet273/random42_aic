"""Offline Vietnamese -> English translation: VinAI Translate (vinai-translate-vi2en-v2,
423M params, AGPL-3.0). Replaces the Google Cloud Translation API, which is no longer
free: no key, no quota, and no internet link in the path.

Loaded once, in a background thread, when the util service starts (keep UTIL_MAX_WORKERS=1:
every worker would load its own copy). fp16 on the GPU while the whole card stays under
TRANSLATE_GPU_MAX_TOTAL_MIB (user cap, 2026-09-25: 12 GB in use at idle, because SigLIP
peaks above its idle use); otherwise fp32 on the CPU.
Measured on the 4080 (2026-09-25): +1,160 MiB on the card (model 860 + CUDA context),
130 ms per query with 5 beams; ~700 ms on the CPU.
"""

from __future__ import annotations

import re
import subprocess
import threading
import time

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from src.modules.clip_models.siglip2 import DTYPE_KWARG
from src.utils.logger import get_logger

logger = get_logger()

MODEL_NAME = "vinai/vinai-translate-vi2en-v2"
GPU_NEED_MIB = 1300  # measured +1,160 MiB, with a margin

# Letters only Vietnamese uses. Text without any is taken as English already and passed
# through untouched: this model rewrites English input into different English.
_VIETNAMESE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
    re.IGNORECASE,
)


def has_vietnamese(text: str) -> bool:
    return bool(_VIETNAMESE.search(text or ""))


class TranslatorUnavailable(RuntimeError):
    pass


def _gpu_used_mib() -> float | None:
    """Memory in use on the whole card, read WITHOUT creating a CUDA context here
    (torch.cuda.mem_get_info would cost ~300 MiB even if we then stay on the CPU)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return float(out.split()[0])
    except Exception:  # noqa: BLE001 -- no nvidia-smi in this container: no GPU
        return None


class VinaiTranslator:
    def __init__(self, cache_dir: str | None, max_total_mib: int) -> None:
        self._cache_dir = cache_dir
        self._max_total_mib = max_total_mib
        self._ready = threading.Event()
        self._lock = threading.Lock()  # one generate at a time
        self._error: str | None = None
        self.device: str | None = None
        threading.Thread(target=self._load, name="vinai-translate-load", daemon=True).start()

    def _pick_device(self) -> tuple[str, str]:
        used = _gpu_used_mib() if torch.cuda.is_available() else None
        if used is None:
            return "cpu", "no GPU"
        if used + GPU_NEED_MIB > self._max_total_mib:
            return "cpu", f"GPU at {used:.0f} MiB; +{GPU_NEED_MIB} would pass the {self._max_total_mib} MiB cap"
        return "cuda", f"GPU at {used:.0f} MiB before loading"

    def _load(self) -> None:
        start = time.time()
        try:
            device, why = self._pick_device()
            kwargs = {"cache_dir": self._cache_dir, DTYPE_KWARG: torch.float16 if device == "cuda" else torch.float32}
            try:
                tok = AutoTokenizer.from_pretrained(MODEL_NAME, src_lang="vi_VN", cache_dir=self._cache_dir, local_files_only=True)
                model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, local_files_only=True, **kwargs)
            except OSError:  # not in the cache yet: download it once (~1.7 GB)
                logger.info(f"downloading {MODEL_NAME}")
                tok = AutoTokenizer.from_pretrained(MODEL_NAME, src_lang="vi_VN", cache_dir=self._cache_dir)
                model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, **kwargs)
            self._tok, self._model, self.device = tok, model.to(device).eval(), device
            self._en = tok.convert_tokens_to_ids("en_XX")
            self._generate(["Xin chào."])  # warm-up: the first call is ~3x slower
            logger.info(f"translation model ready on {device} ({why}) in {time.time() - start:.0f}s")
        except Exception as exc:  # noqa: BLE001
            self._error = f"{type(exc).__name__}: {exc}"
            logger.error(f"translation model failed to load: {self._error}")
        finally:
            self._ready.set()

    def _generate(self, texts: list[str]) -> list[str]:
        with self._lock, torch.inference_mode():
            start = time.perf_counter()
            batch = self._tok(texts, return_tensors="pt", padding=True).to(self.device)
            out = self._model.generate(
                **batch, decoder_start_token_id=self._en, num_beams=5, early_stopping=True, max_new_tokens=256,
            )
            result = [self._tok.decode(o, skip_special_tokens=True).strip() for o in out]
        logger.info(f"translated {len(texts)} sentence(s) in {(time.perf_counter() - start) * 1000:.0f} ms on {self.device}")
        return result

    def translate_many(self, texts: list[str], wait_s: float = 20) -> list[str]:
        """Vietnamese -> English, one output per input; blocking (call it in a thread)."""
        if not self._ready.wait(wait_s):
            raise TranslatorUnavailable("the translation model is still loading, try again in a few seconds")
        if self._error:
            raise TranslatorUnavailable(f"the translation model failed to load: {self._error}")
        return self._generate(texts)
