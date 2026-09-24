"""Score-fusion helpers for combining/merging ranked results from two vector searches."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict


# The temporal merges used to compare every new hit with every chain: 5-6k x 5-6k
# = ~30M Python comparisons at top-K 1000 (43% of a 6-event search). Chains are
# now indexed by video and keyframe, and each hit only looks at its 1000-frame
# window -- same result: the highest score > 0, the earliest chain on a tie.
def _index_chains(chains, end):
    """{video: (keyframes, rows)} for each chain's `end` record (0 = first, -1 = last),
    rows = (keyframe, chain index, score) sorted by keyframe."""
    by_video = defaultdict(list)
    for idx, chain in enumerate(chains):
        rec = chain[end]
        by_video[rec["video_name"]].append((int(rec["keyframe_id"]), idx, float(rec["score"])))
    index = {}
    for video, rows in by_video.items():
        rows.sort()
        index[video] = ([r[0] for r in rows], rows)
    return index


def _best_in_window(index, video, lo, hi):
    """(score, chain index) of the best chain whose keyframe is in [lo, hi]: only
    scores > 0 count and the lowest chain index wins a tie -- exactly what the old
    scan in chain order did. (0.0, None) when there is none."""
    entry = index.get(video)
    if entry is None:
        return 0.0, None
    keys, rows = entry
    best, best_idx = 0.0, None
    for _, idx, score in rows[bisect_left(keys, lo):bisect_right(keys, hi)]:
        if score > best or (best_idx is not None and score == best and idx < best_idx):
            best, best_idx = score, idx
    return best, best_idx


def merge_scores(list_res_A, list_res_B):
    """Fold matching list_res_A scores (by video_name + nearby keyframe_id) into list_res_B and resort."""
    idx_results = {}
    chains_by_last = _index_chains(list_res_A, -1)
    for idx_B, record_B in enumerate(list_res_B):
        video_name = record_B["video_name"]
        keyframe_id = record_B["keyframe_id"]
        kf = int(keyframe_id)
        # a chain whose LAST frame is 1..1000 frames before this hit
        max_temp_score, idx_A = _best_in_window(chains_by_last, video_name, kf - 1000, kf - 1)
        if idx_A is not None:
            idx_results[(video_name, keyframe_id)] = idx_A

        list_res_B[idx_B]["score"] = float(list_res_B[idx_B]["score"]) + max_temp_score

    # resort by score
    sorted_list = sorted(list_res_B, key=lambda x: x["score"], reverse=True)
    results = []
    for record_B in sorted_list:
        video_name = record_B["video_name"]
        keyframe_id = record_B["keyframe_id"]
        if (video_name, keyframe_id) not in idx_results:
            continue
        idx_A = idx_results[(video_name, keyframe_id)]
        record_A = list_res_A[idx_A]
        results.append(record_A + [record_B])

    max_dict = {}
    for item in results:
        key = str(item[-2]["video_name"]) + "_" + str(item[-2]["keyframe_id"])
        if key not in max_dict or item[-1]["score"] > max_dict[key][-1]["score"]:
            max_dict[key] = item
    results = list(max_dict.values())

    return results


def merge_scores_reverse(list_res_A, list_res_B):
    """Same as merge_scores but folds list_res_B scores into list_res_A instead."""
    idx_results = {}
    chains_by_first = _index_chains(list_res_B, 0)
    for idx_A, record_A in enumerate(list_res_A):
        video_name = record_A["video_name"]
        keyframe_id = record_A["keyframe_id"]
        kf = int(keyframe_id)
        # a chain whose FIRST frame is 1..1000 frames after this hit
        max_temp_score, idx_B = _best_in_window(chains_by_first, video_name, kf + 1, kf + 1000)
        if idx_B is not None:
            idx_results[(video_name, keyframe_id)] = idx_B

        list_res_A[idx_A]["score"] = float(record_A["score"]) + max_temp_score

    # resort by score
    sorted_list = sorted(list_res_A, key=lambda x: x["score"], reverse=True)
    results = []
    for record_A in sorted_list:
        video_name = record_A["video_name"]
        keyframe_id = record_A["keyframe_id"]
        if (video_name, keyframe_id) not in idx_results:
            continue
        idx_B = idx_results[(video_name, keyframe_id)]
        record_B = list_res_B[idx_B]
        results.append([record_A] + record_B)

    max_dict = {}
    for item in results:
        key = str(item[1]["video_name"]) + "_" + str(item[1]["keyframe_id"])
        if key not in max_dict or item[0]["score"] > max_dict[key][0]["score"]:
            max_dict[key] = item
    results = list(max_dict.values())

    return results


def preprocess_object_dict(object_dict):
    """Flatten {object_name: [detections]} into {(video, frame): [detections]}."""
    nested = defaultdict(lambda: defaultdict(list))
    for obj_name, det_list in object_dict.items():
        for det in det_list:
            vid = det["video"]
            frm = int(det["frame"])
            nested[vid][frm].append(
                {
                    "object": obj_name,
                    "conf": det["conf"],
                    "bbox": det["bbox"],
                }
            )

    return {
        (vid, frm): objs
        for vid, frames in nested.items()
        for frm, objs in frames.items()
    }


def preprocessing_text(model, text):
    """Extract a flat float32 text embedding from `model`."""
    text_feat_arr = model.get_text_features(text)
    text_feat_arr = text_feat_arr.reshape(1, -1).astype("float32")
    return text_feat_arr[0]


def preprocessing_image(model, image):
    """Extract a flat float32 image embedding from `model`."""
    image_feat_arr = model.get_image_features(image)
    image_feat_arr = image_feat_arr.reshape(1, -1).astype("float32")
    return image_feat_arr[0]
