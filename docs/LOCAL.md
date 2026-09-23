# Client runbook — teammate machine

```
THIS MACHINE                                     SERVER  https://hallie-sabulous-nicholle.ngrok-free.dev
  browser → your nginx :9080 ─┬─ /media/frames ─▶ YOUR <DATA_ROOT>/0/, 1/   (local disk)
                              │                    └─ frame you don't have ─▶ server
                              └─ everything else ──── ngrok ────▶ gateway ─▶ UI, /hub (search),
                                                                            /submission (DRES), video
```

Search queries (small JSON), video and DRES submissions cross the tunnel. **Frames** —
by far the most requests — are served from your own disk. You run **one nginx**:
no conda env, no local hub, no UI build, no DRES login (the server holds the team's
one DRES session).

---

## What you need on disk

Just the keyframes, under a folder `<DATA_ROOT>` that **contains** `0/` and `1/`:

```
<DATA_ROOT>/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif
<DATA_ROOT>/1/frames/low_res_autoshot/Keyframes_M05/keyframes/M05_V001/00042.avif
```

Both come as tarballs from the server's `E:\workspace\AIC_2026\data\`:

```bash
tar -xf 0.tar -C <DATA_ROOT>   # 2.9 GB, batch 0 (L)
tar -xf 1.tar -C <DATA_ROOT>   # 7.6 GB, batch 1: N + S + M (603,703 keyframes)
```

**You do NOT need** videos, features, transcripts, fps or shot files: the server
reads those and sends back results. A frame you don't have is fetched from the
server instead (slower), so a partial copy still works.

## 1. Get the config

From the `aic2026` repo (branch `batch1/aic2026-data`):

```bash
cp nginx/teammate.conf.example nginx/teammate.conf    # gitignored copy you edit
```

## 2. Point nginx at your keyframes

Open `nginx/teammate.conf` and edit **one line** — the `alias` under
`location /media/frames/`, marked `<<< EDIT`:

```nginx
location /media/frames/ {
    alias /home/kiet/data/aic_data/;   # <<< EDIT: your DATA_ROOT
```

- `<DATA_ROOT>` is the folder that **contains** `0/` — not `0/` itself, not `0/frames`.
- **Keep the trailing `/`**, absolute path.
- The server address is already set (`https://hallie-sabulous-nicholle.ngrok-free.dev`).

## 3. Run nginx

**A. The nginx you have** — SIU_Pumpking's bundled binary (Linux x86-64), or
`brew install nginx` on macOS:

```bash
NGINX=nginx                                                            # brew / distro
# NGINX="/path/SIU_Pumpking/nginx/sbin/nginx -p /path/SIU_Pumpking/nginx"  # bundled
$NGINX -c "$PWD/nginx/teammate.conf" -t    # check
$NGINX -c "$PWD/nginx/teammate.conf"       # start   (-s reload after edits, -s stop)
```

It has its own pid file and port (9080), so it runs beside the legacy one.

**B. Docker** — any OS, no nginx and no conf edit (step 2 not needed):

```bash
AIC_FRAMES=<DATA_ROOT> docker compose -f docker-compose-teammate.yml up -d
# PowerShell: $env:AIC_FRAMES="D:\aic_data"; docker compose -f docker-compose-teammate.yml up -d
# stop: docker rm -f aic2026-teammate-web-1
```

## 4. Verify

```bash
curl localhost:9080/hub/ping                                 # server reachable
curl localhost:9080/submission/get_session_and_eval          # "status":200 = team DRES session up
curl -I localhost:9080/media/frames/1/frames/low_res_autoshot/Keyframes_M05/keyframes/M05_V001/00042.avif
```

Then open **<http://localhost:9080>**. The DRES badge shows "no ACTIVE evaluation"
until BTC opens one — that is normal.

---

## No-nginx fallback

If your nginx won't run (or dies mid-task), open
**<https://hallie-sabulous-nicholle.ngrok-free.dev>** directly. Same UI, same search,
same team DRES session — only every keyframe comes from the server, so thumbnails
are slower (~1.4 MB per results page). Switching loses what's only on the page
(unsent TRAKE marks, settings), like a reload.

## Differences from the legacy client (SIU_Pumpking)

| | Legacy `README_LOCAL.md` | Now |
|---|---|---|
| You run | conda hub + nginx | **nginx only** |
| Tunnels | SSH/ngrok, 3–5 ports | **one URL** (ngrok) |
| UI | hub's own page, :9021 | React app, :9080 (yours) / the ngrok URL |
| Keyframes | `0/` only | `0/` + `1/` (N, S, M); missing ones come from the server |
| DRES | each client logs in | **one central session** on the server; duplicate answers refused team-wide |
| nginx edit | the `/img/` alias | the `/media/frames/` alias |

## Gotchas

| Symptom | Fix |
|---|---|
| `ERR_NGROK_3200` / nothing loads | The server tunnel is down: ask the server owner to run `./stack.sh start --remote` |
| Thumbnails slow or broken | Wrong `alias`: it must CONTAIN `0/`, keep the trailing `/` (Docker: check `AIC_FRAMES`) |
| Bundled nginx won't start (macOS, missing `libpcre`) | Use B (Docker) or brew nginx — or the no-nginx fallback now |
| Port 9080 busy | Change `listen 9080` in the conf (and `ports` in the compose file) |
| A 2026 video missing from the video picker | Tick **Batch 1** in Filters (on by default) |
| No traffic-cam / cycling results | Tick **Traffic CCTV** / **Cycling** under Content (off by default) |
| ngrok down, SSH works | Set `$aic_server` to `http://127.0.0.1:9090` (Docker: `http://host.docker.internal:9090`) + `ssh -L 9090:localhost:9090 <server>` |

---

## Server side (whoever runs the server)

```bash
./stack.sh start --remote   # stack + UI build + gateway (:9090) + ngrok; verifies the public URL
./stack.sh ui-build         # after UI changes: the gateway serves the build, not the source
python3 tools/ui_check.py https://$NGROK_DOMAIN   # real browser, every UI feature
```

- ngrok settings: `NGROK_AUTHTOKEN`, `NGROK_DOMAIN` in `.env` (gitignored).
- Only 9090 is published. Qdrant (6333/6335) never — it has no auth.
  `setup_database` is refused at the gateway (it would destroy the index).
- After Docker Desktop is paused/resumed, containers can lose their host port
  bindings while still running: `./stack.sh verify` shows which, `docker restart` them.
