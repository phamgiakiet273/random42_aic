"""Aggregate per-video object-detection JSON files into one file grouped by label, sorted by confidence."""

import argparse
import glob
import json
import os
from collections import defaultdict

from tqdm import tqdm


def aggregate_detections(
    root_dir: str, save_every: int = 100, output_file: str = "total_json.json"
) -> None:
    """Traverse all object_detection JSON files under root_dir, collect detections by label,
    and periodically save aggregated results sorted by confidence.

    Args:
        root_dir (str): Base dataset directory.
        save_every (int): Number of files to process before each intermediate save.
        output_file (str): Path for the final aggregated JSON output.
    """
    # Container for all detections, keyed by label
    detections = defaultdict(list)

    # Pattern matching all JSON files under */object_detection
    pattern = os.path.join(root_dir, "*", "object_detection", "*.json")
    json_files = glob.glob(pattern)

    # Iterate with progress bar
    for idx, json_path in enumerate(tqdm(json_files, desc="Processing JSON files")):
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: could not load {json_path}: {e}")
            continue

        # Derive video name (without extension) from filename
        video_name = os.path.splitext(os.path.basename(json_path))[0]

        # Collect detections for each frame
        for frame_id, objs in data.items():
            for obj in objs:
                label = obj.get("label")
                bbox = obj.get("bbox")
                score = obj.get("score")

                # Append detection entry
                detections[label].append(
                    {
                        "video": video_name,
                        "frame": frame_id,
                        "conf": score,
                        "bbox": bbox,
                    }
                )

        # Periodic save to avoid losing progress
        if (idx + 1) % save_every == 0:
            save_aggregated(detections, output_file)

    # Final save after all files processed
    save_aggregated(detections, output_file)


def save_aggregated(detections: dict, output_file: str) -> None:
    """Sort entries for each label by descending confidence and serialize to JSON."""
    aggregated = {}
    for label, entries in detections.items():
        # Sort by confidence descending
        sorted_entries = sorted(entries, key=lambda x: x["conf"], reverse=True)
        aggregated[label] = sorted_entries

    with open(output_file, "w") as f:
        json.dump(aggregated, f, indent=2)

    print(
        f"Saved aggregated results to {output_file} ({sum(len(v) for v in aggregated.values())} total detections)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Aggregate per-video object-detection JSON into one file."
    )
    parser.add_argument(
        "--root-dir",
        required=True,
        help="Base dataset directory containing */object_detection/*.json.",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Output JSON path. Defaults to <root-dir>/total_json.json.",
    )
    parser.add_argument(
        "--save-every",
        default=1000,
        type=int,
        help="Number of files between intermediate saves.",
    )
    args = parser.parse_args()

    output_file = args.output_file or os.path.join(args.root_dir, "total_json.json")
    aggregate_detections(
        args.root_dir, save_every=args.save_every, output_file=output_file
    )
