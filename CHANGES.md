# Session changelog

Task given: finish the 2026 port — merge `shark_backend_v1` + `fusion_model` +
`frontend-init`, resolve the API-doc comments, wire the new frontend to the
backend with at least the key legacy features.

## Integration

- Ported `fusion_model` and `frontend-init` forward onto `shark_backend_v1`
  rather than merging: both branched before the `/hub/search` consolidation, so
  a merge would have silently reverted it.
- Fusion (`jina_clip_v2`, `gating`, `fusion_model_service`) ported dormant.
  `SERVICE=fusion_model` fails fast — expert B needs a jina collection that
  does not exist.
- Tag `pre-integration-backup` marks the pre-change state. **Nothing committed.**

## API-doc comments resolved

| # | Change |
|---|---|
| [c][n] | Single `POST /hub/search`; `model` + `search_type` |
| [o] | Results score-sorted, `score` numeric, `index` = final rank |
| [p][t] | `frame_path`/`video_path` dropped; `GET /hub/media_config` publishes the layout rule, owned by `src/utils/dataset_layout.py` |
| [k] | `object` / `return_object` removed (48 refs) — empty on all 872,631 points |
| [s] | `send_img_original` no longer rewrites `.avif`→`.jpg` at files that don't exist |
| [l] | `POST /hub/download` — stateless, KIS format |

Deferred per your call: [e] rerank removal, [b][q][r] submission.

## Backend fixes

- **fp16 model load** restored (was fp32, 7.5GB on a 16GB card).
- **HF cache**: `load_dotenv()` before `transformers` imports; `TRANSFORMERS_CACHE`
  is the alias for `HF_HUB_CACHE` (the hub dir, not its parent). Load 2h → 8s.
- **`dtype` vs `torch_dtype`**: version-detected. Conda has transformers 4.57.1,
  the image pins 4.51.3 — one name crashes each.
- **Qdrant prep memoised** to a host-mounted cache. Startup 93s → ~10s.
- **`s2t`** emitted as a real JSON array (was a Python repr, unparseable).
- **`get_video_names`** reads the keyframe tree, not `videos/`: batch 1 has no
  .mp4 files here, so it reported 0 names and batch-1 videos were unfilterable.
- Scroll `score` is `0.0`, not the fabricated `"0.273"`.

## Frontend

Wired from `dummy.js` to the real API: text / image / temporal / scroll search,
grid, filters, settings, frame modal (seek, live current-frame, neighbours,
transcript), CSV export, result manager (via its own service, which resolves the
batch a CSV row can't know).

Fixed after your review:
- Browse sent `utility_feature=frame`, which does not exist → 500. Valid modes
  are `shot` / `dup` / `unique`.
- Per-card **browse-shot** and **find-similar** actions added (were missing);
  they were then invisible behind `opacity-0` until hover.
- Temporal renders one row per chain, columns = events, at the configured
  thumbnail size, centred.
- Frame class colours the rank badge (legacy palette), translucent.
- Neighbour strip includes and centres the current frame; centring computed from
  `offsetLeft` with fixed-size boxes, since lazy images made layout
  non-deterministic.
- Batch checkboxes scope the search; default batch 0. Applied scope shown, and a
  warning when it cannot be applied instead of silently searching everything.
- Enter searches from the query box (Shift+Enter = newline) and filter inputs.
- Card shows `video, frame`; timecode and score removed.
- Removed: TRAKE download, bulk select/range bar, unique button (unrequested).

## Infrastructure

- Full Docker stack incl. GPU. The "No CUDA GPUs available" note in
  `start_services.sh` was written for a different machine; this box works.
- Qdrant: reuses the running `qdrant-pumpking` (v1.15.5, 872,631 points) via
  `host.docker.internal`. Compose's own qdrant services are **not** started —
  they pin v1.14.1 against v1.15.5 storage.
- `./src` bind-mounted read-only into all services: restart, not rebuild.
- Vite proxies `/hub`, `/img`, `/video`, `/result_manager` — one port for remote
  use, since absolute `localhost` URLs resolve to the viewer's machine.
- Vite watcher polls: `/mnt/e` is 9p, inotify never fires, so edits were served
  stale and no refresh helped.
- `.env` is container-shaped; `.env.baremetal` holds the host variant.

## Known, not fixed

- Remote video is slow: files are non-faststart (moov at the end of 80–280MB),
  and nginx `?start=` 500s because 9p `msize=65536` short-reads a 1MB `pread`.
  Options: faststart remux, move videos to ext4, or nginx as single origin.
- Batch-1 (`K*`) videos absent from disk — thumbnails work, playback 404s.
- Only `siglip_alpha` has an index.
