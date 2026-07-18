"""Shot boundary detection using the AutoShot model."""

from typing import Dict, Union

import numpy as np

from src.pre_processing.shot_detection.autoshot.model import AutoShot

DEFAULT_CHECKPOINT_PATH = (
    "src/pre_processing/shot_detection/autoshot/model_weight/ckpt_0_200_0.pth"
)


class ShotDetection:
    """A class for performing shot detection on videos using the AutoShot model."""

    def __init__(
        self, choice: str = "autoshot", checkpoint_path: str = DEFAULT_CHECKPOINT_PATH
    ):
        """Initialize the ShotDetection class.

        Args:
            choice (str): The model to use for shot detection.
            checkpoint_path (str): Path to the pretrained AutoShot checkpoint.
        """
        self.choice = choice.lower()
        if self.choice == "autoshot":
            self.model = AutoShot(checkpoint_path)
        else:
            raise ValueError("Invalid choice. Please choose 'autoshot'.")

    def run_model(self, video_path_dict: Dict[str, str]) -> Dict[str, np.ndarray]:
        """Run shot detection on a dictionary of video paths.

        Args:
            video_path_dict (Dict[str, str]): A dictionary mapping video names to their file paths.

        Returns:
            Dict[str, np.ndarray]: A dictionary mapping video names to their detected scene boundaries.
        """
        return self._run_autoshot(video_path_dict)

    def _run_autoshot(
        self, video_path_dict: Dict[str, Union[str, Dict]]
    ) -> Dict[str, Union[np.ndarray, Dict]]:
        """Run shot detection using the AutoShot model.

        Args:
            video_path_dict (Dict[str, Union[str, Dict]]): A nested dictionary mapping video names or folder names
                                                           to their file paths or further nested dictionaries.

        Returns:
            Dict[str, Union[np.ndarray, Dict]]: A nested dictionary mapping video names or folder names
                                                to their detected scene boundaries or further nested dictionaries.
        """
        res = self.model.process_videos(video_path_dict)
        return res
