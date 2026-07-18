"""Localize and caption events within a video shot using Qwen2.5-VL, image + s2t + web context."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from src.pre_processing.vlm_extractor.llm_model.qwen25vl import Qwen25VL
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class EventLocalizer:
    """Uses Qwen2.5-VL to localize events within a video shot, given frames and text context."""

    def __init__(self):
        logger.info("[EventLocalizer] Initializing shared Qwen25VL...")
        self.qwen_model = Qwen25VL()
        self.prompt_template = self._load_prompt_template(
            get_settings().prompt_caption_path
        )
        logger.info("[EventLocalizer] Ready.")

    def _load_prompt_template(self, template_path: str) -> str:
        """Load the prompt content from a text file."""
        if not template_path:
            raise ValueError("prompt_caption_path is not set")
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found at '{template_path}'")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_images(self, frame_paths: List[str]) -> Optional[List[np.ndarray]]:
        """Load images from a list of paths."""
        images = []
        unique_paths = sorted(list(set(frame_paths)), key=frame_paths.index)
        for path_str in unique_paths:
            p = Path(path_str)
            if not p.exists():
                logger.warning(f"  [EventLocalizer] Skipping missing frame: {p}")
                continue
            try:
                with Image.open(p) as img:
                    images.append(np.array(img.convert("RGB")))
            except Exception as e:
                logger.warning(f"  [EventLocalizer] Could not open image {p}: {e}")
        return images if images else None

    def _build_prompt(self, s2t: str, context_text: str) -> str:
        """Build the detailed prompt for the model."""
        s2t_content = s2t if s2t else "No speech."
        context_content = (
            context_text
            if context_text
            else "No additional context, focus on the frames in the video"
        )
        return self.prompt_template.format(
            s2t=s2t_content, context_text=context_content
        )

    def _parse_json_from_model_output(self, output_text: str) -> Optional[List[Dict]]:
        """Extract and parse a JSON block from the raw model output."""
        json_pattern = re.search(
            r"```json\s*([\s\S]*?)\s*```|(\[[\s\S]*\]|{[\s\S]*})", output_text
        )
        if not json_pattern:
            logger.warning(
                "  [EventLocalizer] No JSON block found in the model output."
            )
            return None
        json_str = json_pattern.group(1) or json_pattern.group(2)
        try:
            json_str_cleaned = json_str.strip().replace("'", '"')
            return json.loads(json_str_cleaned)
        except json.JSONDecodeError:
            logger.error(
                f"  [EventLocalizer] Error parsing JSON from string: {json_str[:200]}..."
            )
            return None

    def localize_events_in_shot(
        self, shot_data: Dict[str, Any], context_text: str
    ) -> Optional[Dict[str, Any]]:
        """Process a single shot and call the shared Qwen25VL instance."""
        frames = shot_data.get("frames", [])
        if not frames:
            logger.warning("  [EventLocalizer] Shot has no frames list, skipping.")
            return None

        images = self._load_images(frames)
        if not images:
            logger.error("  [EventLocalizer] Could not load any frame, cannot process.")
            return None

        video_data = np.stack(images)
        s2t = shot_data.get("s2t", "")
        prompt = self._build_prompt(s2t=s2t, context_text=context_text)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "video", "video": video_data},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        logger.info(
            f"  [EventLocalizer] Sending request ({len(images)} frames) to shared Qwen25VL..."
        )
        raw_output_text = self.qwen_model.infer(messages)

        parsed_json = self._parse_json_from_model_output(raw_output_text)

        return {
            "localized_events": parsed_json,
            "model_raw_output": raw_output_text,
            "context_provided": context_text,
        }
