#!/usr/bin/env bash
# =============================================================================
# start_services.sh — Khởi động siglip_alpha (AIC 2026) trên GPU 3 + hub UI
#
# Cách dùng:
#   ./start_services.sh     # siglip_alpha -> GPU 3 (9029) + hub frontend (9021)
#
# Lưu ý:
#   - Chạy THỦ CÔNG bằng uvicorn ngoài Docker (container Docker GPU bị crash
#     vì "No CUDA GPUs are available" / OOM — xem Agent.md mục 6.1).
#   - Qdrant collection SIGLIP_V2 đã có 177.321 điểm => KHÔNG cần setup lại.
#   - Cần Qdrant (port 6333) + media_server (9027) chạy sẵn trong Docker.
#   - hub (9021) là frontend UI, proxy tới siglip_alpha qua SIGLIP_V2_HOST_PUBLIC
#     trong .env (đang là http://localhost:9029).
# =============================================================================

set -euo pipefail

cd "$(dirname "$0")"
export PYTHONPATH=.

# ---------------------------------------------------------------------------
# Python: dùng conda env "random42_aic" một cách TƯỜNG MINH (không phụ thuộc
# env đang active trong terminal — nếu .venv đang active sẽ shadow python).
# ---------------------------------------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-/workspace/tuannt/miniconda3/envs/random42_aic/bin/python}"

# ---------------------------------------------------------------------------
# Kích hoạt conda env "random42_aic" (đã cài đủ torch/transformers/qdrant)
# ---------------------------------------------------------------------------
if [ -f /workspace/tuannt/miniconda3/etc/profile.d/conda.sh ]; then
  source /workspace/tuannt/miniconda3/etc/profile.d/conda.sh
  conda activate random42_aic
fi

# ---------------------------------------------------------------------------
# Kiểm tra Qdrant đã chạy chưa (port 6333 = siglip_alpha)
# ---------------------------------------------------------------------------
if ! curl -s --max-time 3 http://localhost:6333/collections >/dev/null 2>&1; then
  echo "[ERROR] Qdrant chưa chạy. Chạy lệnh sau rồi thử lại:"
  echo "  docker compose -f docker-compose-server.yml up -d qdrant-siglip-alpha media_server"
  exit 1
fi
echo "[OK] Qdrant đang chạy."

mkdir -p logs

# ---------------------------------------------------------------------------
# Giữ container Docker siglip_alpha đã tắt (tránh restart đè lên port 9029)
# ---------------------------------------------------------------------------
docker compose -f docker-compose-server.yml stop siglip_alpha 2>/dev/null || true

# ---------------------------------------------------------------------------
# 1) siglip_alpha — port 9029, chạy trên GPU 3
#    Load SigLIP2 Giant + ViLitTextEncoder (ViCLIP-OT tiếng Việt)
# ---------------------------------------------------------------------------
if curl -s --max-time 3 http://localhost:9029/siglip_alpha/ping >/dev/null 2>&1; then
  echo "[OK] siglip_alpha đã chạy sẵn trên port 9029."
else
  echo "[START] siglip_alpha -> GPU 3, port 9029"
  CUDA_VISIBLE_DEVICES=3 SERVICE=siglip_alpha \
    nohup $PYTHON_BIN -m uvicorn src.main:app --host 0.0.0.0 --port 9029 \
    > logs/siglip_alpha.log 2>&1 &
  echo "       PID: $!  (log: logs/siglip_alpha.log)"
fi

# ---------------------------------------------------------------------------
# 1b) fusion_model — port 9032, chạy trên GPU 0
#     SigLIP2 + jina-clip-v2 + learned gating MLP trong 1 process
#     (FUSION_MODEL_CUDA_VISIBLE_DEVICES trong .env, mặc định 0)
# ---------------------------------------------------------------------------
if curl -s --max-time 3 http://localhost:9032/fusion_model/ping >/dev/null 2>&1; then
  echo "[OK] fusion_model đã chạy sẵn trên port 9032."
else
  echo "[START] fusion_model -> GPU ${FUSION_MODEL_CUDA_VISIBLE_DEVICES:-0}, port 9032"
  SERVICE=fusion_model     nohup $PYTHON_BIN -m uvicorn src.main:app --host 0.0.0.0 --port 9032     > logs/fusion_model.log 2>&1 &
  echo "       PID: $!  (log: logs/fusion_model.log)"
fi

# ---------------------------------------------------------------------------
# 2) hub — port 9021 (FRONTEND UI, chạy CPU, không cần GPU)
# ---------------------------------------------------------------------------
if curl -s --max-time 3 http://localhost:9021/hub/ping >/dev/null 2>&1; then
  echo "[OK] hub đã chạy sẵn trên port 9021."
else
  echo "[START] hub -> port 9021 (frontend UI)"
  SERVICE=hub \
    nohup $PYTHON_BIN -m uvicorn src.main:app --host 0.0.0.0 --port 9021 \
    > logs/hub.log 2>&1 &
  echo "       PID: $!  (log: logs/hub.log)"
fi

echo ""
echo "======================================================================"
echo " ✅ Đã khởi động xong!"
echo "    - siglip_alpha: GPU 3, port 9029"
echo "    - fusion_model: port 9032 (2 experts + gating)"
echo "    - hub UI:       port 9021"
echo ""
echo " 🔗 Mở frontend tại: http://localhost:9021"
echo ""
echo " Kiểm tra nhanh:"
echo "   curl http://localhost:9021/hub/ping"
echo "   curl -X POST http://localhost:9032/fusion_model/text_search \\"
echo "        -H 'Content-Type: application/json' -d '{\"text\": \"mèo\", \"k\": 20}'"
echo "======================================================================"
