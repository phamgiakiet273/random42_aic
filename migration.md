# Migration map: SIU_Pumpking -> random42_aic

Old repo: `SIU_Pumpking/SIU_Pumpking/` (flat, 7 hand-copied FastAPI services, 10 separate `os.getenv`-based
config classes, offline scripts mixed in with live code). New repo: this one, `src/` laid out by responsibility
(apis / services / modules / externals / common / utils / ui / pre_processing). The 7 services stay separately
deployable — they're now selected via `SERVICE=<name>` against one shared `src/main.py`, instead of 7 copy-pasted
entrypoint files. See [`review.md`](review.md) for open questions and known behavior deltas introduced below.

## Shared infrastructure

| Old | New | Notes |
|---|---|---|
| `configs/*.py` (10 classes: `app.py`, `hub_config.py`, `SIGLIP_v2_configs.py`, `SIGLIP_v2_B_configs.py`, `METACLIP_configs.py`, `nginx_config.py`, `rerank.py`, `result_manager_config.py`, `submission.py`, `util.py`) | `src/utils/settings.py` | Collapsed into one `pydantic-settings` `Settings` class. Fixed `METACLIP_QDRANT_HOST` (was misnamed - held a port number) into proper `METACLIP_QDRANT_URL/PORT/GRPC_PORT` fields, and gave METACLIP full field parity with the SIGLIP configs (host_public, qdrant grpc port, etc.) since it's now a supported variant. |
| `configs/logger.py` + `utils/logger.py` | `src/utils/logger.py` | Merged; same loguru sinks (stdout + rotating file), driven by `Settings` instead of a separate `LoggerConfig`. |
| Fragile `sys.path` walk (`for parent in current_path.parents: if parent.name == "SIU_Pumpking": ...`) present in nearly every legacy file | removed entirely | Replaced by normal `from src.xxx import yyy` absolute imports now that everything lives under one `src` package. |

## Schemas

