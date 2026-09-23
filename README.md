# random42_aic

Video-retrieval backend for the AIC (video search) competition. Given a text/image query, it searches a
pre-indexed keyframe database (CLIP-family embeddings in Qdrant) and returns matching video moments, with
reranking, transcript search, object filters, and DRES competition submission built in.

This repo is a from-scratch restructuring of an earlier prototype (`SIU_Pumpking`) — same feature set, ported
into a clean `src/` layout. See [`migration.md`](migration.md) for exactly what moved where, and
[`review.md`](review.md) for known rough edges that still need attention.

## Architecture

The backend is 8 independently-deployable FastAPI services sharing one codebase. Each process is started with
`SERVICE=<name> uvicorn src.main:app`, which builds only that service's app (`src/main.py`):

| SERVICE | Purpose | Default port |
|---|---|---|
| `hub` | API gateway the UI calls: fans search out to the model services, media redirects, forwards `/submission` | 9021 |
| `result_manager` | Secondary UI for reviewing/exporting results | 9022 |
| `siglip_alpha` | SigLIP2 search backend (primary model + Qdrant collection) | 9029 |
| `siglip_beta` | SigLIP2 search backend (second model/collection, for A/B comparison) | 9030 |
| `metaclip` | MetaCLIP search backend (third model variant) | 9031 |
| `rerank` | Reranks candidate frames by dominant color | 9126 |
| `util` | Translation, neighboring-frame lookup, direct vector lookup | 9025 |
| `submission` | The team's ONE DRES client (KIS/QA/TRAKE): one session, duplicate guard; see `docs/SUBMISSION_SPEC.md` | 9024 |

**The UI is the React app in `src/ui/aic`**, served by the `frontend` container on **:10000** (this machine)
and, built, by the `gateway` nginx on **:9090** = the public ngrok URL for teammates (`docs/LOCAL.md`). The
hub's own Jinja UI on :9021 is retired. The browser only talks to one origin, which proxies `/hub`,
`/submission`, `/result_manager` and `/media` (keyframes + video from the `media_server` nginx, :9027).

```
src/
  apis/            FastAPI routers + the shared app factory (create_app)
  services/        Business logic per deployable service (one class per service)
  modules/         Reusable domain logic: CLIP model wrappers, rerank algorithm, score-fusion
  externals/       Thin clients for external systems: Qdrant, DRES, Google Translate
  common/schemas/  Pydantic request/response models shared across routers
  utils/           Settings, logging, path/frame helpers
  ui/aic/          THE UI: React + Vite app (dev server :10000; `./stack.sh ui-build` -> dist/ for the gateway)
  ui/templates,static  legacy Jinja UI (retired)
  pre_processing/  Offline pipeline: shot detection, feature extraction, VLM captioning, etc.
                   (not part of the live app — run these manually to (re)build a dataset index)
  main.py          Generic launcher; SERVICE env var selects which of the 8 apps to build & run
```

## Requirements

