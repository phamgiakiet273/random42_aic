"""YOLO-based classifier detecting whether a frame belongs to a news-intro segment."""

from ultralytics import YOLO


class NewsIntroClassifier:
    """Wraps a YOLO classification model for news-intro detection/training."""

    # Default is the fine-tuned checkpoint ("best.pt"); pass model_path="param/yolo11x-cls.pt"
    # (the pretrained base checkpoint) instead when starting a fresh training run.
    def __init__(self, model_path: str = "param/best.pt"):
        self.model = YOLO(model_path)

    def train(self, dataset_path: str):
        # Requires ~50GB GPU memory, ~5 hours.
        results = self.model.train(data=dataset_path, epochs=30, imgsz=1280, patience=5)
        return results
