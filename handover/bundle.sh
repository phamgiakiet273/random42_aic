#!/usr/bin/env bash
# Refresh the H: drive so another machine can run this exact stack with no
# preprocessing (the reverse of the 2026-09-21 migration). Run on the SERVER.
# The other side: docs/RESTORE.md + handover/restore.sh.
#
#   bash handover/bundle.sh data    # dataset + videos (additive; run any time)
#   bash handover/bundle.sh state   # Qdrant index + images + node_modules + repo + MANIFEST
#                                   # (live: no service is stopped)
#
# Bulk copies go through Windows robocopy/tar (native NTFS writes); WSL's 9p is
# far slower for small files. Never walks H: (slow USB): counts come from the source.
set -u
SUDO=$([ "$(id -u)" = 0 ] || echo sudo)   # Qdrant files are root-owned; root needs no sudo
A=/mnt/e/workspace/AIC_2026/aic2026; D=/mnt/e/workspace/AIC_2026/data
H=/mnt/h/random42; HW='H:\random42'; MIG=$H/migration; W=/mnt/c/Windows/System32
LOGDIR=/mnt/e/workspace/AIC_2026/handover; L=$LOGDIR/bundle.log; mkdir -p "$LOGDIR"
log(){ echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$L"; }
rc(){ "$W/robocopy.exe" "$@" /R:2 /W:5 /NP /NDL /NJH >> "$LOGDIR/robocopy.log" 2>&1; c=$?
      [ $c -lt 8 ] && log "   robocopy ok ($c)" || { log "   !! robocopy FAILED ($c)"; return 1; }; }
envval(){ sed -n "s/^$1=//p" "$A/.env" | tail -1; }
cd /

stage_data() {
  log "== data: batch-1 dataset, processed videos, utils (additive)"
  [ -d "$H/data/aic_2025/1/frames/low_res_autoshot" ] \
    || "$W/tar.exe" -xf 'E:\workspace\AIC_2026\data\1.tar' -C "$HW\\data\\aic_2025" >> "$LOGDIR/tar.log" 2>&1
  rc 'F:\workspace\aic_2026\original\1\videos' "$HW\\data\\aic_2025\\original\\1\\videos" 'N*_V*.mp4' /S
  SD=$H/data/aic_2025/original/1/videos/Videos_S01/video   # S01: byte-identical, so link our names
  for f in "$SD"/S01-V*.mp4; do t="$SD/$(basename "$f" | sed 's/^S01-V/S01_V/')"; [ -e "$t" ] || ln "$f" "$t"; done
  for d in shot speech_to_text features; do rc "E:\\workspace\\AIC_2026\\data\\1\\$d" "$HW\\data\\aic_2025\\1\\$d" /S; done
  rc 'E:\workspace\AIC_2026\data\utils' "$HW\\data\\aic_2025\\utils" /S
  log "== data done"
}

stage_state() {
  log "== state"
  # name maps (the region vectors are NOT bundled: their collection is in the index)
  rc 'F:\workspace\aic_2026\1\_meta' "$HW\\data\\aic_2025\\1\\_meta" /S

  # Qdrant index, copied LIVE (search keeps running). Qdrant only rewrites files
  # on ingest or when its optimizer merges/indexes segments, so: wait until every
  # collection is green with the optimizer idle, copy, and confirm the source did
  # not change during the copy; if it did, re-sync just the changed files.
  SRC=$(envval QDRANT_STORAGE_HOST_PATH); DST="$MIG/qdrant_storage.new"
  idle(){ curl -s localhost:6333/collections | jq -r '.result.collections[].name' | while read -r c; do
            curl -s "localhost:6333/collections/$c" | jq -r '"\(.result.status) \(.result.optimizer_status)"'; done | grep -vc '^green ok$'; }
  until [ "$(idle)" = 0 ]; do log "   waiting for Qdrant to finish optimizing"; sleep 60; done
  sig(){ $SUDO find "$SRC" -type f -printf '%P %s %T@\n' | sort | md5sum; }
  ok=0
  for pass in 1 2 3; do
    before=$(sig); $SUDO rsync -a --delete "$SRC/" "$DST/"; after=$(sig)
    [ "$before" = "$after" ] && { ok=1; break; }
    log "   index changed during pass $pass -- re-syncing the changed files"
  done
  if [ "$ok" = 1 ]; then
    [ -d "$MIG/qdrant_storage" ] && $SUDO mv "$MIG/qdrant_storage" "$MIG/qdrant_storage.old"
    $SUDO mv "$DST" "$MIG/qdrant_storage" && $SUDO rm -rf "$MIG/qdrant_storage.old"
    log "   qdrant_storage copied (consistent, no downtime)"
  else log "   !! index kept changing -- drive keeps its previous index; re-run 'state' later"; fi

  # model cache: add what's new since the last bundle (e.g. the s2t models), keep the rest
  $SUDO cp -a -n "$(envval MODEL_CACHE_HOST_PATH)/." "$MIG/hf_cache/" && log "   hf_cache synced"

  log "   docker images (support + app) and the UI node_modules volume"
  docker save -o "$MIG/docker-images/support-images.tar.new" \
    qdrant/qdrant:v1.15.5-gpu-nvidia qdrant/qdrant:v1.19.0 nginx:alpine oven/bun:1 alpine:latest ngrok/ngrok:latest \
    && mv "$MIG/docker-images/support-images.tar.new" "$MIG/docker-images/support-images.tar"
  # the app image only changes on a rebuild (code is bind-mounted): re-save only if it
  # was built after the tar on the drive was written
  built=$(date -d "$(docker image inspect random42-aic:latest -f '{{.Created}}')" +%s)
  saved=$(stat -c %Y "$MIG/docker-images/random42-aic.tar" 2>/dev/null || echo 0)
  if [ "$built" -gt "$saved" ]; then docker save -o "$MIG/docker-images/random42-aic.tar.new" random42-aic:latest \
    && mv "$MIG/docker-images/random42-aic.tar.new" "$MIG/docker-images/random42-aic.tar"; else log "   app image unchanged, tar kept"; fi
  docker run --rm -v aic2026_aic_node_modules:/nm:ro -v "$MIG/docker-images":/out alpine tar -cf /out/node_modules.tar -C /nm .

  log "   repo: $H/workspace/aic2026 -> this checkout's HEAD + .env"
  git -c safe.directory='*' -C "$H/workspace/aic2026" fetch -q "$A" "$(git -C "$A" branch --show-current)" \
    && git -c safe.directory='*' -C "$H/workspace/aic2026" checkout -q -f -B handover FETCH_HEAD
  cp "$A/.env" "$H/workspace/aic2026/.env"          # restore.sh rewrites the machine-specific lines
  cp "$A/docs/RESTORE.md" "$A/handover/restore.sh" "$MIG/"

  log "   MANIFEST"
  { echo "# Random42 handover bundle  ($(date -u +%FT%TZ))  commit $(git -C "$A" rev-parse --short HEAD)"
    echo "# restore.sh checks these file counts after copying"
    for d in qdrant_storage qdrant_jina_storage hf_cache; do
      case $d in qdrant_storage) s=$(envval QDRANT_STORAGE_HOST_PATH);; qdrant_jina_storage) s=$(envval QDRANT_JINA_STORAGE_HOST_PATH);; hf_cache) s=$(envval MODEL_CACHE_HOST_PATH);; esac
      echo "$d files=$($SUDO find "$s" -type f | wc -l) size=$($SUDO du -sh "$s" | cut -f1)"
    done
    echo "points PUMPKING_SIGLIP_V2=$(curl -s localhost:6333/collections/PUMPKING_SIGLIP_V2 | jq -r .result.points_count) PUMPKING_SIGLIP_REGIONS=$(curl -s localhost:6333/collections/PUMPKING_SIGLIP_REGIONS | jq -r '.result.points_count // "absent"')"
    ls -la "$MIG/docker-images" | awk 'NR>3{printf "%s size=%.1fG\n", $9, $5/1e9}'
  } > "$MIG/MANIFEST.txt"
  cat "$MIG/MANIFEST.txt" | tee -a "$L"
  log "== state done"
}

case "${1:-}" in
  data) stage_data ;;
  state) stage_state ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