- Python 3.11
- An NVIDIA GPU (CUDA 12.8) for `siglip_alpha`/`siglip_beta`/`metaclip` — the rest run fine on CPU
- Docker + Docker Compose (recommended) or a local Python environment
- A dataset already processed into keyframes/features (see [pre-processing](#pre-processing-pipeline))

## Setup

```bash
cp .env.example .env
# fill in HUGGINGFACE_HUB_TOKEN, GG_TRANSLATE_API_KEY, SUBMIT_USERNAME/PASSWORD, and dataset paths
# (+ NGROK_AUTHTOKEN / NGROK_DOMAIN for `./stack.sh start --remote`: teammates, docs/LOCAL.md)
```

### Docker (recommended): `./stack.sh`

```bash
./stack.sh start            # server stack + hub + UI, preflight + full verify   -> http://localhost:10000
./stack.sh start --remote   # ... + gateway + ngrok tunnel (public URL for teammates)
./stack.sh verify | status | stop | restart | ui-build
python3 tools/ui_check.py [url]   # drive the real UI in a browser, every feature (Playwright)
```

`stack.sh` is the supported way to run it; the compose files underneath split by workload:

- **`docker-compose-server.yml`** — everything heavy: `siglip_alpha`/`siglip_beta`/`metaclip` (GPU), the 3
  Qdrant instances, `rerank`/`util`/`submission`/`result_manager`, and the `media_server` (nginx, serves
  keyframe images/video). Runs on a machine with an NVIDIA GPU.
- **`docker-compose-local.yml`** — the `hub` + the `frontend` (UI on :10000), on the same machine.
- **`docker-compose-gateway.yml`** — the public `gateway` nginx (:9090) + its `ngrok` tunnel.

```bash
# on the GPU server
# Copy .env.example to .env first. Inside the server stack, keep the three
# *_QDRANT_URL values pointed at their compose service names (the defaults do this).
docker compose -f docker-compose-server.yml up --build -d

# wherever you want the UI (can be the same machine or your laptop)
# first point .env's *_HOST_PUBLIC / NGINX_*_HOST vars at the server above
docker compose -f docker-compose-local.yml up --build
```

For the temporary local-machine configuration, `.env` uses host bind mounts for
the dataset, model cache, and logs. Replace those local paths with managed
storage before a final or public deployment; the model cache and logs contain
runtime state and must not be committed to the repository.

Scale the server stack down by commenting out services you don't need (e.g. drop `metaclip` +
`qdrant-metaclip` if you only run the two SIGLIP2 variants).

### Local Python environment

```bash
# running only the hub gateway (lightweight, no GPU deps needed):
pip install -r requirements-local.txt
export PYTHONPATH=.
SERVICE=hub uvicorn src.main:app --host 0.0.0.0 --port 9021 --reload

# running any other service (needs the full ML stack):
pip install -r requirements.txt
SERVICE=siglip_alpha uvicorn src.main:app --port 9029
```

The Qdrant index is **restored from disk** (`QDRANT_STORAGE_HOST_PATH`, a fast local ext4 disk) — it is
built once by the batch pipeline, not at startup. **Never call `GET /{model}/setup_database` on a built
index**: it re-ingests and destroys the collection (the public gateway refuses it).

Open **http://localhost:10000** for the UI (public: `https://$NGROK_DOMAIN` after `./stack.sh start --remote`).

## Pre-processing pipeline

`src/pre_processing/` builds the dataset a `SERVICE=siglip_alpha`-style search backend queries against. It is
not wired into the live app — run these as one-off/batch jobs before (re)indexing a dataset:

1. `shot_detection/run_pipeline.py` — shot-boundary detection (AutoShot) + keyframe extraction
2. `format/avif_compress.py`, `format/get_fps.py`, `format/indexer.py` — low-res frame compression, FPS lookup, frame indexing
3. `feature_extraction/clip_features.py` — SigLIP2 embeddings per keyframe
4. `feature_extraction/object_detection.py`, `format/compile_object_json.py` — object-detection features (optional)
5. `vlm_extractor/orchestrator.py` — VLM-based title/caption/context extraction (optional, for richer metadata)
6. `speech_to_text/extract.py`, `speech_to_text/frame_matching.py` — transcript extraction + keyframe alignment (optional)

Then load a `siglip_alpha`/`siglip_beta`/`metaclip` service and call its `setup_database` endpoint once to
ingest the produced features/metadata into Qdrant.

Each script takes CLI args for its input/output paths — run with `--help` for the full list.

## Configuration

All runtime configuration is one `Settings` object (`src/utils/settings.py`, pydantic-settings) loaded from
`.env` — see `.env.example` for every variable with inline comments. There is no other config file to edit.

## Development

`src/` is bind-mounted into every container (read-only), so a backend code
change needs a **restart, not a rebuild**:

```bash
docker compose -f docker-compose-server.yml restart util     # picks up src/ changes
docker compose -f docker-compose-local.yml  restart hub
```

Rebuild (`docker compose ... build <service>`) only when dependencies change —
`requirements.txt`, the Dockerfiles, or the Python version.

The frontend dev server polls for changes (`src/ui/aic/vite.config.js`): the repo
lives on a 9p/DrvFs mount where inotify events are never delivered, so without
polling Vite silently serves the files it read at startup and no refresh helps.

## Development tooling

```bash
pip install pre-commit
pre-commit install   # runs ruff (lint + format) and basic hygiene checks on every commit
```

## Known issues

See [`review.md`](review.md) for a running list of hardcoded values, insecure defaults, and other rough edges
carried over from the original prototype (or introduced during the port) that should be cleaned up before this
is treated as production-ready.
