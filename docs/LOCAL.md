# Client runbook — running the UI on your own machine

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

`DATASET_HOST_PATH` is the folder that **contains** `0/` — not `0/`, not
`0/frames`.

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

## 2. Open the tunnels

Three things are tunnelled: siglip (9029), util (9025), and the server's media
nginx for **video** (its 9027 → your 9028).

**SSH** (defaults in `.env.client` assume this):

```bash
ssh -N \
  -L 9029:localhost:9029 \
  -L 9025:localhost:9025 \
  -L 9028:localhost:9027 \
  <user>@<server-host>
```

**ngrok** — on the *server*, then point the matching vars in `.env.client` at
the reserved domains:

```bash
ngrok http --url=<siglip-domain> 9029
ngrok http --url=<util-domain>   9025
ngrok http --url=<media-domain>  9027
```

```ini
SIGLIP_V2_HOST_PUBLIC=https://<siglip-domain>
UTIL_HOST_PUBLIC=https://<util-domain>
VIDEO_UPSTREAM=https://<media-domain>
```

A reserved domain matters for video: a free ngrok endpoint serves its
interstitial page instead of the file.

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
curl -I -r 0-100 http://localhost:9080/media/clips/0/videos/Videos_L21/media/clips/L21_V001.mp4
curl http://localhost:9029/siglip_alpha/ping           # tunnel
curl http://localhost:9025/util/ping                   # tunnel
```

Substitute a frame that actually exists.

## Differences from the server stack

| | Server | Client |
|---|---|---|
| Compose file | `docker-compose-server.yml` + `-local.yml` | `docker-compose-client.yml` |
| Services | hub, siglip, util, result_manager, media_server | hub, web (nginx) |
| GPU | required for siglip | none |
| siglip / util | local containers | tunnel |
| Frames | server dataset | **your disk** |
| Video | local media nginx | tunnel |
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
  With only batch 0 locally, batch-1 (`K*`) results show broken thumbnails.
- **Rebuild the SPA** (`bun run build`) after pulling frontend changes — nginx
  serves `dist/`, so source edits alone change nothing.
