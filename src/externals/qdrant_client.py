"""Thin wrapper around QdrantClient adding video/time filtering, temporal search, and dup/unique frame lookups."""

from __future__ import annotations

import bisect
import glob
import os
from collections import defaultdict
from typing import Any

import numpy as np
import ujson
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, HnswConfigDiff, PointStruct, VectorParams
from tqdm import tqdm

from src.modules.vector_search.fusion import merge_scores, merge_scores_reverse
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()


class QdrantSearchClient:
    """Search/ingest wrapper for a single Qdrant collection (siglip alpha/beta, metaclip, ...)."""

    def __init__(
        self,
        qdrant_url: str,
        qdrant_port: int,
        qdrant_grpc_port: int,
        collection_name: str | None = None,
        dataset_glob_path: str | None = None,
        dup_folder_path: str | None = None,
        unique_folder_path: str | None = None,
        timeout: int = 1800,
    ):
        settings = get_settings()
        dataset_root = dataset_glob_path or os.path.join(
            settings.dataset_path_team, "*"
        )
        dup_folder_path = dup_folder_path or os.path.join(
            settings.dataset_path_team, "utils", "duplicate1"
        )
        unique_folder_path = unique_folder_path or os.path.join(
            settings.dataset_path_team, "utils", "unique1"
        )

        self.timeout = timeout
        self.collection_name = collection_name

        self.client = QdrantClient(
            url=f"{qdrant_url}:{qdrant_port}",
            grpc_port=qdrant_grpc_port,
            prefer_grpc=True,
            timeout=self.timeout,
        )

        self.frame_names = self._prepare_data(dataset_root)
        self.img_dups = self._prepare_dup(dup_folder_path)
        self.img_uniques = self._prepare_unique(unique_folder_path)
        logger.info(
            f"Qdrant connection established on port {qdrant_port} (collection={collection_name})"
        )

    def add_database(
        self,
        collection_name: str,
        feature_size: int,
        keyframe_folder_path: str,
        features_path: list[str],
        split_name: str,
        s2t_path: list[str],
        fps_path: list[str],
        shot_path: list[str],
        unique_json_path: str,
        create_collection: bool = True,
    ) -> bool:
        """Create (or reuse) `collection_name` and bulk-ingest feature vectors + metadata into it."""
        self.collection_name = collection_name

        if create_collection:
            if self.client.collection_exists(collection_name=collection_name):
                logger.warning("Collection existed, deleting...")
                self.client.delete_collection(collection_name=self.collection_name)

            logger.info(f"Creating collection {collection_name}...")
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=feature_size,
                    distance=Distance.COSINE,
                    quantization_config=models.BinaryQuantization(
                        binary=models.BinaryQuantizationConfig(always_ram=True),
                    ),
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=4,
                    indexing_threshold=20000,
                ),
                on_disk_payload=True,
                shard_number=2,
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                    on_disk=False,
                ),
            )
            logger.info(f"Collection {collection_name} created")
        else:
            logger.info("Collection creation skipped")

        dict_fps: dict[str, Any] = {}
        for path in fps_path:
            with open(path, encoding="utf-8-sig") as json_file:
                dict_fps |= ujson.load(json_file)
        logger.info("FPS dict loaded")

        dict_s2t: dict[str, Any] = {}
        for path in s2t_path:
            with open(path, encoding="utf-8-sig") as json_file:
                dict_s2t |= ujson.load(json_file)
        logger.info("S2T dict loaded")

        with open(unique_json_path, encoding="utf-8-sig") as json_file:
            dict_unique = ujson.load(json_file)
        logger.info("Unique dict loaded")

        dict_shot: dict[str, Any] = {}
        for path in shot_path:
            with open(path, encoding="utf-8-sig") as json_file:
                dict_shot |= ujson.load(json_file)
        logger.info("Shot dict loaded")

        logger.info("Building payload...")

        struct_id = 0
        batch_size = 100_000  # flush threshold, adjust based on available RAM

        for idx_folder, folder_path in enumerate(features_path):
            insert_points = []

            for feat_npy in tqdm(sorted(os.listdir(folder_path))):
                video_name = feat_npy.split(".")[0]
                npy_path = os.path.join(folder_path, feat_npy)

                feats_arr = np.load(npy_path, mmap_mode="r")
                vectors = feats_arr.astype("float32").reshape(-1, feats_arr.shape[-1])

                # collection = dataset in qdrant; point = 1 vector + its metadata
                frame_path = os.path.join(
                    keyframe_folder_path,
                    str(idx_folder),
                    "frames",
                    split_name,
                    f"Keyframes_{video_name.split('_')[0]}",
                    "keyframes",
                    video_name,
                )
                frame_list = sorted(os.listdir(frame_path))
                frame_list = [f.replace(".avif", ".jpg") for f in frame_list]
                frame_nums = [
                    int(fn.replace(".jpg", "").replace(".avif", ""))
                    for fn in frame_list
                ]

                fps = dict_fps[video_name]
                s2t_map = dict_s2t.get(video_name + ".mp4", [])
                unique = dict_unique[video_name]
                shot = dict_shot[video_name]
                base_id = struct_id
                for idx, (vec, frm) in enumerate(zip(vectors, frame_nums)):
                    insert_points.append(
                        PointStruct(
                            id=base_id + idx,
                            vector=vec,
                            payload={
                                "idx_folder": idx_folder,
                                "video_name": video_name + ".mp4",
                                "frame_name": frm,
                                "fps": fps,
                                "s2t": s2t_map.get(frame_list[idx], "")
                                if isinstance(s2t_map, dict)
                                else "",
                                "is_unique": not unique[str(frm)],
                                "object": [],
                                "frame_class": shot[frame_list[idx]][0]
                                if shot != ""
                                else 2,
                                "related_start_frame": shot[frame_list[idx]][1]
                                if shot != ""
                                else 0,
                                "related_end_frame": shot[frame_list[idx]][2]
                                if shot != ""
                                else 50000,
                            },
                        )
                    )

                    if len(insert_points) >= batch_size:
                        phase = (struct_id // batch_size) + 1
                        logger.info(
                            f"Upserting data batch {phase} (size={len(insert_points)})"
                        )
                        self.client.upsert(
                            collection_name=self.collection_name,
                            wait=False,
                            points=insert_points,
                        )
                        insert_points = []

                struct_id += len(vectors)

            if insert_points:
                logger.info(f"Upserting final batch for folder {idx_folder + 1}")
                self.client.upsert(
                    collection_name=self.collection_name,
                    wait=False,
                    points=insert_points,
                )

            logger.info(
                f"Dataset insert completed {idx_folder + 1}/{len(features_path)}"
            )

        logger.info("Creating index...")
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="video_name",
            field_schema=models.TextIndexParams(
                tokenizer=models.TokenizerType.PREFIX,
                type="text",
                on_disk=True,
            ),
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="s2t",
            field_schema=models.TextIndexParams(
                type="text",
                tokenizer=models.TokenizerType.WORD,
                min_token_len=2,
                max_token_len=15,
                lowercase=True,
            ),
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="frame_class",
            field_schema=models.IntegerIndexParams(
                type=models.IntegerIndexType.INTEGER,
                on_disk=True,
                lookup=True,
                range=False,
            ),
        )
        logger.info("Payload index creation complete")

        return True

    def scroll_video(
        self,
        k: int,
        video_filter: str,
        time_in: str | None = None,
        time_out: str | None = None,
        s2t_filter: str | None = None,
        feature: str = "shot",
        frame_class_filter: list | None = None,
        skip_frames: list | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
    ):
        """Fetch points by id range (`feature="shot"`) or by precomputed dup/unique id lists."""
        if feature == "shot":
            id_list = sorted(self._get_frames(video_filter, time_in, time_out))
        elif feature == "dup":
            id_list = self.img_dups[video_filter][time_in.lstrip("0")]
        elif feature == "unique":
            id_list = self.img_uniques[video_filter][time_in.lstrip("0")]
        else:
            raise ValueError(f"Unknown feature: {feature}")

        scroll_result = self.client.retrieve(
            collection_name=self.collection_name,
            ids=id_list,
            with_payload=True,
            with_vectors=False,
        )
        return_result = self._format_search_results(
            scroll_result,
            use_query=False,
            return_s2t=return_s2t,
            return_object=return_object,
        )
        logger.info("Processed retrieval")
        return return_result

    def search(
        self,
        query: list[float],
        k: int = 100,
        video_filter: str = "",
        s2t_filter: str | None = None,
        frame_class_filter: list | None = None,
        skip_frames: list | None = None,
        sort_to_news: bool = True,
        return_s2t: bool = True,
        return_object: bool = True,
    ):
        """Single-vector similarity search with optional video/s2t/frame-class filters and news-style grouping."""
        frame_class_filter = frame_class_filter or []
        skip_frames = skip_frames or []

        query_filter = self._build_filter(
            video_filter, s2t_filter, frame_class_filter, skip_frames
        )

        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query,
            query_filter=query_filter,
            timeout=self.timeout,
            limit=int(k),
        ).points

        return_result = self._format_search_results(
            search_results, return_s2t=return_s2t, return_object=return_object
        )

        if sort_to_news:
            return_result = self._sort_to_news(return_result)

        return return_result

    def delete_database(self):
        self.client.delete_collection(collection_name=self.collection_name)

    def get_count(self) -> int:
        info = self.client.get_collection(collection_name=self.collection_name)
        return info.points_count or 0

    def search_temporal(
        self,
        query_list: list[list[float]],
        query_main: int = 0,
        k: int = 100,
        video_filter: list | str | None = None,
        s2t_filter: str | None = None,
        frame_class_filter: list | None = None,
        skip_frames: list | None = None,
        return_s2t: bool = True,
        return_object: bool = True,
    ):
        """Multi-event temporal search: search the main event, then chain neighboring events forward/backward."""
        frame_class_filter = frame_class_filter or []
        skip_frames = skip_frames or []
        video_filter = video_filter or []

        query_filter = self._build_filter(
            video_filter, s2t_filter, frame_class_filter, skip_frames
        )

        query_len = len(query_list)
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_list[query_main],
            query_filter=query_filter,
            timeout=self.timeout,
            limit=int(k) * query_len,
        ).points

        return_result = self._format_search_results(
            search_results, return_s2t=return_s2t, return_object=return_object
        )
        search_results = [[result] for result in return_result]
        previous_search_results = search_results

        logger.info(
            f"Processed scene {query_main + 1} for temporal with length: {len(previous_search_results)}"
        )

        for query_idx in range(query_len - 1, -1, -1):
            if query_idx >= query_main:
                continue

            id_condition = set()
            for result in search_results:
                video_name = result[0]["video_name"].replace(".mp4", "")
                frame = int(result[0]["keyframe_id"])
                id_condition |= set(
                    self._get_frames(video_name, frame - 1000, frame - 1)
                )

            filter_results = models.Filter(
                must=[models.HasIdCondition(has_id=list(id_condition))]
            )
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_list[query_idx],
                query_filter=filter_results,
                limit=int(k) * (query_len - query_main + query_idx),
                timeout=self.timeout,
            ).points

            return_result = self._format_search_results(
                search_results, return_s2t=return_s2t, return_object=return_object
            )
            search_results = merge_scores_reverse(
                return_result, previous_search_results
            )
            previous_search_results = search_results

            logger.info(
                f"Processed scene {query_idx + 1} for temporal with length: {len(previous_search_results)}"
            )

        for query_idx, query in enumerate(query_list):
            if query_idx <= query_main:
                continue

            id_condition = set()
            for result in search_results:
                video_name = result[-1]["video_name"].replace(".mp4", "")
                frame = int(result[-1]["keyframe_id"])
                id_condition |= set(
                    self._get_frames(video_name, frame + 1, frame + 1000)
                )

            filter_results = models.Filter(
                must=[models.HasIdCondition(has_id=list(id_condition))]
            )
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query,
                query_filter=filter_results,
                limit=int(k) * (len(query_list) + query_main - query_idx),
                timeout=self.timeout,
            ).points

            return_result = self._format_search_results(
                search_results, return_s2t=return_s2t, return_object=return_object
            )
            search_results = merge_scores(previous_search_results, return_result)
            previous_search_results = search_results

            logger.info(
                f"Processed scene {query_idx + 1} for temporal with length: {len(previous_search_results)}"
            )

        if query_main != 0 and query_main + 1 != query_len:
            search_results = sorted(
                search_results,
                key=lambda x: x[0]["score"]
                + x[-1]["score"]
                - float(x[query_main]["score"]),
                reverse=True,
            )
        return search_results

    def _build_filter(
        self, video_filter, s2t_filter, frame_class_filter, skip_frames
    ) -> models.Filter:
        must_field = []

        if video_filter not in ("", None, []):
            if isinstance(video_filter, str):
                video_filter = video_filter.split(",")
            should_field = [
                models.FieldCondition(
                    key="video_name", match=models.MatchText(text=frame_name)
                )
                for frame_name in video_filter
            ]
            must_field.append(models.Filter(should=should_field))

        if s2t_filter not in (None, ""):
            must_field.append(
                models.FieldCondition(
                    key="s2t", match=models.MatchText(text=s2t_filter)
                )
            )

        if frame_class_filter:
            must_field.append(
                models.FieldCondition(
                    key="frame_class", match=models.MatchAny(any=frame_class_filter)
                )
            )

        id_condition = set()
        for frame in skip_frames:
            id_condition |= set(
                self._get_frames(
                    frame["video_name"],
                    frame["related_start_frame"],
                    frame["related_end_frame"],
                )
            )

        must_not_field = [models.HasIdCondition(has_id=list(id_condition))]
        return models.Filter(must=must_field, must_not=must_not_field)

    @staticmethod
    def _sort_to_news(return_result: list[dict]) -> list[dict]:
        """Group consecutive keyframes of the same video into one "news" cluster scored by its best frame."""
        return_result = sorted(
            return_result, key=lambda x: (x["video_name"], x["keyframe_id"])
        )
        group = defaultdict(float)
        score_group = defaultdict(float)
        count = 1
        for i, item in enumerate(return_result):
            key = (item["video_name"], item["keyframe_id"])
            group[key] = key
            if i == 0:
                score_group[group[key]] = float(item["score"])
                continue
            if (
                item["video_name"] == return_result[i - 1]["video_name"]
                and int(item["key"]) - 1 == int(return_result[i - 1]["key"])
                and count <= 10
            ):
                group[key] = group[
                    (
                        return_result[i - 1]["video_name"],
                        return_result[i - 1]["keyframe_id"],
                    )
                ]
                score_group[group[key]] = max(
                    score_group[group[key]], float(item["score"])
                )
                count += 1
            else:
                score_group[group[key]] = float(item["score"])
                count = 1

        return sorted(
            return_result,
            key=lambda x: (
                score_group[group[(x["video_name"], x["keyframe_id"])]],
                -int(x["keyframe_id"]),
            ),
            reverse=True,
        )

    def _format_search_results(
        self,
        search_results,
        use_query: bool = True,
        return_s2t: bool = False,
        return_object: bool = False,
    ) -> list[dict]:
        return_result = []

        for item in search_results:
            payload = item.payload
            key = str(item.id)
            score = str(item.score) if use_query else "0.273"

            result = {
                "key": key,
                "idx_folder": str(payload["idx_folder"]),
                "video_name": str(payload["video_name"]),
                "keyframe_id": str(payload["frame_name"]).zfill(5),
                "fps": str(payload["fps"]),
                "score": score,
                "frame_class": str(payload["frame_class"]),
                "is_unique": payload["is_unique"],
                "related_start_frame": str(payload["related_start_frame"]),
                "related_end_frame": str(payload["related_end_frame"]),
            }
            if return_s2t:
                result["s2t"] = str(payload["s2t"])
            if return_object:
                result["object"] = ""
            return_result.append(result)

        return return_result

    def _prepare_data(self, folder_glob: str) -> dict[str, dict[int, int]]:
        frame_names: dict[str, dict[int, int]] = {}
        count = 0

        for batch_path in sorted(glob.glob(folder_glob)):
            split_glob = os.path.join(
                batch_path, "frames/low_res_autoshot", "Keyframes_*"
            )
            for split_path in sorted(glob.glob(split_glob)):
                video_glob = os.path.join(split_path, "keyframes", "*")
                for video_path in sorted(glob.glob(video_glob)):
                    frames = os.listdir(video_path)
                    name = {
                        int(frame[:5]): count + idx
                        for idx, frame in enumerate(sorted(frames))
                    }
                    frame_names[os.path.basename(video_path)] = name
                    count += len(name)
        return frame_names

    def _get_frames(self, video_name, first_frame, last_frame):
        frame_video = self.frame_names[video_name]

        list_keys = list(frame_video.keys())
        if first_frame is None:
            first_frame = list_keys[0]
        if last_frame is None:
            last_frame = list_keys[-1]

        first_frame, last_frame = int(first_frame), int(last_frame)
        if first_frame not in frame_video:
            id_frame = bisect.bisect_left(list_keys[:-1], first_frame)
            first_frame = list_keys[id_frame]
        if last_frame not in frame_video:
            id_frame = bisect.bisect_right(list_keys[:-1], last_frame)
            last_frame = list_keys[id_frame]

        list_values = list(frame_video.values())
        idx = list_values[0]
        first_idx = frame_video[first_frame]
        last_idx = frame_video[last_frame]
        return list_values[first_idx - idx : last_idx - idx + 1]

    def _prepare_dup(self, folder_path: str) -> dict[str, Any]:
        return self._load_json_folder(folder_path)

    def _prepare_unique(self, folder_path: str) -> dict[str, Any]:
        return self._load_json_folder(folder_path)

    @staticmethod
    def _load_json_folder(folder_path: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if not os.path.isdir(folder_path):
            logger.warning(f"Folder not found, skipping: {folder_path}")
            return result
        for json_name in os.listdir(folder_path):
            video_name, _ = os.path.splitext(json_name)
            with open(
                os.path.join(folder_path, json_name), encoding="utf-8-sig"
            ) as json_file:
                result[video_name] = ujson.load(json_file)
        return result