| Old | New |
|---|---|
| `schema/api.py` | `src/common/schemas/api.py` |
| `schema/hub.py` (dropped commented-out dead `TextQuery`/`TemporalQuery`) | `src/common/schemas/hub.py` |
| `schema/rerank.py` | `src/common/schemas/rerank.py` |
| `schema/submission.py` | `src/common/schemas/submission.py` |
| `schema/util.py` | `src/common/schemas/util.py` |
| `schema/vector_v2.py` | `src/common/schemas/vector.py` (dropped the "v2" suffix — there's only one version now) |

## External system clients (new layer — didn't exist as a separate concept before)

| Old | New | Notes |
|---|---|---|
| `engine/vector_database/qdrant_database.py` (`QDRANT` class) | `src/externals/qdrant_client.py` (`QdrantSearchClient`) | Renamed class. Constructor now takes `qdrant_url/port/grpc_port/collection_name` as explicit params instead of reading a config object, so it can be instantiated 3x (alpha/beta/metaclip) from the same code. Hardcoded dup/unique-check paths became constructor params defaulting from `Settings` (see review.md #2). Fixed a literal Python syntax error (stray unquoted Vietnamese comment) and a couple of mutable-default-argument bugs found while porting. |
| DRES HTTP calls inside `handlers/submission_handler.py` | `src/externals/dres_client.py` (`DRESClient`) | Extracted the thin HTTP-calling part only; payload-building business logic stayed in `src/services/submission_service.py`. Login is no longer a constructor side effect — call `.login()` explicitly. |
| Google Translate call inside `handlers/util_handler.py` | `src/externals/translate_client.py` (`TranslateClient`) | Thin async wrapper; sentence-splitting logic stayed in `src/services/util_service.py` (business logic, not a client concern). |

## Modules (reusable domain logic — new layer)

| Old | New | Notes |
|---|---|---|
| `engine/CLIPFeatureModel/siglip2_model.py` (`SIGLIP2`) | `src/modules/clip_models/siglip2.py` (`Siglip2Model`) | Constructor now takes `cuda_visible_devices`/`cache_dir`/`hf_token` explicitly instead of reading a config class internally, so alpha/beta can each instantiate it with different settings. |
| `engine/CLIPFeatureModel/metaclip_model.py` (`METACLIP`) | `src/modules/clip_models/metaclip.py` (`MetaclipModel`) | Same generalization. Built fresh from the *working* `metaclip_model.py`, not the broken `metaclip2_model.py` (see "Dropped" below). |
| `engine/rerank/sort_by_dominant_color/color_sort_gen.py` (`step_sort_key`) **and** `handlers/rerank_handler.py`'s inline `_step()` (a near-duplicate) | `src/modules/rerank/color_sort.py` | Deduplicated into one function. The two originals weren't quite byte-identical (see review.md) — canonical behavior now matches the live request-path version. |
| `engine/rerank/sort_by_dominant_color/dominant_color.py` (`get_dominant_color`) | `src/modules/rerank/color_sort.py` | Merged into the same module as `step_sort_key` since both are used together. |
| `utils/vector_database_util.py` (`merge_scores`, `merge_scores_reverse`, `preprocess_object_dict`, `preprocessing_text`, `preprocessing_image`) | `src/modules/vector_search/fusion.py` | Direct port, no behavior change. |

## Services (business logic — replaces `handlers/*.py`)

| Old | New | Notes |
|---|---|---|
| `handlers/SIGLIP_v2_handler.py`, `handlers/SIGLIP_v2_B_handler.py`, `handlers/METACLIP_handler.py` (3 structurally-identical classes) | `src/services/clip_service.py` (`ClipSearchService`) | Collapsed into ONE class taking an already-built model + `QdrantSearchClient`; the caller (`src/main.py`) decides which model/collection pair to inject per variant. |
| `handlers/hub_handler.py` (~1060 lines) | `src/services/hub_service.py` (`HubGatewayService`) | Same HTTP-proxying gateway role. Removed the unconditional `debug_failed_image.bin` debug write; turned the never-actually-scheduled session/eval-id background refresh loop into a real `start_session_refresh_loop()` wired up via `main.py`'s `lifespan`; replaced mixed `flask.json`/`ujson` usage with just `ujson`; all `*_HOST_PUBLIC`/nginx/split-name values now come from `Settings` instead of ad hoc `os.getenv()` calls. Gained generalized `metaclip` passthrough methods alongside the existing alpha/beta ones (see review.md). |
| `handlers/rerank_handler.py` | `src/services/rerank_service.py` (`RerankService`) | Now branches on `get_batch()` for the `Keyframes_L`/`Keyframes_K` path prefix instead of always assuming batch 0 (bug fix, see review.md). Uses the shared `color_sort.step_sort_key` instead of its own inline copy. |
| `handlers/submission_handler.py` | `src/services/submission_service.py` (`SubmissionService`) | Dropped the large dead commented-out `submit_handler` block. No more auto-login in `__init__`. Shared `_submit()` helper replaces 3 copy-pasted submit-and-parse blocks. |
| `handlers/util_handler.py` | `src/services/util_service.py` (`UtilService`) | `get_vector` rewritten to use an injected `QdrantSearchClient` instead of a hardcoded module-level client bypassing all config (see review.md). |
| `handlers/result_manager_handler.py` | `src/services/result_manager_service.py` (`ResultManagerService`) | Same path-building logic, batch-1 zero-pad quirk preserved and documented; one pre-existing inconsistency deliberately left as-is and flagged (see review.md). |
| `utils/metadata_util.py` | `src/utils/metadata.py` | Direct port, config source switched to `Settings`. |
| `utils/get_k_frames.py` | `src/utils/video_batch.py` | Direct port (`get_batch`, `get_neighboring_frames`), config source switched to `Settings`. |
| `utils/get_name_videos.py` | `src/utils/video_names.py` | Direct port, config source switched to `Settings`. |

## APIs (FastAPI routers + app factory)

| Old | New | Notes |
|---|---|---|
| `apis/api.py` (generic `setup_app()`) | `src/apis/base.py` (`create_app()`) | Dropped the defined-but-never-attached `TimeoutMiddleware` (legacy dead code). Added optional `lifespan` passthrough for services that need startup hooks. |
| `apis/hub.py`, `apis/result_manager.py` | `src/apis/base.py` (`create_app(templates_dir=..., static_dir=..., template_name=...)`) | Both folded into the same factory via parameters instead of two near-duplicate files. |
| `routes/hub_router.py` | `src/apis/hub_api.py` | Same `/hub` prefix and route surface, plus generalized `metaclip` passthrough routes. |
| `routes/SIGLIP_v2_router.py`, `routes/SIGLIP_v2_B_router.py`, `routes/METACLIP_router.py` | `src/apis/clip_api.py` (`build_router(service, prefix)`) | One router factory reused 3x instead of 3 near-identical files. |
| `routes/rerank_router.py` | `src/apis/rerank_api.py` | Direct port. |
| `routes/submission_router.py` | `src/apis/submission_api.py` | `DRESSubmitError` from the service layer is converted to `HTTPException` at this layer. |
| `routes/util_router.py` | `src/apis/util_api.py` | Direct port. |
| `routes/result_manager_router.py` | `src/apis/result_manager_api.py` | Direct port. |
| `services/hub_service.py`, `services/rerank_service.py`, `services/result_manager_service.py`, `services/submission_service.py`, `services/util_service.py`, `services/SIGLIP_v2_service.py`, `services/SIGLIP_v2_B_service.py`, `services/METACLIP_service.py` (7 hand-copied uvicorn entrypoints — same directory name as, but a completely different role from, the new `src/services/`) | `src/main.py` | One generic launcher; `SERVICE` env var picks which app to build. Same host/port/worker-count wiring, GZip opt-out, and SIGINT/SIGTERM graceful shutdown behavior, without the copy-paste. |

## Frontend

| Old | New | Notes |
|---|---|---|
| `static/js/*.js`, `static/css/*.css`, `static/icon/*` | `src/ui/static/{js,css,icon}/` | Copied as-is, no logic changes. |
| `templates/index.html` (live, 334 lines) | `src/ui/templates/hub.html` | Copied. |
| `templates_result_manager/index.html` (root-level) | `src/ui/templates/result_manager.html` | Copied. |
| `templates/old/*`, `templates/backup/index.html`, `schema/templates_result_manager/index.html` | **dropped** | Confirmed stale/duplicate: `templates/old/` and `templates/backup/` were earlier/shorter snapshots superseded by the live `templates/index.html`; `schema/templates_result_manager/index.html` was a stray duplicate never actually read by `apis/result_manager.py` (which only looks at the repo-root copy). |

## Pre-processing pipeline (`src/pre_processing/`, new dedicated home — was scattered across `engine/`, `src/`, and `utils/` mixed in with live code)

| Old | New | Notes |
|---|---|---|
| `engine/shot_boundary_detection/Shot_Detection/shot_detecion_selector.py` | `src/pre_processing/shot_detection/detector.py` | Hardcoded absolute checkpoint path became a constructor param. |
| `engine/shot_boundary_detection/Shot_Detection/io_setup.py` | `src/pre_processing/shot_detection/io_utils.py` | Fixed a `NameError` bug (`self.input_dir` referenced inside a plain function). |
| `engine/shot_boundary_detection/Shot_Detection/AutoShot/*.py` | `src/pre_processing/shot_detection/autoshot/*.py` | Copied as-is — this is the actual model architecture needed to load the checkpoint, not a generic vendored framework. |
| `src/frame_split/autoshot.py` | `src/pre_processing/shot_detection/run_pipeline.py` | 3 hardcoded batch input/output dirs -> CLI args; no more top-level execution on import. |
| `src/feature_extraction/clip_feature_extract.py` | `src/pre_processing/feature_extraction/clip_features.py` | Rewritten against `Siglip2Model` (legacy used the *old* `siglip_model.SIGLIP`, not the current `SIGLIP2` — a staleness bug, now fixed). 3 near-duplicate `batch_0/1/2()` functions collapsed into one parametrized `extract_features()`. |
| `src/feature_extraction/detic_object_extract.py` | `src/pre_processing/feature_extraction/object_detection.py` | Hardcoded paths/GPU id -> function/CLI args. |
| `src/format/avif_compress.py`, `compile_object_json.py`, `get_fps.py` | `src/pre_processing/format/{avif_compress,compile_object_json,get_fps}.py` | Hardcoded per-batch dicts -> CLI args; wrapped in `if __name__ == "__main__":` (legacy ran at import time). |
| `src/frame_split/indexer.py` | `src/pre_processing/format/indexer.py` | Same CLI-args treatment. |
| `engine/VLM_Extractor/` (the newer of two competing implementations) | `src/pre_processing/vlm_extractor/` | Fixed `maintest.py`'s undefined `PROJECT_ROOT` bug when porting it to `orchestrator.py`. Everything now reads paths from `Settings` instead of hardcoded dev-machine paths. |
| `engine/Object_Detection/YOLOE_Prompt_Free/prompt_free.py` | `src/pre_processing/object_detection/prompt_free_demo.py` | Fixed a path-concatenation bug (`"data/examplesprediction_output.jpg"` missing a `/`). |
| `engine/speech_to_text/{SpeechToText,speech_extraction,speech_frame_matching}.py` | `src/pre_processing/speech_to_text/{stt,extract,frame_matching}.py` | Fixed a `NameError` (referenced an unimported `METACLIPV2Config`); all hardcoded absolute paths -> CLI args/`Settings`. Untested against real data (see review.md). |
| `engine/scene_classifier/news_introduction_detect.py` + `yolo_classifier_train.py` (2 near-duplicate files, both with a missing-`self` bug in `train()`) | `src/pre_processing/scene_classifier/news_intro_classifier.py` | Merged into one class, bug fixed. |

## Dropped entirely (confirmed dead, superseded, or explicitly out of scope)

| Path | Why |
|---|---|
| `engine/CLIPFeatureModel/siglip_model.py` | Old SigLIP v1, only used by unmounted experimental code; has garbage text appended after the code. |
| `engine/CLIPFeatureModel/metaclip2_model.py` | Broken import (`configs.METACLIP_v2_configs` doesn't exist in the repo), hardcoded dev-machine `sys.path`, unreferenced anywhere. |
| `engine/vector_database/qdrant_database_old.py`, `_old1.py`, `_old2.py` | Confirmed sequential dev snapshots superseded by `qdrant_database.py`. |
| `engine/VLMs/` (predecessor of `VLM_Extractor/`) | Confirmed superseded: duplicated inline logic (site lists, model loading) that `VLM_Extractor` later extracted into shared, config-driven modules. |
| `engine/Object_Detection/Detic/` + `third_party/` (CenterNet2, Deformable-DETR) | Large vendored detectron2-based framework (~250 files) — out of scope for this port, needs separate vendoring if required later. |
| `engine/scene_classifier/*` original two files | Superseded by the merged, bug-fixed `news_intro_classifier.py`. |
| `routes/router.py` + `handlers/general.py` | Broken import (`handler.general` vs. real package `handlers`), empty handler file, referenced nowhere. |
| `routes/experimental_api/clip_feature_api.py` | A Flask app (inconsistent with the rest of the FastAPI stack), unmounted anywhere, entrypoint commented out. |
| Legacy root Flask monolith (`server.py`) and its templates (`templates/old/keyframes.html`, `video.html`, `video_modal.html`) | Superseded by the FastAPI services. |
| `src/frame_split/pyscenedetect.py` | Misleadingly named — doesn't call PySceneDetect at all, just an exact duplicate of `indexer.py`. |
| `src/frame_split/autoshot_name_refract.py` | One-off historical directory-migration script, not a repeatable pipeline step. |
| `src/pysencedetec.py` | Unrelated one-off dev tool (frame extraction for manual inspection). |
| `utils/get_topic_videos.py` | Zero importers anywhere in the legacy repo; hardcoded competition-year-specific topic taxonomy that won't apply to a new dataset. |
| `utils/test.py`, `utils/test_load_object_dict.py` | Scratch/debug scripts, not real tests (no pytest, no assertions). |
| `docs/test_dres.py`, `docs/test_get_path.py` | Manual smoke-test scripts, not real tests; superseded by proper package structure. |
| Vendored `nginx/` (full nginx 1.24.0 source + compiled binary + build objects) | Replaced by the official `nginx:alpine` Docker image — vendoring a compiled web server into git was itself a bad practice, not just outdated code. |
| `data/weights/`, `data/qdrant_storage/`, log files, `.pyc`/`__pycache__` | Build artifacts / runtime state, never source — not applicable to a source-code port. |

## Model-variant scope decision

Per an explicit product decision made during this port: all **three** CLIP model variants (SIGLIP2 alpha,
SIGLIP2 beta, METACLIP) are kept as configurable variants of `src/services/clip_service.py`, even though
METACLIP was never actually deployed in the legacy system (no `.env` values existed for it there). See
review.md for what that means for testing before relying on the `metaclip` service.
