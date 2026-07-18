"""Driver: run speech-to-text over a directory of videos and write per-video + combined transcript JSON."""

import argparse
import json
import pathlib
from collections import OrderedDict
from pathlib import Path

from src.pre_processing.speech_to_text.stt import SpeechToText


def folder_scan(data_path: str, save_path: str, s2t: SpeechToText) -> None:
    total_dict = {}
    for file in Path(data_path).glob("**/*.mp4"):
        if not file.is_file():  # Skip directories
            continue
        video_name = pathlib.PurePath(file).name
        video_save_path = save_path + str(video_name).replace(".mp4", "") + "/"
        video_save_path = Path(video_save_path)
        video_save_path.mkdir(parents=True, exist_ok=True)
        video_json_path = str(video_save_path) + ".json"
        video_dict = s2t.video_to_text(
            video_path=str(file), wav_path=str(video_save_path) + "/"
        )
        with open(video_json_path, "w", encoding="utf-8-sig") as outfile:
            json.dump(video_dict, outfile, indent=4, ensure_ascii=False)
        total_dict[str(video_name).replace(".mp4", "")] = video_dict
        total_dict = OrderedDict(total_dict)
        with open(
            save_path + "transcript_all.json", "w", encoding="utf-8-sig"
        ) as outfile:
            json.dump(total_dict, outfile, indent=4, ensure_ascii=False)
        print(file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run speech-to-text over a directory of videos."
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory of source videos."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write per-video and combined transcript JSON into.",
    )
    parser.add_argument(
        "--ngram-lm-path", required=True, help="Path to the KenLM n-gram .bin file."
    )
    args = parser.parse_args()

    speech_to_text = SpeechToText(ngram_lm_path=args.ngram_lm_path)
    folder_scan(args.input_dir, args.output_dir, speech_to_text)
