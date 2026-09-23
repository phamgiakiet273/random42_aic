#!/usr/bin/env bash
# Random42 AIC -- run the whole stack on this machine.
#
#   ./stack.sh start          server + hub + frontend, with preflight + verify
#   ./stack.sh start --remote ... and the gateway on :9090 + its ngrok tunnel
#                             (https://$NGROK_DOMAIN; rebuilds the UI it serves)
#   ./stack.sh ui-build       rebuild src/ui/aic/dist (what the gateway serves teammates)
#   ./stack.sh stop
#   ./stack.sh restart        force-recreate (use after editing .env)
#   ./stack.sh status
#   ./stack.sh verify
#   ./stack.sh logs [service]
#
# Why preflight: E: and F: are 9p drvfs mounts. After a host reboot Docker can
# start containers before those mounts attach, and the services then come up
# against empty directories -- Qdrant logs "tmpfs is memory-based" while the
# real index sits untouched on disk. Cheaper to refuse to start than to debug.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"

# One logical project across three compose files: each call would otherwise
# warn about the others' containers as orphans. Never "fix" that with
# --remove-orphans -- it would delete the rest of the stack.
export COMPOSE_IGNORE_ORPHANS=true

SERVER=docker-compose-server.yml
LOCAL=docker-compose-local.yml
GATEWAY=docker-compose-gateway.yml

# The services the search stack actually needs. siglip_beta / metaclip / jina /
# rerank are defined in the compose file but are not part of this deployment --
# their indexes were never migrated. `submission` is the team's ONE DRES client
# (every hub and the gateway forward /submission/* to it); CPU-only, no GPU.
SERVICES=(qdrant-siglip-alpha media_server util result_manager submission siglip_alpha)

EXT4=/srv/random42
DATA=/mnt/e/workspace/AIC_2026/data
VIDEO=/mnt/f/workspace/aic_2026/original

RED=$'\e[31m'; GRN=$'\e[32m'; YEL=$'\e[33m'; RST=$'\e[0m'
ok()   { printf '    %s✓%s %s\n' "$GRN" "$RST" "$*"; }
bad()  { printf '    %s✗%s %s\n' "$RED" "$RST" "$*"; }
warn() { printf '    %s!%s %s\n' "$YEL" "$RST" "$*"; }
head_() { printf '\n== %s ==\n' "$*"; }

preflight() {
  head_ "preflight"
  local fail=0
  check() { # check <label> <path>
    if [ -e "$2" ]; then ok "$1"; else bad "$1  -- missing: $2"; fail=1; fi
  }
  check "qdrant index (ext4)"  "$EXT4/qdrant_storage/collections/PUMPKING_SIGLIP_V2"
  check "jina index (ext4)"    "$EXT4/qdrant_jina_storage/collections/EXPERT_B_V1"
  check "model cache (ext4)"   "$EXT4/hf_cache/hub"
  check "dataset batch 0 (E:)" "$DATA/0/frames/low_res_autoshot"
  check "source videos (F:)"   "$VIDEO/0/videos/Videos_L21/video"
  check "repo logs dir"        "./logs"
  if [ "$fail" = 1 ]; then
    printf '\n%sRefusing to start.%s If the paths above look right but are reported\n' "$RED" "$RST"
    echo "missing, the 9p mounts probably did not attach after a reboot. Check with:"
    echo "    ls /mnt/e /mnt/f"
    echo "and if they are empty, restart WSL from PowerShell: wsl --shutdown"
    return 1
  fi
  return 0
}

wait_http() { # wait_http <label> <url> <timeout-seconds> [expected-code]
  local label=$1 url=$2 limit=$3 want=${4:-200} t0 code
  t0=$(date +%s)
  while :; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null)
    [ "$code" = "$want" ] && { ok "$label ($(( $(date +%s) - t0 ))s)"; return 0; }
    [ $(( $(date +%s) - t0 )) -ge "$limit" ] && { bad "$label -- still $code after ${limit}s"; return 1; }
    sleep 2
  done
}

