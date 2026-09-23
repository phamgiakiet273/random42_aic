# Teammate runbook

You run **one nginx**. It serves keyframes from your disk and forwards everything
else (UI, search, DRES submission, video) to the server's ngrok URL
`https://hallie-sabulous-nicholle.ngrok-free.dev`.
No bun, no conda, no UI build, no DRES login on your machine.

## 1. Keyframes

A folder that contains `0/` (batch 0, as before) and ideally `1/` (batch 1):

```bash
tar -xf 1_frames_low_res_autoshot.tar -C <that folder>   # server F:, ~3 GB; N + S only (no M)
```

Frames you don't have load from the server instead (slower), so a partial copy works.

## 2. Start (pick one)

**A. Docker: any OS, recommended on macOS / Windows**

```bash
AIC_FRAMES=/path/to/folder docker compose -f docker-compose-teammate.yml up -d
# PowerShell: $env:AIC_FRAMES="D:\aic_data"; docker compose -f docker-compose-teammate.yml up -d
# stop: docker rm -f aic2026-teammate-web-1
```

**B. Your own nginx: Linux bundled SIU_Pumpking binary, or `brew install nginx` on macOS**

```bash
cp nginx/teammate.conf.example nginx/teammate.conf   # edit the alias line -> /path/to/folder/
NGINX=nginx                                          # brew / distro
# NGINX="/path/SIU_Pumpking/nginx/sbin/nginx -p /path/SIU_Pumpking/nginx"   # bundled (Linux x86-64 only)
$NGINX -c "$PWD/nginx/teammate.conf" -t              # check
$NGINX -c "$PWD/nginx/teammate.conf"                 # start   (-s reload | -s stop)
```

## 3. Check

Open <http://localhost:9080>.

```bash
curl localhost:9080/hub/ping                          # 200
curl localhost:9080/submission/get_session_and_eval   # "status":200 = team DRES session up
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERR_NGROK_3200` / nothing loads | Server tunnel is down: ask the server owner to run `./stack.sh start --remote` |
| Thumbnails slow or broken | Wrong frames folder: it must CONTAIN `0/`. (B) keep the trailing `/` in `alias`; (A) check `AIC_FRAMES` |
| Bundled nginx won't start (macOS, missing `libpcre`) | Use A (Docker) or brew nginx |
| Port 9080 busy | Change `listen 9080` in the conf (and `ports` in the compose file) |
| DRES badge red | Hover it: "no ACTIVE evaluation" is normal until BTC opens one |
| ngrok down, SSH works | Set `$aic_server` to `http://127.0.0.1:9090` (Docker: `http://host.docker.internal:9090`) + `ssh -L 9090:localhost:9090 <server>` |

## Server side (whoever runs the server)

```bash
./stack.sh start --remote   # stack + gateway + ngrok tunnel; builds the UI the gateway serves
./stack.sh ui-build         # after pulling UI changes
```

One public URL = the gateway (`nginx/gateway.conf`): `/` UI, `/hub`, `/submission`,
`/media`, `/result_manager`, `/siglip_alpha`, `/util`. DRES goes through ONE central
submission service: see `docs/SUBMISSION_SPEC.md`.
