"""Driver: run AutoShot shot detection over a video directory and cut keyframes."""

import argparse
import os

from src.pre_processing.shot_detection.detector import (
    ShotDetection,
    DEFAULT_CHECKPOINT_PATH,
)
from src.pre_processing.shot_detection.io_utils import (
    setup_video_path,
    SceneJsonLoader,
    CutKeyFrameLoader,
)


def split_video_into_frame(
    input_dir: str, output_folder: str, model: ShotDetection
) -> None:
    all_video_paths = setup_video_path(input_dir)

    prediction_scenes = model.run_model(video_path_dict=all_video_paths)

    scene_json_dir = os.path.join(output_folder, "SceneJson")
    os.makedirs(scene_json_dir, exist_ok=True)
    json_handling = SceneJsonLoader(prediction_scenes, scene_json_dir)
    json_handling.save_results()

    keyframe_dir = os.path.join(output_folder, "keyframes")
    keyframe_handler = CutKeyFrameLoader(scene_json_dir, keyframe_dir)
    keyframe_handler.extract_keyframes(all_video_paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run AutoShot shot detection over a video directory."
    )
    parser.add_argument(
        "--input-dir", required=True, help="Directory of source videos."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write SceneJson + keyframes into.",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=DEFAULT_CHECKPOINT_PATH,
        help="AutoShot checkpoint path.",
    )
    parser.add_argument(
        "--cuda-visible-devices",
        default=None,
        help="Optional CUDA_VISIBLE_DEVICES override.",
    )
    args = parser.parse_args()

    if args.cuda_visible_devices is not None:
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        os.environ["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices

    shot_model = ShotDetection("autoshot", checkpoint_path=args.checkpoint_path)
    split_video_into_frame(args.input_dir, args.output_dir, shot_model)
