"""Extract SigLIP2 image features for every keyframe under a keyframe root, one .npy per video."""

import argparse
import os

import numpy as np
from PIL import Image
from tqdm import tqdm

from src.modules.clip_models.siglip2 import Siglip2Model
from src.utils.settings import get_settings


def extract_features(keyframe_root: str, output_root: str, model: Siglip2Model) -> None:
    """Walk `keyframe_root/<video_name>/*.jpg`, embed each frame, save one array per video under `output_root`."""
    os.makedirs(output_root, exist_ok=True)
    for video_name in sorted(os.listdir(keyframe_root)):
        frame_dir = os.path.join(keyframe_root, video_name)
        if not os.path.isdir(frame_dir):
            continue
        video_feature = []
        for frame_name in tqdm(sorted(os.listdir(frame_dir)), desc=video_name):
            if frame_name.lower().endswith(".csv"):
                continue
            frame_path = os.path.join(frame_dir, frame_name)
            image = Image.open(frame_path).convert("RGB")
            video_feature.append(model.get_image_features(image))
        video_feature = np.array(video_feature)
        np.save(os.path.join(output_root, f"{video_name}.npy"), video_feature)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract SigLIP2 features for a keyframe directory tree."
    )
    parser.add_argument(
        "--keyframe-root",
        required=True,
        help="Directory containing one subfolder of frames per video.",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        help="Directory to write per-video .npy feature files into.",
    )
    parser.add_argument(
        "--cuda-visible-devices",
        default="0",
        help="CUDA_VISIBLE_DEVICES for the model.",
    )
    args = parser.parse_args()

    settings = get_settings()
    clip_model = Siglip2Model(
        cuda_visible_devices=args.cuda_visible_devices,
        cache_dir=settings.transformers_cache,
        hf_token=settings.huggingface_hub_token,
    )
    extract_features(args.keyframe_root, args.output_root, clip_model)
