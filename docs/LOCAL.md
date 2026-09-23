# Client runbook — running the UI on your own machine

## Teammates: just your nginx (recommended)

If you already run the SIU_Pumpking client (conda hub + bundled nginx), this
replaces it with **one nginx config**. No conda env, no local hub, no UI build, no
DRES password: the server runs the hub, the UI build and the team's ONE DRES
client, and your nginx only adds your local keyframes.

```
THIS MACHINE                                     SERVER  (gateway :9090 = the ngrok URL)
  browser → your nginx :9080 ─┬─ /media/frames ──▶ YOUR disk (0/, 1/)   ─404─▶ server
                              └─ everything else ─ngrok / ssh─▶ gateway ─┬─ /            UI build
                                 (UI, /hub, /submission, video)          ├─ /hub         hub
                                                                         ├─ /submission  central DRES client
                                                                         └─ /media/clips video
```

1. `cp nginx/teammate.conf.example nginx/teammate.conf` (gitignored) and edit the
   `<<< EDIT` line: your keyframe folder, the one that **contains** `0/` (keep the
   trailing `/`). Frames you don't have are fetched from the server automatically,
   so a partial copy works -- just slower for the missing part (see
   [What you need on disk](#what-you-need-on-disk); the batch-1 tar has no `M`).

   The server address is already set: `https://hallie-sabulous-nicholle.ngrok-free.dev`
   (the team ngrok account). If ngrok is down, use `http://127.0.0.1:9090` with
   `ssh -L 9090:localhost:9090 <server>` (one port replaces the old five).
   Heads-up for the legacy client: that domain used to be SIGLIP alone; it is now
   the gateway (which still routes `/siglip_alpha/`).
2. Run it with the nginx you already have (SIU_Pumpking's bundled one works):
   ```bash
   NGINX=/path/to/SIU_Pumpking/nginx
   $NGINX/sbin/nginx -p $NGINX -c "$PWD/nginx/teammate.conf" -t   # check
   $NGINX/sbin/nginx -p $NGINX -c "$PWD/nginx/teammate.conf"      # start (-s reload / -s stop)
   ```
   It has its own pid file and port (9080), so it can run beside the legacy one.
3. Open <http://localhost:9080>. Check:
   ```bash
   curl localhost:9080/hub/ping
   curl localhost:9080/submission/get_session_and_eval   # status 200 = team session is up
   ```

Server side: `./stack.sh start --remote` starts the gateway, builds the UI it serves,
and starts the ngrok tunnel (a container; `NGROK_AUTHTOKEN` / `NGROK_DOMAIN` in `.env`).

What crosses ngrok: search requests/results (small JSON), the UI files (once,
then cached), the clips you play, submissions, and keyframes you don't have. Your
browser only ever talks to `localhost:9080`; your nginx is what talks to ngrok.

## Docker client (hub in a container)

The older route below runs its own hub container and a prebuilt `dist/`. It
still works (its hub forwards `/submission` to the central service), but the
nginx-only setup above is simpler. The sections from here to "Gotchas" are for
this route; "What you need on disk" applies to both.

```
THIS MACHINE                                   SERVER
  browser → web :9080 ─┬─ /hub ──▶ hub container ──tunnel──▶ siglip :9029 → qdrant
                       │                          └─tunnel──▶ util   :9025
                       ├─ /media/frames  ──▶ YOUR aic_2025/0/frames/   (local disk)
                       └─ /media/clips ─tunnel──▶ server media nginx
```

Search queries (small JSON) and video cross the tunnel. **Frames** — by far the
most requests — are served from your own disk.

One port (`9080`) is all the browser touches: the same nginx serves the SPA, the
frames, and proxies `/hub` and `/media/clips`. That works because `NGINX_IMAGE_HOST`
and `NGINX_VIDEO_HOST` are *relative*; make them absolute and remote access
breaks, because `localhost` would then mean the viewer's machine.

## What you need on disk

Just the keyframes:

```
<DATASET_HOST_PATH>/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00016.avif
```

`DATASET_HOST_PATH` is the folder that **contains** `0/` **and** `1/` — not
`0/`, not `0/frames`.

Batch 1 (AIC 2026) is served too (`N` traffic, `S` cycling, `M` news), so you
also want its keyframes:

```
<DATASET_HOST_PATH>/1/frames/low_res_autoshot/Keyframes_N001/keyframes/N001_V001/00000.avif
```

Grab them from the packaged tarball (`1_frames_low_res_autoshot.tar`, ~3 GB, on
the server's F:) and unpack under `<DATASET_HOST_PATH>/1/frames/`. That tar was
packed before `M` arrived: it holds `N` + `S` only.

Missing keyframes: the **teammate nginx** fetches them from the server (they load,
over ngrok); the **Docker client** shows a broken thumbnail instead.

You do **not** need `0/fps/`, `0/speech_to_text2/`, `0/shot/`, `utils/object/`
or `0/features/`: the hub never opens them; the server's services read them and
return the results. Their `*_PATH` entries in `.env.client` may dangle.

Videos are not local — playback is proxied to the server, so only the clip you
actually click is streamed.

## 1. Build the SPA

nginx serves the built files, so there is no Node/Vite to run:

```bash
cd src/ui/aic && bun install && bun run build   # produces dist/
```

## 2. Reach the server

**ngrok (default now)** — the server's `./stack.sh start --remote` publishes ONE
URL, the gateway, which routes every path below. Point all of these in
`.env.client` at it:

```ini
SIGLIP_V2_HOST_PUBLIC=https://hallie-sabulous-nicholle.ngrok-free.dev
UTIL_HOST_PUBLIC=https://hallie-sabulous-nicholle.ngrok-free.dev
SUBMISSION_HOST_PUBLIC=https://hallie-sabulous-nicholle.ngrok-free.dev
VIDEO_UPSTREAM=https://hallie-sabulous-nicholle.ngrok-free.dev
RESULT_MANAGER_UPSTREAM=https://hallie-sabulous-nicholle.ngrok-free.dev
```

**SSH** (what the defaults in `.env.client` assume) — siglip, util, result
manager, the central submission service, and the media nginx for video (its
9027 → your 9028):

```bash
ssh -N \
  -L 9029:localhost:9029 \
  -L 9025:localhost:9025 \
  -L 9022:localhost:9022 \
  -L 9024:localhost:9024 \
  -L 9028:localhost:9027 \
  <user>@<server-host>
```

## 3. Edit `.env.client`

Only two lines usually need changing:

```ini
DATASET_HOST_PATH=/your/path/to/aic_2025   # the folder containing 0/
CLIENT_PORT=9080
```

## 4. Run

```bash
docker compose -f docker-compose-client.yml --env-file .env.client up -d --build
```

Open <http://localhost:9080>.

## 5. Verify

```bash
curl http://localhost:9080/hub/ping                    # hub
curl http://localhost:9080/hub/media_config            # should show /media/frames and /video
curl -I http://localhost:9080/media/frames/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif
curl -I -r 0-100 http://localhost:9080/media/clips/0/videos/Videos_L21/video/L21_V001.mp4
curl http://localhost:9080/submission/get_session_and_eval   # status 200 = team session is up
curl http://localhost:9029/siglip_alpha/ping           # SSH tunnel only
curl http://localhost:9025/util/ping                   # SSH tunnel only
```

Substitute a frame that actually exists.

## Differences from the server stack

| | Server | Client |
|---|---|---|
| Compose file | `docker-compose-server.yml` + `-local.yml` | `docker-compose-client.yml` |
| Services | hub, siglip, util, result_manager, media_server | hub, web (nginx) |
| GPU | required for siglip | none |
| siglip / util | local containers | ngrok gateway or SSH tunnel |
| DRES submission | central `submission` service | the server's, via its hub |
| Frames | server dataset | **your disk** |
| Video | local media nginx | ngrok gateway or SSH tunnel |
| Browser ports | 10000 (vite) + others | **9080 only** |
| SPA | vite dev server | prebuilt `dist/` on nginx |

## Gotchas

- **Trailing slash on the `/media/frames/` alias** — the usual cause of blank thumbnails.
  It is already correct in `nginx/client.conf`; only change the mount.
- **Keep `NGINX_IMAGE_HOST` / `NGINX_VIDEO_HOST` relative.** Absolute values are
  baked into URLs the browser fetches and only work when the browser runs on the
  server.
- **`.env` is read when a container is created**, not on restart. After editing
  it: `up -d --force-recreate`, not `restart`.
- **Frames you don't have** 404 individually; the rest of the UI keeps working.
  The Docker client needs batch 0 **and** batch 1 (`N`/`S`/`M`) keyframes locally;
  a missing set means broken thumbnails for that subset (the teammate nginx
  fetches them from the server instead). Or scope searches with the UI
  **Content** checkboxes to the subsets you do have.
- **Rebuild the SPA** (`bun run build`) after pulling frontend changes — nginx
  serves `dist/`, so source edits alone change nothing.

## DRES submission: one central service for the whole team

Nothing on a client logs in to DRES. The server runs ONE submission service
(`SERVICE=submission`, :9024) that owns the team's single DRES session. It logs in
once (again only if DRES drops the session), re-reads the ACTIVE evaluation every
10 s, submits with **its** session and evaluation (ids a client sends are ignored),
and refuses the same answer to the same evaluation within 5 min for the whole team
(HTTP 409, nothing sent). Every attempt is appended to `logs/submissions.jsonl`.

How each UI reaches it:
- **Teammates (nginx only):** browser → your nginx → gateway `/submission/` → service.
- **Server UI (`localhost:10000`):** browser → vite → hub `/submission/*` → service.
- **Docker client:** browser → its local hub `/submission/*` → `SUBMISSION_HOST_PUBLIC`
  (the ngrok gateway URL, or `-L 9024:localhost:9024` over SSH).

Names resolve server-side from `name_map.json`.
