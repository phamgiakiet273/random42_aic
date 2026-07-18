"""Align per-video speech transcripts to keyframes using PhoBERT word segmentation + FPS timing."""

import argparse
import json
import os
import re
from collections import OrderedDict
from pathlib import Path

import py_vncorenlp
import torch
from transformers import AutoModel, AutoTokenizer


def cosine(a, b):
    from numpy import dot
    from numpy.linalg import norm

    return dot(a, b) / (norm(a) * norm(b))


class PhoBERT:
    def __init__(self, vncorenlp_save_dir: str) -> None:
        """
        Args:
            vncorenlp_save_dir (str): Directory holding (or to download) the VnCoreNLP word-segmentation model.
        """
        self.device = "cuda"
        self.phobert = AutoModel.from_pretrained("vinai/phobert-base-v2")
        self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base-v2")
        self.rdrsegmenter = py_vncorenlp.VnCoreNLP(
            annotators=["wseg"],
            save_dir=vncorenlp_save_dir,
        )

    def remove_special_character(self, text: str):
        chars_to_ignore = "[^\ a-zA-Z_àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳỵỷỹýÀÁÃẠẢĂẮẰẲẴẶÂẤẦẨẪẬÈÉẸẺẼÊỀẾỂỄỆĐÌÍĨỈỊÒÓÕỌỎÔỐỒỔỖỘƠỚỜỞỠỢÙÚŨỤỦƯỨỪỬỮỰỲỴỶỸÝ]"
        text = re.sub(chars_to_ignore, "", text.lower())
        return text

    def segmenter(self, text: str):
        if len(text) == 0:
            return text
        text = self.remove_special_character(text)
        text = self.rdrsegmenter.word_segment(text)
        text = text[0].split(" ")
        text = [x.replace("_", " ") for x in text]
        return text

    def extract(self, text: str):
        input_ids = torch.tensor([self.tokenizer.encode(text)])
        input_ids.to(self.device)
        with torch.no_grad():
            features = self.phobert(input_ids)[0].numpy().squeeze(0)
        return features


def matching(
    speech_json: str,
    keyframe_jpg: str,
    save_path: str,
    fps_dict_all: dict,
    phobert: PhoBERT,
) -> None:
    total_dict = {}
    for video_json in Path(speech_json).glob("*.json"):
        video_name = str(os.path.basename(video_json)).replace(".json", "")
        if not video_name.startswith("L"):
            continue
        keyframes_folder = (
            keyframe_jpg + "Keyframes_" + video_name[:3] + "/keyframes/" + video_name
        )
        with open(str(video_json), encoding="utf-8-sig") as f:
            data = json.load(f)

        transcript_dict = {}
        for frame_transcript in data.items():
            start_frame = ""
            end_frame = ""
            for i in range(0, len(frame_transcript[0])):
                if frame_transcript[0][i] == "_":
                    end_frame = frame_transcript[0][i + 1 :]
                    break
                start_frame += frame_transcript[0][i]
            start_frame = int(start_frame)
            end_frame = int(end_frame)
            transcript_dict[(start_frame, end_frame)] = phobert.segmenter(
                frame_transcript[1]
            )

        video_dict = {}

        for file in Path(keyframes_folder).glob("**/*.jpg"):
            if not file.is_file():  # Skip directories
                continue
            pic_name = str(os.path.basename(str(file)))
            pic_frame = int(os.path.basename(str(file).replace(".jpg", "")))
            second = float(pic_frame) / float(fps_dict_all[video_name])
            for x in transcript_dict.keys():
                if second >= x[0] and second <= x[1]:
                    video_dict[pic_name] = transcript_dict[x]
                    break
                if x[0] > second:
                    break

            if pic_name not in video_dict:
                for x in transcript_dict.keys():
                    transcript = transcript_dict[x]
                    if x[0] > second:
                        break
                video_dict[pic_name] = transcript

        video_dict = OrderedDict(sorted(video_dict.items()))
        total_dict[str(video_name + ".mp4")] = video_dict
        total_dict = OrderedDict(sorted(total_dict.items()))
        with open(
            save_path + "transcript_all_autoshot_segmented.json",
            "w",
            encoding="utf-8-sig",
        ) as outfile:
            json.dump(total_dict, outfile, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Align speech transcripts to keyframes via FPS timing."
    )
    parser.add_argument(
        "--speech-json-dir",
        required=True,
        help="Directory of per-video speech transcript JSON.",
    )
    parser.add_argument(
        "--keyframe-dir", required=True, help="Directory of extracted keyframes."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write the segmented transcript JSON into.",
    )
    parser.add_argument(
        "--fps-json",
        action="append",
        required=True,
        help="Path to a video_fps_*.json file (repeatable).",
    )
    parser.add_argument(
        "--vncorenlp-save-dir",
        required=True,
        help="Directory holding the VnCoreNLP model.",
    )
    args = parser.parse_args()

    fps_dict_all = {}
    for fps_path in args.fps_json:
        with open(fps_path, "r", encoding="utf-8-sig") as infile:
            fps_dict_all.update(json.load(infile))

    phobert_model = PhoBERT(vncorenlp_save_dir=args.vncorenlp_save_dir)
    matching(
        args.speech_json_dir,
        args.keyframe_dir,
        args.output_dir,
        fps_dict_all,
        phobert_model,
    )
