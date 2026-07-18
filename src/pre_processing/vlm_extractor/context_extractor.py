"""Summarize crawled web context into a single extracted-info text via Qwen3."""

import os

from src.pre_processing.vlm_extractor.llm_model.qwen3 import QwenChatModel
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class ContextExtractor:
    def __init__(self, model_object: QwenChatModel):
        """
        Args:
            model_object (QwenChatModel): A pre-loaded model instance.
        """
        settings = get_settings()
        self.base_dir = settings.base_output_craw_path
        self.qwen = model_object

        prompt_path = settings.summuray_prompt_path
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
            logger.info(f"Loaded prompt template from '{prompt_path}'")
        except FileNotFoundError:
            logger.error(f"Prompt file not found at: {prompt_path}")
            raise

    def _read_all_context(self) -> str:
        """Read all crawl output files under base_dir."""
        context_parts = []
        for root, _, files in os.walk(self.base_dir):
            for file in files:
                if file.startswith("output_") and file.endswith(".txt"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                            if content:
                                context_parts.append(content)
                    except Exception as e:
                        logger.warning(f"Could not read {file_path}: {e}")
        return "\n\n".join(context_parts)

    def extract(self, context_text: str) -> str:
        """Combine context, send to Qwen for extraction, and save the result."""
        context_text = self._read_all_context()
        if not context_text:
            logger.error("No context found in the output files.")
            return None

        prompt = self.prompt_template.format(context_text=context_text)

        logger.info("Sending extraction request to the model...")
        thinking, response = self.qwen.generate_response(prompt)
        logger.debug("Thinking content:\n" + thinking)

        if response:
            try:
                i = 1
                while True:
                    output_filename = f"sum_{i}.txt"
                    output_filepath = os.path.join(self.base_dir, output_filename)
                    if not os.path.exists(output_filepath):
                        break
                    i += 1

                with open(output_filepath, "w", encoding="utf-8") as f:
                    f.write(response)
                logger.info(f"Saved summary result to: '{output_filepath}'")

            except Exception as e:
                logger.error(f"Error saving summary file: {e}")

        return response
