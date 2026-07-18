"""Demo: run YOLOE prompt-free object detection on a single image and save the annotated result."""

import argparse

import cv2
from ultralytics import YOLOE


def run_demo(weight_path: str, image_path: str, output_path: str) -> None:
    model = YOLOE(weight_path)

    # No prompts required.
    results = model.predict(image_path)

    # `plot()` renders the predictions on the image and returns a NumPy array.
    result_image = results[0].plot()
    cv2.imwrite(output_path, result_image)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run YOLOE prompt-free detection on a single image."
    )
    parser.add_argument(
        "--weight-path",
        default="data/weights/yoloe-11l-seg-pf.pt",
        help="YOLOE weight file.",
    )
    parser.add_argument(
        "--image-path",
        default="data/examples/animal_pf_test_2.jpg",
        help="Input image.",
    )
    parser.add_argument(
        "--output-path",
        default="data/examples/prediction_output.jpg",
        help="Annotated output image path.",
    )
    args = parser.parse_args()

    run_demo(args.weight_path, args.image_path, args.output_path)