do_start() {
  local recreate=${1:-} remote=${2:-}
  preflight || return 1
  head_ "starting server stack"
  docker compose -f "$SERVER" up -d --no-deps $recreate "${SERVICES[@]}" 2>&1 | sed 's/^/    /'
  head_ "starting hub + frontend"
  docker compose -f "$LOCAL" up -d $recreate 2>&1 | sed 's/^/    /'
  if [ -n "$remote" ]; then
    do_ui_build
    head_ "starting remote gateway"
    docker compose -f "$GATEWAY" up -d $recreate 2>&1 | sed 's/^/    /'
  fi
  head_ "waiting for services"
  wait_http "qdrant siglip  :6333" http://localhost:6333/readyz 120
  wait_http "media server   :9027" "http://localhost:9027/media/frames/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif" 60
  wait_http "util           :9025" http://localhost:9025/util/ping 120
  wait_http "submission     :9024" http://localhost:9024/submission/ping 60
  wait_http "result_manager :9022" http://localhost:9022/result_manager/ping 120
  # siglip_alpha loads SigLIP2 from the model cache; ~2 min cold on ext4.
  wait_http "siglip_alpha   :9029" http://localhost:9029/siglip_alpha/ping 400
  wait_http "hub            :9021" http://localhost:9021/hub/ping 120
  wait_http "frontend      :10000" http://localhost:10000/ 180
  if [ -n "$remote" ]; then
    wait_http "gateway        :9090" http://localhost:9090/gateway/ping 60
    local dom; dom=$(sed -n 's/^NGROK_DOMAIN=//p' .env)
    wait_http "ngrok  https://$dom" "https://$dom/gateway/ping" 90
  fi
  do_verify
}

