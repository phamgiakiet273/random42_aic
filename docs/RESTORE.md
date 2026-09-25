# Handover — run this stack on another PC from the H: drive

Plug the drive into a new PC, run **one script**, start the stack. No
preprocessing: the index, the model weights, the dataset (keyframes, fps, shots,
transcripts) and the videos are all on the drive.

```
<drive>/random42/
├── migration/                  what restore.sh copies to the new PC's local disk
│   ├── RESTORE.md  restore.sh  MANIFEST.txt      (this doc, the script, file counts)
│   ├── qdrant_storage/         PUMPKING_SIGLIP_V2 902,050 pts
│   ├── qdrant_jina_storage/    EXPERT_B_V1 (optional second model, not started)
│   ├── hf_cache/               SigLIP2-giant (+ jina, + the s2t models)
│   └── docker-images/          random42-aic.tar, support-images.tar (qdrant, nginx, bun,
│                               alpine, ngrok), node_modules.tar (the UI's dependencies)
├── workspace/aic2026/          the repo (branch batch1/aic2026-data) + its .env
└── data/aic_2025/              served straight from the drive, read-only
    ├── 0/  1/                  keyframes, fps, shots, transcripts, features (batch 0 L, batch 1 M/N/S)
    ├── utils/                  duplicate / unique frame lists
    └── original/0/ original/1/ the videos
```

## Needs on the new PC

- Windows + WSL2 (Ubuntu), Docker Desktop with WSL integration on
- NVIDIA GPU, **16 GB VRAM** (the search model keeps ≥10 GB), current driver
- ~35 GB free on the WSL disk (index + model cache + repo)
- in WSL: `git curl jq python3` (`sudo apt install -y git curl jq python3`)

## Restore (once)

```bash
ls /mnt/            # find the drive's letter, e.g. /mnt/d
bash /mnt/d/random42/migration/restore.sh ~/random42
```

It copies the index + model cache to `~/random42` (local disk: running them off
the drive is ~100x slower), checks the file counts against `MANIFEST.txt`, loads
the Docker images, restores the UI's `node_modules`, copies the repo to
`~/random42/aic2026` and writes every machine-specific `.env` value (paths,
uid/gid, hostname). Nothing to edit by hand. Re-running it is safe.

## Start

```bash
cd ~/random42/aic2026
./stack.sh start            # UI: http://localhost:10000   (~2 min cold: the model loads)
./stack.sh start --remote   # + gateway + ngrok -> https://hallie-sabulous-nicholle.ngrok-free.dev
```

`start` refuses to run if the drive or the index isn't visible, then verifies:
902,050 points, index on a real disk, search on batch 0 and 1, UI, video
seeking, DRES session. Teammates connect with `docs/LOCAL.md`.

Full check, like a person using it: `python3 tools/ui_check.py` (needs
`pip install playwright && playwright install chromium`).

## Gotchas

- **Only one machine may run `--remote` at a time**: the ngrok domain belongs to
  one agent. Stop the old server's gateway first (`./stack.sh stop`).
- **`.env` holds the team's secrets** (DRES login, ngrok token, HF token). It
  travels on the drive; don't commit or share it.
- **Keep ≥10 GB of VRAM for the search model.** Don't start other GPU jobs
  beside the stack (a GPU out-of-memory takes all of WSL down).
- **After a reboot**, run `./stack.sh verify`; anything red -> `./stack.sh restart`
  (Docker can start containers before the drive is mounted).
- **After Docker Desktop is paused/resumed**, containers can keep running but lose
  their ports: `./stack.sh verify` shows which, `docker restart` them.
- **`.env` is read when a container is created**: after editing it use
  `./stack.sh restart`, not `docker restart`.
- **Never call `GET /siglip_alpha/setup_database`** (re-ingests, destroys the index)
  and **never `docker compose ... --remove-orphans`** (deletes the rest of the stack).
- The drive is slow for small files: never `du`/`find` over it.

## Keeping the drive current (on the running server)

```bash
bash handover/bundle.sh data    # dataset + videos (additive, any time)
bash handover/bundle.sh state   # index + images + node_modules + repo + MANIFEST (live: nothing is stopped)
```
