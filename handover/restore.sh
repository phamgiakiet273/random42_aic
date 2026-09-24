#!/usr/bin/env bash
# Restore the Random42 AIC stack on a NEW machine from the H: drive. Read
# docs/RESTORE.md first (it is also at <drive>/random42/migration/RESTORE.md).
#
#   bash <drive>/random42/migration/restore.sh <local-ext4-dir>
#   e.g. bash /mnt/d/random42/migration/restore.sh ~/random42
#
# What it does (idempotent: re-running skips what is already there):
#   1. copies the Qdrant indexes + model cache to <local-ext4-dir>  (never run
#      them off the drive: over WSL's 9p mount the model takes ~2 h to load)
#   2. verifies file counts against MANIFEST.txt
#   3. loads the Docker images and restores the UI's node_modules volume
#   4. copies the repo to <local-ext4-dir>/aic2026 and writes the machine-specific
#      .env values (paths, uid/gid, hostname) -- nothing to edit by hand
# The dataset and the videos STAY on the drive (served read-only from there).
# Then:  cd <local-ext4-dir>/aic2026 && ./stack.sh start      (--remote for teammates)
set -euo pipefail
SUDO=$([ "$(id -u)" = 0 ] || echo sudo)   # Qdrant files are root-owned; root needs no sudo
MIG="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"          # <drive>/random42/migration
DRIVE_R42="$(dirname "$MIG")"                                 # <drive>/random42
LOCAL="$(mkdir -p "${1:?usage: restore.sh <local-ext4-dir>}" && cd "$1" && pwd)"
DATA="$DRIVE_R42/data/aic_2025"; REPO_SRC="$DRIVE_R42/workspace/aic2026"; REPO="$LOCAL/aic2026"
say(){ printf '\n==> %s\n' "$*"; }

case "$(stat -f -c %T "$LOCAL")" in
  ext2/ext3|ext4|xfs|btrfs) ;;
  *) echo "!! $LOCAL is on '$(stat -f -c %T "$LOCAL")' -- pick a local Linux disk (e.g. ~ in WSL), not /mnt/c or the drive"; exit 1 ;;
esac

say "1/4 indexes + model cache -> $LOCAL"
for d in qdrant_storage qdrant_jina_storage hf_cache; do
  if [ -d "$LOCAL/$d" ]; then echo "    $d already there"; continue; fi
  echo "    $d"; $SUDO cp -a "$MIG/$d" "$LOCAL/"   # sudo: some Qdrant files are root-owned
done
sync

say "2/4 verify against MANIFEST.txt"
fail=0
while read -r name files _; do
  [ -d "$LOCAL/$name" ] || continue
  want=${files#files=}; got=$($SUDO find "$LOCAL/$name" -type f | wc -l)
  printf '    %-22s expected %-7s got %-7s ' "$name" "$want" "$got"
  [ "$want" = "$got" ] && echo ok || { echo MISMATCH; fail=1; }
done < <(grep -E '^(qdrant_storage|qdrant_jina_storage|hf_cache) ' "$MIG/MANIFEST.txt")
[ "$fail" = 0 ] || { echo "!! file counts differ -- do NOT start the stack; re-run this script"; exit 1; }

say "3/4 docker images + UI node_modules volume"
for t in support-images random42-aic; do docker load -i "$MIG/docker-images/$t.tar"; done
if ! docker volume inspect aic2026_aic_node_modules >/dev/null 2>&1; then
  docker volume create aic2026_aic_node_modules >/dev/null
  docker run --rm -v aic2026_aic_node_modules:/nm -v "$MIG/docker-images":/in:ro alpine \
    tar -xf /in/node_modules.tar -C /nm
  echo "    node_modules volume restored"
fi

say "4/4 repo -> $REPO, machine-specific .env"
if [ ! -d "$REPO" ]; then
  mkdir -p "$REPO"
  tar -C "$REPO_SRC" --exclude=./logs --exclude=./.cache --exclude=./src/ui/aic/node_modules -cf - . | tar -C "$REPO" -xf -
fi
mkdir -p "$REPO/logs" "$REPO/.cache/qdrant_prep"
setenv(){ grep -q "^$1=" "$REPO/.env" && sed -i "s|^$1=.*|$1=$2|" "$REPO/.env" || echo "$1=$2" >> "$REPO/.env"; }
setenv QDRANT_STORAGE_HOST_PATH      "$LOCAL/qdrant_storage"
setenv QDRANT_JINA_STORAGE_HOST_PATH "$LOCAL/qdrant_jina_storage"
setenv MODEL_CACHE_HOST_PATH         "$LOCAL/hf_cache"
setenv DATASET_HOST_PATH             "$DATA"
setenv VIDEO_HOST_PATH               "$DATA/original"
setenv NAME_MAP_META_HOST_PATH       "$DATA/1/_meta"
setenv LOG_HOST_PATH                 "$REPO/logs"
setenv HOST_UID                      "$(id -u)"
setenv HOST_GID                      "$(id -g)"
setenv VITE_ALLOWED_HOSTS            "localhost,$(hostname),.ts.net"
grep -E '^(QDRANT_STORAGE|QDRANT_JINA_STORAGE|MODEL_CACHE|DATASET|VIDEO|LOG)_?[A-Z_]*HOST_PATH=|^HOST_(UID|GID)=' "$REPO/.env" | sed 's/^/    /'

cat <<NEXT

==> done. Start it:
    cd "$REPO" && ./stack.sh start            # UI on http://localhost:10000
    cd "$REPO" && ./stack.sh start --remote   # + public URL for teammates (ngrok)
    python3 tools/ui_check.py                  # optional: drive the UI in a browser (needs Playwright)
NEXT
