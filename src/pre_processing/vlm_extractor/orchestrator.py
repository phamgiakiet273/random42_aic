"""Driver: title -> web search -> summary -> caption pipeline over a directory of per-shot frame folders."""

import argparse
import json
import os

import torch

from src.pre_processing.vlm_extractor.caption import EventLocalizer
from src.pre_processing.vlm_extractor.context_extractor import ContextExtractor
from src.pre_processing.vlm_extractor.llm_model.qwen3 import QwenChatModel
from src.pre_processing.vlm_extractor.title_extractor import TitleExtractor
from src.pre_processing.vlm_extractor.web_search import Search_web
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class MainWorkflow:
    """Coordinates the title / web-search / summary / caption steps for each shot."""

    def __init__(self):
        logger.info("Workflow initialized (no model loaded yet).")

    def execute_step_1_title(self, frame_paths: list) -> str:
        """Step 1: load model, extract title, release model."""
        logger.info("[Step 1] Loading TitleExtractor model...")
        title = None
        title_extractor = None
        try:
            title_extractor = TitleExtractor()
            title = title_extractor.extract_from_paths(frame_paths)
        finally:
            del title_extractor
            torch.cuda.empty_cache()
            logger.info("[Step 1] Released TitleExtractor memory.")
        return title

    def execute_step_2_web_search(self, title: str, shot_index: int) -> str:
        """Step 2: search the web based on the title."""
        logger.info("[Step 2] Searching the web...")
        web_search_pipeline = Search_web(query=title, shot_index=shot_index)
        content = web_search_pipeline.run()
        return content

    def execute_step_3_summary(self, content: str) -> str:
        """Step 3: load model, summarize content, release model."""
        if not content:
            logger.warning("[Step 3] Skipped: no web content.")
            return ""

        logger.info("[Step 3] Loading ContextExtractor model...")
        summary = ""
        qwen_model = None
        context_extractor = None
        try:
            qwen_model = QwenChatModel()
            context_extractor = ContextExtractor(model_object=qwen_model)
            summary = context_extractor.extract(content)
        finally:
            del qwen_model
            del context_extractor
            torch.cuda.empty_cache()
            logger.info("[Step 3] Released ContextExtractor memory.")
        return summary

    def execute_step_4_caption(self, frame_paths: list, context_text: str) -> dict:
        """Step 4: load model, caption the shot, release model. Always runs, even with empty context."""
        logger.info("[Step 4] Loading EventLocalizer (Caption) model...")
        if not context_text:
            logger.warning(
                "[Step 4] No context (summary), caption will be based on images only."
            )

        caption_result = None
        event_localizer = None
        try:
            event_localizer = EventLocalizer()
            shot_data = {"frames": frame_paths, "s2t": ""}

            result_dict = event_localizer.localize_events_in_shot(
                shot_data=shot_data, context_text=context_text
            )
            if result_dict:
                caption_result = result_dict.get("localized_events")

        except Exception as e:
            logger.error(f"[Step 4] Error while generating caption: {e}", exc_info=True)
        finally:
            del event_localizer
            torch.cuda.empty_cache()
            logger.info("[Step 4] Released EventLocalizer memory.")

        return caption_result


def run(input_root_dir: str, output_dir: str) -> None:
    workflow = MainWorkflow()

    if not os.path.isdir(input_root_dir):
        logger.error(f"Input folder '{input_root_dir}' does not exist.")
        return

    shot_dirs = sorted(
        d
        for d in os.listdir(input_root_dir)
        if os.path.isdir(os.path.join(input_root_dir, d))
    )
    if not shot_dirs:
        logger.warning(f"No shot folders found in '{input_root_dir}'.")

    for idx, shot_dir_name in enumerate(shot_dirs):
        shot_index = idx + 1
        shot_dir_path = os.path.join(input_root_dir, shot_dir_name)

        logger.info(
            f"===== PROCESSING SHOT {shot_index}/{len(shot_dirs)}: {shot_dir_name} ====="
        )

        frame_paths = [
            os.path.join(shot_dir_path, f)
            for f in sorted(os.listdir(shot_dir_path))
            if f.lower().endswith((".png", ".jpg", ".jpeg"))
        ]

        if not frame_paths:
            logger.warning(
                f"Shot folder {shot_dir_name} contains no image files. Skipping."
            )
            continue

        logger.info(f"Found {len(frame_paths)} frames for shot {shot_index}.")

        title = workflow.execute_step_1_title(frame_paths)
        if not title or "error" in title.lower() or "lỗi" in title.lower():
            logger.error(
                f"Stopping shot {shot_index}: could not extract title. Result: '{title}'"
            )
            continue
        logger.info(f"[Step 1] Extracted title: '{title}'")

        content = workflow.execute_step_2_web_search(title, shot_index)
        if not content:
            logger.warning(f"No web content found for shot {shot_index}.")
        else:
            logger.info("[Step 2] Web content found.")

        summary = workflow.execute_step_3_summary(content)
        if not summary:
            logger.warning(f"Could not summarize web content for shot {shot_index}.")
        else:
            logger.info("[Step 3] Content summarized successfully.")

        caption = workflow.execute_step_4_caption(
            frame_paths, context_text=summary or ""
        )

        if caption:
            logger.info("[Step 4] Caption generated successfully.")
        else:
            logger.warning(f"Could not generate caption for shot {shot_index}.")

        if caption:
            os.makedirs(output_dir, exist_ok=True)
            json_output_path = os.path.join(
                output_dir, f"caption_shot_{shot_index}.json"
            )
            try:
                with open(json_output_path, "w", encoding="utf-8") as f:
                    json.dump(caption, f, ensure_ascii=False, indent=4)
                logger.info(f"Saved JSON result to: {json_output_path}")
            except Exception as e:
                logger.error(f"Error saving JSON file: {e}")


if __name__ == "__main__":
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Run the title/web-search/summary/caption pipeline."
    )
    parser.add_argument(
        "--input-root-dir",
        default=os.path.join(settings.base_path, "vlm_extractor", "input"),
        help="Directory containing one subfolder of frames per shot.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.join(settings.base_path, "vlm_extractor", "final_results"),
        help="Directory to write per-shot caption JSON into.",
    )
    args = parser.parse_args()

    logger.info("================ PROGRAM START ================")
    run(args.input_root_dir, args.output_dir)
    logger.info("================ PROGRAM END ================")
