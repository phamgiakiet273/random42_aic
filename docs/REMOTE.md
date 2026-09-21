# Remote access over ngrok — server side and client side

How to expose this machine's stack to teammates, and how their machines connect.
Supersedes the tunnel section of `docs/LOCAL.md`, which assumed one tunnel per
service. Same shape as the legacy `SIU_Pumpking/README_LOCAL.md`, but the
services now sit behind a single gateway.

```
THIS MACHINE (server)                        TEAMMATE'S MACHINE (client)
                                               browser → web :9080 ─┬─ /            SPA
  gateway :9090 ◀──── ngrok ────── https ──────────────────────────┤
    ├─ /siglip_alpha/ → siglip_alpha :9029        hub container ───┘─ /hub
    ├─ /util/         → util         :9025
    ├─ /result_manager/ → result_mgr :9022        /media/frames ─ local disk, or
    └─ /media/        → media nginx  :9027                        proxied back here
```

## You publish exactly ONE port

Every service already mounts its routes under a distinct prefix
(`/siglip_alpha/`, `/util/`, `/result_manager/`, `/media/`), so one nginx can
front all of them with no path rewriting, and the hub's own
`f"{host_public}/util/translate"` URLs still land correctly. That matters
because ngrok's free tier allows a single agent tunnel.

| Port | Service | Publish? |
|---|---|---|
| **9090** | **gateway (nginx)** | **YES — the only one** |
| 9029 | siglip_alpha | no — reached via `/siglip_alpha/` |
| 9025 | util | no — via `/util/` |
| 9022 | result_manager | no — via `/result_manager/` |
| 9027 | media nginx | no — via `/media/` |
| 9021 | hub | no — each client runs its own |
| 10000 | frontend (vite) | no — this machine's own UI |
| 6333 / 6335 | Qdrant | **never** — no auth, full read/write on the index |

## Server side

```bash
cd /mnt/e/workspace/AIC_2026/aic2026
./stack.sh start --remote                      # stack + gateway on :9090
ngrok http --url=<your-reserved-domain> 9090
```

Verify the tunnel before telling anyone it is up:

```bash
curl https://<domain>/gateway/ping              # -> gateway ok
curl https://<domain>/siglip_alpha/ping         # -> {"status":200,...}
curl https://<domain>/util/ping
curl https://<domain>/result_manager/ping
curl -I https://<domain>/media/frames/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif
```

**Use a reserved domain.** A random free ngrok endpoint serves a browser
interstitial page instead of the file, which breaks video and thumbnails. If you
must use an ephemeral URL, add `--request-header-add "ngrok-skip-browser-warning: 1"`
on the client side — but reserved is the supported path.

`setup_database` is blocked at the gateway with a 403: it re-ingests and would
destroy `PUMPKING_SIGLIP_V2`, and the gateway is on the public internet. It stays
reachable on `localhost:9029` for whoever is at the machine.

Consider `ngrok http --basic-auth 'team:<password>' --url=<domain> 9090` — the
gateway has no auth of its own.

## Yes — video goes over the same single port

Worth spelling out, because it is the part that looks like it needs its own
tunnel. It does not.

The browser asks the **client's** nginx for `/media/clips/...`; that block
proxies to `${VIDEO_UPSTREAM}`, which is the same `https://<domain>`; the
gateway routes `/media/` to the media nginx, which serves the file off F:.
Images are local to the client, video is not — and both ride the one tunnel.

Measured end to end through `client -> gateway -> media_server`:

| check | result |
|---|---|
| `Content-Length` | `130322332` — exactly the file size on disk |
| md5 of bytes `1000000-1000099` vs reading the file directly | **identical** |
| mid-file seek (`Range: bytes=50000000-...`) | `206 Partial Content` |
| `Accept-Ranges` | `bytes` |

So seeking works and no byte is mangled in the two proxy hops. The legacy
`SIU_Pumpking` setup needed a separate video tunnel only because the client's
own nginx already occupied port 9027; here the client serves on 9080 and the
gateway multiplexes `/media/` alongside the API prefixes.

One thing that *is* worth watching: each nginx hop used to re-add
`Accept-Ranges` and CORS headers, so clients saw `Accept-Ranges` four times.
The proxies now pass the origin's headers through instead of restating them.
If you add a hop, do the same.

## The server's own UI (port 10000) is not part of the tunnel

`:10000` is the vite dev server for whoever sits at this machine. It proxies
`/hub`, `/result_manager` and `/media` itself, so the server operator needs only
that one port — but it is *not* what remote clients use; they run their own hub
and UI.

