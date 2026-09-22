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

`DATASET_HOST_PATH` is the folder that **contains** `0/` **and** `1/` — not
`0/`, not `0/frames`.

Batch 1 (AIC 2026) is now served too, so you also need its keyframes:

```
<DATASET_HOST_PATH>/1/frames/low_res_autoshot/Keyframes_N001/keyframes/N001_V001/00000.avif
```

Grab them from the packaged tarball (`1_frames_low_res_autoshot.tar`, ~3 GB, on
the server's F:) and unpack under `<DATASET_HOST_PATH>/1/frames/`. Without it,
every `N` (traffic) / `S` (cycling) result shows a broken thumbnail — those are
now ~40% of an unfiltered grid.

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
  You now need batch 0 **and** batch 1 (`N`/`S`) keyframes locally; without the
  batch-1 set every traffic/cycling result is a broken thumbnail. Or scope
  searches with the UI **Content** checkboxes to the subsets you do have.
- **Rebuild the SPA** (`bun run build`) after pulling frontend changes — nginx
  serves `dist/`, so source edits alone change nothing.

## DRES submission (works on the client too)

The 1-button submit works on this local build: the client runs the **hub**, which
now hosts the `/submission` router (nginx proxies `/submission/` → hub, added to
`nginx/client.conf`). The exact DRES name comes from `name_map.json`, which is
**bundled in the repo** (`src/utils/name_map.json`, rides the `./src` mount), so
you do NOT need the dataset for names to resolve (`N001-V001`, `S01-V001`,
`M05_V001`, `L21_V001`, no extension).

You only need to set the team's DRES credentials in `.env.client`:
```ini
SUBMIT_BASE_URL=https://eventretrieval.oj.io.vn   # or the URL BTC gives on the day
SUBMIT_USERNAME=<team username>
SUBMIT_PASSWORD=<team password>
```
Login is lazy: the header "DRES" badge shows connection; "connect" retries. Each
client logs in independently (its own session); the dup-submit guard is per client.
Rebuild `dist/` after pulling UI changes (`cd src/ui/aic && bun run build`).
