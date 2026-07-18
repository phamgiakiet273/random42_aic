"""Extract a title from a sequence of video keyframes using Qwen2.5-VL."""

from concurrent.futures import ThreadPoolExecutor
from typing import List

import numpy as np
from PIL import Image

from src.pre_processing.vlm_extractor.llm_model.qwen25vl import Qwen25VL
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class TitleExtractor:
    """Extracts a title from video frames via a shared Qwen25VL instance."""

    def __init__(self):
        logger.info("[TitleExtractor] Initializing...")
        self.qwen_model = Qwen25VL()
        logger.info("[TitleExtractor] Ready.")

    def read_prompt(self, prompt_path: str) -> str:
        with open(prompt_path, "r", encoding="utf-8") as file:
            return file.read()

    def _load_frames_parallel(
        self, frame_paths: list, max_workers: int = 16
    ) -> np.ndarray:
        """Load image frames in parallel from full file paths."""

        def _load_single_frame(path: str):
            try:
                return np.array(Image.open(path).convert("RGB"))
            except Exception as e:
                logger.warning(f"Could not load frame: {path}. Error: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(_load_single_frame, frame_paths)
            loaded_frames = [frame for frame in results if frame is not None]

        return np.stack(loaded_frames) if loaded_frames else None

    def extract_from_paths(self, frame_paths: List[str]) -> str:
        """Load frames from paths and extract a title. Main entry point of this class."""
        if not frame_paths:
            return "Error: frame path list is empty."

        logger.info(f"[TitleExtractor] Loading {len(frame_paths)} frames...")
        loaded_frames = self._load_frames_parallel(frame_paths)
        if loaded_frames is None:
            return "Error: could not load any frame."

        user_prompt = self.read_prompt(get_settings().prompt_title_extractor_path)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "video", "video": loaded_frames},
                    {"type": "text", "text": user_prompt},
                ],
            }
        ]

        logger.info("[TitleExtractor] Sending request to Qwen25VL for inference...")
        title = self.qwen_model.infer(messages, max_new_tokens=120)

        logger.info(f"[TitleExtractor] Title received: {title}")
        return title