If you ever do expose it, note `allowedHosts` in `src/ui/aic/vite.config.js`:
vite returns `403 Blocked request` for any `Host` not on the list. The migrated
config listed only the old machine's names, so this machine 403'd on its own
hostname until it was added. It is now env-overridable:

```ini
VITE_ALLOWED_HOSTS=host-a,host-b,.example.ts.net,my-ngrok-domain
```

## Client side

Both cases need the SPA built once, and the four upstreams pointed at the same
domain:

```bash
cd src/ui/aic && bun install && bun run build   # produces dist/, served by nginx
```

```ini
# .env.client -- identical in both cases
SIGLIP_V2_HOST_PUBLIC=https://<domain>
UTIL_HOST_PUBLIC=https://<domain>
VIDEO_UPSTREAM=https://<domain>
RESULT_MANAGER_UPSTREAM=https://<domain>

CLIENT_PORT=9080
HOST_UID=1000        # id -u   (0 on a root-only WSL setup)
HOST_GID=1000        # id -g
LOG_HOST_PATH=./logs
```

All four are the **same** domain — the prefixes keep them apart.

### Case A — the client HAS the low-res keyframes

The normal setup: thumbnails come off their own disk, only search JSON and the
clicked clip cross the tunnel.

```ini
DATASET_HOST_PATH=/path/that/contains/0     # NOT .../0 and NOT .../0/frames
# CLIENT_NGINX_CONF unset -> nginx/client.conf (frames served locally)
```

```bash
docker compose -f docker-compose-client.yml --env-file .env.client up -d --build
```

Their tree must look like:

```
<DATASET_HOST_PATH>/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif
```

They do **not** need `0/fps/`, `0/shot/`, `0/speech_to_text2/`, `0/features/` or
`utils/` — the hub never opens them; this machine reads them and returns results.

### Case B — the client has NO local images

Everything, thumbnails included, comes through the tunnel. Works fine, but the
result grid is much slower and leans on HTTP caching.

```ini
CLIENT_NGINX_CONF=./nginx/client-remote-frames.conf
FRAMES_UPSTREAM=https://<domain>
DATASET_HOST_PATH=./logs      # dummy: nothing is served from it in this mode,
                              # but compose still needs an existing path to mount
```

```bash
docker compose -f docker-compose-client.yml --env-file .env.client up -d --build
```

`client-remote-frames.conf` is `client.conf` with the `/media/frames/` block
changed from a local `alias` to a proxy, plus a 30-day immutable cache header so
each frame crosses the tunnel only once.

### Verify (either case)

```bash
curl http://localhost:9080/hub/ping
curl http://localhost:9080/hub/media_config
curl -I http://localhost:9080/media/frames/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif
curl -I -H 'Range: bytes=0-1023' http://localhost:9080/media/clips/0/videos/Videos_L21/video/L21_V001.mp4
```

Then open <http://localhost:9080>. Expect `200` on the frame and `206` on the
ranged clip.

## Gotchas

- **`Host` header.** Both client configs send `Host $proxy_host` with
  `proxy_ssl_server_name on` for server-bound blocks. ngrok routes by Host/SNI
  and returns its own error page if it receives `localhost:9080`. The stock
  upstream config used `Host $host`, which works for SSH tunnels and fails for
  ngrok — this was changed here.
- **Keep `NGINX_IMAGE_HOST` / `NGINX_VIDEO_HOST` relative** (`/media/frames`,
  `/media/clips`). Absolute values get baked into URLs the browser fetches and
  only work when the browser runs on the server.
- **The `/media/` prefix is deliberate** — ad-blocker lists block generic
  `/img/` and `/video/` paths.
- **`.env` is read at container creation.** After editing: `up -d --force-recreate`,
  not `restart`.
- **Rebuild the SPA** (`bun run build`) after pulling frontend changes; nginx
  serves `dist/`, so source edits alone change nothing.
- **Batch 1 is not on this server.** The index still contains its points, so
  clients should send
  `video_filter=L21,L22,L23,L24,L25,L26,L27,L28,L29,L30`
  or roughly two thirds of every result grid will be broken thumbnails. See
  `RANDOM42_OPS.md` §6.
- **If you prefer one tunnel per service** (closer to the old README), skip the
  gateway and expose 9029 / 9025 / 9022 / 9027 separately, then set each
  `*_HOST_PUBLIC` / `*_UPSTREAM` to its own domain. It needs four reserved
  domains and a paid ngrok plan for concurrent agents.
