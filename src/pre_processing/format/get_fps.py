"""Collect per-video FPS from a directory of source videos into a JSON map."""

import argparse
import json
from collections import OrderedDict
from pathlib import Path

import cv2


def get_fps(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps


def collect_fps(data_path: str, output_file: str) -> None:
    """Walk `data_path` for .mp4 files and write {video_name: fps} to `output_file`."""
    total_dict = OrderedDict()
    for file in Path(data_path).glob("**/*.mp4"):
        if not file.is_file():  # Skip directories
            continue
        video_name = file.stem
        total_dict[video_name] = get_fps(str(file))
        with open(output_file, "w", encoding="utf-8-sig") as json_save:
            json.dump(total_dict, json_save, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect per-video FPS into a JSON map."
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory of source videos."
    )
    parser.add_argument(
        "--output-file", required=True, help="Path to write the JSON FPS map."
    )
    args = parser.parse_args()

    collect_fps(args.input_dir, args.output_file)
