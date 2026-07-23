"""Build per-video frame-name -> index JSON files from a keyframe directory tree."""

import argparse
import pathlib
from collections import OrderedDict
from pathlib import Path

import ujson


def indexing(
    dataset_path: str, output_file: str, entire: bool = True, entire_folder: str = None
) -> None:
    visited = set()
    index_dict = {}
    for file in Path(dataset_path).glob("**/*.jpg"):
        if not file.is_file():  # Skip directories
            continue
        video_name = str(pathlib.PurePath(file).parent.name)
        folder_name = str(pathlib.PurePath(file).parent)
        if video_name in visited:
            continue
        visited.add(video_name)
        print(video_name)
        list_image = []

        for image in Path(folder_name).glob("**/*.jpg"):
            real_image_name = str(pathlib.PurePath(image).stem)
            list_image.append(real_image_name)
        list_image = sorted(list_image)
        for idx, item in enumerate(list_image):
            index_dict[(video_name, item)] = idx

        if entire is False:
            save_dict = OrderedDict()
            for item in index_dict:
                save_dict[int(item[1])] = index_dict[item]
            with open(entire_folder + "/" + video_name + ".json", "w") as outfile:
                ujson.dump(save_dict, outfile, indent=4)
            save_dict.clear()
            index_dict.clear()

    if entire is True:
        index_dict = OrderedDict(index_dict.items())
        with open(output_file, "w") as outfile:
            ujson.dump(index_dict, outfile, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build per-video frame-name -> index JSON files."
    )
    parser.add_argument(
        "--input-dir", required=True, help="Keyframe directory tree to index."
    )
    parser.add_argument(
        "--output-file", default=None, help="Output JSON path when --entire is set."
    )
    parser.add_argument(
        "--entire",
        action="store_true",
        help="Write a single combined index file instead of per-video files.",
    )
    parser.add_argument(
        "--entire-folder",
        default=None,
        help="Directory to write per-video index files into (when --entire is not set).",
    )
    args = parser.parse_args()

    indexing(
        args.input_dir,
        output_file=args.output_file,
        entire=args.entire,
        entire_folder=args.entire_folder,
    )
