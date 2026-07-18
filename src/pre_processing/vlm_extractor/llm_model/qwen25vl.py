"""Core loader/inference wrapper around Qwen2.5-VL, no business logic."""

from typing import Any, Dict, List

import torch
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class Qwen25VL:
    """Loads and runs inference with the Qwen2.5-VL model."""

    def __init__(self, model_path: str | None = None):
        if model_path is None:
            model_path = get_settings().model_qwen25_weight_folder
        if not model_path:
            raise ValueError("MODEL_QWEN25_WEIGHT_FOLDER is not set")

        self.model_path = model_path
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[Qwen25VL] Loading model '{self.model_path}' on {self.device}...")

        try:
            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.model_path, torch_dtype="auto", device_map="auto"
            )
            self.processor = AutoProcessor.from_pretrained(self.model_path)
            logger.info("[Qwen25VL] Model and processor ready.")
        except Exception as e:
            logger.critical(f"[Qwen25VL] Fatal error loading model: {e}", exc_info=True)
            raise

    def infer(self, messages: List[Dict[str, Any]], max_new_tokens: int = 1024) -> str:
        """Run inference on a chat-style message payload containing video/text content."""
        try:
            text_prompt = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            videos = [
                content_item["video"]
                for message in messages
                if message["role"] == "user"
                for content_item in message["content"]
                if content_item["type"] == "video"
            ]

            inputs = self.processor(
                text=[text_prompt], videos=videos, padding=True, return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                )

            output_ids = generated_ids[0][len(inputs["input_ids"][0]) :]
            response = self.processor.decode(
                output_ids, skip_special_tokens=True
            ).strip()
            return response

        except Exception as e:
            logger.error(f"[Qwen25VL] Inference failed: {e}", exc_info=True)
            return "Error: inference failed."
