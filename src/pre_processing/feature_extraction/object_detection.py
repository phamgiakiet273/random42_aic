"""Run Detic (via HuggingFace deformable-DETR) object detection over a keyframe directory tree."""

import argparse
import json
import os
from pathlib import Path

import torch
from PIL import Image
from tqdm import tqdm
from transformers import AutoImageProcessor, DeformableDetrForObjectDetection


def setup_environment(gpu_id: str = "0", cache_dir: str = None):
    """Configure GPU visibility and Transformers cache directory."""
    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_id
    if cache_dir:
        os.environ["TRANSFORMERS_CACHE"] = cache_dir


class DeticHuggingFace:
    def __init__(
        self,
        model_name: str = "facebook/deformable-detr-detic",
        use_fast: bool = True,
        device: str = "cuda",
    ):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.processor = AutoImageProcessor.from_pretrained(
            model_name, use_fast=use_fast
        )
        self.model = DeformableDetrForObjectDetection.from_pretrained(model_name)
        self.model.to(self.device)

    def predict(self, image_path: str, threshold: float = 0.5):
        """Run object detection on an image and return a list of {bbox, label, score} detections."""
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)

        target_sizes = torch.tensor([image.size[::-1]])  # (height, width)
        results = self.processor.post_process_object_detection(
            outputs, target_sizes=target_sizes, threshold=threshold
        )[0]

        detections = []
        for score, label, box in zip(
            results["scores"], results["labels"], results["boxes"]
        ):
            detections.append(
                {
                    "bbox": [round(x, 2) for x in box.tolist()],
                    "label": self.model.config.id2label[label.item()],
                    "score": round(score.item(), 3),
                }
            )
        return detections


def batch_detect(
    input_dir: Path,
    output_dir: Path,
    threshold: float = 0.5,
    gpu_id: str = "0",
    cache_dir: str = None,
):
    """Walk input_dir, detect objects in each .jpg frame, and save results grouped by video name into JSON files."""
    setup_environment(gpu_id, cache_dir)
    detic = DeticHuggingFace()

    # Find all JPEG images recursively
    image_paths = list(input_dir.rglob("*.jpg"))
    if not image_paths:
        print(f"No .jpg images found in {input_dir}")
        return

    # Accumulate detections: video_name -> { frame_name: [detections] }
    all_results = {}
    # Progress bar over images
    for img_path in tqdm(image_paths, desc="Processing frames", unit="frame"):
        video_name = img_path.parent.name  # e.g., L01_V001
        frame_name = img_path.stem  # e.g., 00000

        detections = detic.predict(str(img_path), threshold=threshold)

        if video_name not in all_results:
            all_results[video_name] = {}
        all_results[video_name][frame_name] = detections

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON per video with progress bar
    for video_name, frames in tqdm(
        all_results.items(), desc="Writing JSON", unit="video"
    ):
        out_file = output_dir / f"{video_name}.json"
        with open(out_file, "w") as f:
            json.dump(frames, f, indent=2)
        print(f"Saved detections for '{video_name}' -> {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Detic object detection over a keyframe directory tree."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory of keyframes (searched recursively for .jpg).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write per-video detection JSON into.",
    )
    parser.add_argument(
        "--threshold", default=0.3, type=float, help="Detection confidence threshold."
    )
    parser.add_argument("--gpu-id", default="0", help="CUDA_VISIBLE_DEVICES value.")
    parser.add_argument(
        "--cache-dir", default=None, help="Optional Transformers cache directory."
    )
    args = parser.parse_args()

    batch_detect(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        threshold=args.threshold,
        gpu_id=args.gpu_id,
        cache_dir=args.cache_dir,
    )