do_verify() {
  head_ "verify"
  local pts mnt
  # .expected_points is written by batch1/ingest.py (298,347 batch 0 + batch 1)
  local want; want=$(cat .expected_points 2>/dev/null || echo 526656)
  pts=$(curl -s --max-time 10 localhost:6333/collections/PUMPKING_SIGLIP_V2 | jq -r '.result.points_count' 2>/dev/null)
  if [ "$pts" = "$want" ]; then ok "PUMPKING_SIGLIP_V2: $pts points"
  else bad "PUMPKING_SIGLIP_V2: got '$pts', expected $want"; fi

  # The reboot trap: storage must be a real device, never tmpfs.
  mnt=$(docker exec aic2026-qdrant-siglip-alpha-1 df -h /qdrant/storage 2>/dev/null | awk 'NR==2{print $1}')
  case "$mnt" in
    /dev/*) ok "qdrant storage on $mnt (real device)" ;;
    "")     bad "could not inspect qdrant storage mount" ;;
    *)      bad "qdrant storage on '$mnt' -- index not attached. Run: ./stack.sh restart" ;;
  esac

  # End-to-end: a search whose frames actually resolve.
  local n
  n=$(curl -s --max-time 120 -X POST localhost:9021/hub/search \
        -F 'model=siglip_alpha' -F 'search_type=text' -F 'text=a busy street' -F 'k=5' \
        -F "video_filter=$(batch0_filter)" | jq -r '.data | length' 2>/dev/null)
  if [ "$n" = "5" ]; then ok "end-to-end search returned $n batch-0 results"
  else bad "end-to-end search returned '$n'"; fi

  # The UI is a vite dev server that proxies /hub, /result_manager and /media.
  # "GET / -> 200" only proves vite is up; check what the browser actually needs.
  local ui=http://localhost:10000 asset code
  asset=$(curl -s --max-time 15 "$ui/" | grep -oE 'src="[^"]+\.(js|jsx)"' | head -1 | sed 's/src="//;s/"//')
  if [ -n "$asset" ] && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$ui$asset")" = "200" ]; then
    ok "UI serves its JS entry ($asset)"
  else bad "UI JS entry did not load (asset='$asset')"; fi
  for probe in "/hub/ping:200" "/result_manager/ping:200" \
      "/media/frames/0/frames/low_res_autoshot/Keyframes_L21/keyframes/L21_V001/00000.avif:200"; do
    path=${probe%:*}; want=${probe##*:}
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$ui$path")
    [ "$code" = "$want" ] && ok "UI proxy ${path%%\?*}" || bad "UI proxy $path -> $code (want $want)"
  done
  # DRES submit path: UI -> /submission (vite) -> hub -> central submission service
  # -> DRES. Read-only (cached session/evaluation). status 200 = logged in (eval_id
  # null until BTC opens an evaluation); 400 = no SUBMIT_* creds in .env;
  # 503 = service unreachable.
  local sub
  sub=$(curl -s --max-time 30 "$ui/submission/get_session_and_eval")
  if [ "$(jq -r '.status' <<<"$sub" 2>/dev/null)" = "200" ]; then
    ok "DRES login via UI proxy ($(jq -r '.message' <<<"$sub"))"
  else bad "DRES submit path: $(jq -r '.message // empty' <<<"$sub" 2>/dev/null || head -c 120 <<<"$sub")"; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' -H 'Range: bytes=0-1023' --max-time 30 \
    "$ui/media/clips/0/videos/Videos_L21/video/L21_V001.mp4")
  [ "$code" = "206" ] && ok "UI proxy /media/clips (range -> 206, video seeking)" \
                      || bad "UI proxy /media/clips range -> $code (want 206)"
  # vite 403s on any Host not in allowedHosts; the migrated config listed only
  # the OLD machine's names, so the UI refused this machine's own hostname.
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -H "Host: $(hostname):10000" "$ui/")
  [ "$code" = "200" ] && ok "UI accepts this machine's hostname ($(hostname))" \
                      || bad "UI rejects Host $(hostname) -> $code; add it to VITE_ALLOWED_HOSTS"

  # batch 1: one traffic-CCTV and one broadcast query; every returned frame must resolve
  local q v kf code
  for q in "N:a bus turning at an intersection" "S:cyclists racing on a road"; do
    local pre=${q%%:*} text=${q#*:} bad_n=0 n=0
    while read -r v kf; do
      [ -z "$v" ] && continue; n=$((n+1))
      code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        "http://localhost:9027/media/frames/1/frames/low_res_autoshot/Keyframes_${v%%_*}/keyframes/$v/$kf.avif")
      [ "$code" = "200" ] || bad_n=$((bad_n+1))
    done < <(curl -s --max-time 120 -X POST localhost:9021/hub/search -F 'model=siglip_alpha' -F 'search_type=text' \
               -F "text=$text" -F 'k=10' -F "video_filter=$pre" | jq -r '.data[] | "\(.video_name|sub("\\.mp4$";"")) \(.keyframe_id)"' 2>/dev/null)
    if [ "$n" -gt 0 ] && [ "$bad_n" = 0 ]; then ok "batch 1 ($pre) search: $n hits, all frames resolve"
    else bad "batch 1 ($pre) search: $n hits, $bad_n frames did not resolve"; fi
  done

  printf '\n    UI: %shttp://localhost:10000%s\n' "$GRN" "$RST"
}

batch0_filter() { echo 'L21,L22,L23,L24,L25,L26,L27,L28,L29,L30'; }

do_status() {
  head_ "containers"
  # All three compose files share the `aic2026` project, so one ps lists them all.
  docker compose -f "$SERVER" ps --format '{{.Name}}\t{{.Status}}' 2>/dev/null \
    | sort -u | sed 's/^/    /'
  head_ "endpoints"
  for p in "6333:/readyz" "9021:/hub/ping" "9025:/util/ping" "9022:/result_manager/ping" "9024:/submission/ping" \
           "9029:/siglip_alpha/ping" "10000:/" "9090:/gateway/ping"; do
    port=${p%%:*}; path=${p#*:}
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$port$path" 2>/dev/null)
    [ "$code" = "200" ] && ok ":$port $path" || warn ":$port $path -> ${code:-down}"
  done
}

# The gateway serves the BUILT UI to remote teammates (vite dev over ngrok would be
# ~1.9k module requests per page load). Same bun image + node_modules volume as the
# frontend container; CPU only.
do_ui_build() {
  head_ "building the UI (src/ui/aic/dist)"
  docker run --rm -v "$PWD/src/ui/aic:/app" -v aic2026_aic_node_modules:/app/node_modules \
    -w /app oven/bun:1 bun run build 2>&1 | tail -3 | sed 's/^/    /'
}

do_stop() {
  head_ "stopping"
  docker compose -f "$GATEWAY" down 2>&1 | sed 's/^/    /'
  docker compose -f "$LOCAL"   down 2>&1 | sed 's/^/    /'
  docker compose -f "$SERVER"  down 2>&1 | sed 's/^/    /'
}

case "${1:-}" in
  start)   shift; r=""; [ "${1:-}" = "--remote" ] && r=yes; do_start "" "$r" ;;
  restart) shift; r=""; [ "${1:-}" = "--remote" ] && r=yes; do_start "--force-recreate" "$r" ;;
  stop)    do_stop ;;
  status)  do_status ;;
  verify)  do_verify ;;
  ui-build) do_ui_build ;;
  logs)    shift; docker compose -f "$SERVER" logs -f --tail=100 "$@" ;;
  *) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
