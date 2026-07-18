"""Compress a keyframe directory tree of .jpg images into low-res .avif images."""

import argparse
from pathlib import Path

import pillow_avif  # noqa: F401  (registers the AVIF plugin with Pillow)
from PIL import Image
from tqdm import tqdm


def compress_image_folder(
    high_res_path: str, low_res_path: str, quality: int = 10
) -> None:
    """Recursively re-encode every .jpg under `high_res_path` as .avif under `low_res_path`."""
    images = list(Path(high_res_path).glob("**/*.jpg"))
    for image in tqdm(images, desc=f"Compressing {high_res_path}"):
        if not image.is_file():
            continue
        relative_path = image.relative_to(high_res_path)
        low_res_image = Path(low_res_path) / relative_path.with_suffix(".avif")
        low_res_image.parent.mkdir(parents=True, exist_ok=True)
        picture = Image.open(image)
        picture.save(str(low_res_image), "AVIF", optimize=True, quality=quality)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compress a keyframe folder into low-res AVIF images."
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory of high-res .jpg keyframes."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write low-res .avif images into.",
    )
    parser.add_argument("--quality", default=10, type=int, help="AVIF encode quality.")
    args = parser.parse_args()

    compress_image_folder(args.input_dir, args.output_dir, args.quality)
