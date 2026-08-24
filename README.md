# Random42 — AIC 2026 Cross-Lingual Video Retrieval

Text-to-video retrieval cho AIC 2026: query ngắn (2-3 keyword, tiếng Việt/Anh) -> tìm video/keyframe từ corpus 873 videos / 177,321 frames.

- **Expert A**: SigLIP2 (google/siglip2-giant-opt-patch16-384) -> collection `SIGLIP_V2` (1536-d)
- **Expert B**: jina-clip-v2 (đa ngữ) -> collection `EXPERT_B_V1` (1024-d)
- **Fusion**: Context-rule gating (overlap-aware, KHÔNG cần train) — best hit@1 10%

> 📌 README này được viết để **Cline (AI agent) trên server mới đọc và setup tự động**.

---

## 1. KIẾN TRÚC + PORT

| Thành phần | Port | Cách chạy | GPU |
|---|---|---|---|
| Qdrant (`SIGLIP_V2` + `EXPERT_B_V1`) | 6333 | Docker | — |
| media_server (nginx thumbnails/video) | 9027 | Docker | — |
| siglip_alpha (SigLIP2-alone) | 9029 | uvicorn thủ công | GPU 3 (~8.5GB) |
| fusion_model (SigLIP2+jina+gating) | 9032 | uvicorn thủ công | GPU 0 (~11.5GB) |
| hub (UI) | 9021 | uvicorn thủ công | CPU |
| siglip_beta / metaclip (không bắt buộc) | 9030 / 9031 | uvicorn thủ công | GPU |

> ⚠️ Service GPU chạy **thủ công bằng uvicorn** (KHÔNG qua Docker) — Docker GPU từng crash trên máy này.

---

## 2. TRONG GIT vs KHÔNG TRONG GIT (bắt buộc đọc)

| Trong git (clone có) | KHÔNG trong git (phải chuẩn bị) |
|---|---|
| `src/`, `start_services.sh`, `docker-compose-server.yml` | `data/weights/` (models SigLIP2 ~7GB, jina ~4GB...) |
| `requirements.txt`, `requirements-local.txt` | Keyframes `data/0/frames/autoshot/` (~30GB) |
| `.env.example`, `.gitignore`, `README.md` | Qdrant storage `data/qdrant_storage/` (177k×2 points) |
| | `.env` (config thật) + `data/weights/gating_mlp_v3.pt` + `research/` |

**`data/` bị gitignore -> clone về chỉ có code.** Muốn chạy phải **chuyển data** (Lựa chọn A) hoặc **dựng lại** (Lựa chọn B, tốn nhiều giờ GPU). `research/` cũng không trong git — cần copy từ server cũ nếu cần script build/eval.

---

## 3. YÊU CẦU SERVER MỚI

- GPU NVIDIA (tối thiểu 2 GPU: fusion ~11.5GB, siglip ~8.5GB) + driver + CUDA
- Docker + NVIDIA Container Toolkit
- Miniconda (Python 3.11) — hoặc có thể dùng env Python khác nhưng phải có uvicorn/transformers/torch
- HF token (model gated) — xem `.env.example`
- Disk trống >= 60GB

---

## 4. PRE-FLIGHT CHECKS — AI phải kiểm tra TRƯỚC khi setup

> Chạy từng bước, đối chiếu "Kỳ vọng". Nếu lệch -> dừng, xử lý, rồi mới sang bước sau.

### 4.1 Môi trường
```bash
nvidia-smi                      # Kỳ vọng: thấy GPU + đủ VRAM
#   GPU fusion : cần ~11.5GB trống (FUSION_MODEL_CUDA_VISIBLE_DEVICES)
#   GPU siglip : cần ~8.5GB trống (SIGLIP_V2_CUDA_VISIBLE_DEVICES)
docker info >/dev/null 2>&1 && echo "docker OK" || echo "docker FAIL"
df -h /workspace                 # Kỳ vọng: >= 60GB trống
conda env list 2>/dev/null       # Kỳ vọng: có random42_aic (hoặc tạo mới)
```

### 4.2 DATA — nơi phải đặt (bắt buộc khớp)
```bash
cd <repo>/data
# Cấu trúc chuẩn:
#   data/weights/                 # models: siglip2-giant, jina-clip-v2(+impl), viclip-ot, vietnamese-sbert, gating_mlp_v3.pt
#   data/0/frames/autoshot/       # keyframes (~177k .jpg, 873 folders) — symlink tới KEYFRAMES_DIR
#   data/qdrant_storage/          # Qdrant data (có sẵn -> KHÔNG rebuild; thiếu -> dựng lại)
#   data/0/features/siglip2/      # siglip features .npy (bên kia đã có sẵn)
#   data/{index, s2t, map-keyframes} + train_anno.json + val_anno.json

ls data/weights/                       # Kỳ vọng: đủ models + gating_mlp_v3.pt
ls data/0/frames/autoshot/ | wc -l     # Kỳ vọng: ~873 video folders
readlink -f data/0/frames/autoshot     # Kỳ vọng: trỏ đúng KEYFRAMES_DIR trong .env
```
- Thiếu model -> download HF (cần HUGGINGFACE_HUB_TOKEN) hoặc rsync từ server cũ.
- Thiếu keyframes -> rsync `data/0/frames/autoshot/`.
- Thiếu qdrant_storage -> dựng lại (section 5.5).

### 4.3 Qdrant + collections
```bash
# Sau khi docker compose up qdrant (chờ hết "unhealthy"):
curl -s http://localhost:6333/collections
# Kỳ vọng: {"result":{"collections":[{"name":"EXPERT_B_V1"},{"name":"SIGLIP_V2"}]},"status":"ok"}
curl -s http://localhost:6333/collections/SIGLIP_V2 | grep -o '"points_count":[0-9]*'
curl -s http://localhost:6333/collections/EXPERT_B_V1 | grep -o '"points_count":[0-9]*'
```
- SIGLIP_V2: kỳ vọng 177,321 points (bên kia đã có).
- **EXPERT_B_V1**: nếu chưa tồn tại -> PHẢI BUILD (section 5.5 bước 5) bằng
  `research/expert_fusion/build_expert_collection.py` (copy script từ server cũ vì research/ không trong git).

### 4.4 .env khớp với thực tế
```bash
grep -E 'PORT|HOST_PUBLIC|QDRANT|KEYFRAMES|CUDA_VISIBLE|HUGGINGFACE' .env
# Kỳ vọng:
#  - Các *_PORT không trùng service khác đang chạy (nếu trùng -> section 9 ĐỔI PORT)
#  - KEYFRAMES_DIR / KEYFRAMES_MOUNT_DIR khớp symlink (4.2)
#  - CUDA_VISIBLE_DEVICES trỏ GPU trống
#  - HUGGINGFACE_HUB_TOKEN có giá trị (nếu cần download model)
```

### 4.5 PYTHON_BIN đúng (tránh bug .venv shadow)
```bash
PYTHON_BIN=<path>/miniconda3/envs/random42_aic/bin/python   # tự chọn đúng path
$PYTHON_BIN -c "import uvicorn, transformers, torch; print('deps OK')"   # Kỳ vọng: deps OK
```
> ⚠️ LUÔN dùng `$PYTHON_BIN` tường minh, KHÔNG dùng `python` trần (terminal activate `.venv` sẽ shadow).

---
## 5. SETUP

### 5.1 Clone
```bash
git clone <repo-url> random42_aic
cd random42_aic
```

### 5.2 Python env + dependencies
```bash
source <path>/miniconda3/etc/profile.d/conda.sh   # hoặc ~/miniconda3, /opt/miniconda3
conda create -n random42_aic python=3.11 -y
conda activate random42_aic
pip install -r requirements.txt
pip install -r requirements-local.txt   # nếu tồn tại
```

### 5.3 Config `.env`
```bash
cp .env.example .env
```
Điền bắt buộc:
- `HUGGINGFACE_HUB_TOKEN` — token HF (model gated)
- `KEYFRAMES_DIR`, `KEYFRAMES_MOUNT_DIR` — path keyframes (docker-compose dùng; MOUNT_DIR phải khớp symlink)
- `FUSION_MODEL_CUDA_VISIBLE_DEVICES`, `SIGLIP_V2_CUDA_VISIBLE_DEVICES` — GPU ids
- `SIGLIP_V2_HOST_PUBLIC`, `FUSION_MODEL_HOST_PUBLIC`, `NGINX_IMAGE_HOST` — host public (UI/hub proxy dùng)
- `SUBMIT_USERNAME`/`SUBMIT_PASSWORD` — DRES submission (nếu có)

### 5.4 Lựa chọn A — chuyển DATA từ server cũ (khuyến dùng)

Chạy trên **server mới** (thay `<SERVER_CU>` bằng host server cũ):
```bash
mkdir -p data
# Models (~15GB)
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/weights/ data/weights/
# Keyframes (~30GB)
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/0/frames/autoshot/ data/0/frames/autoshot/
# Qdrant storage — tránh rebuild (tốn thời gian nhất)
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/qdrant_storage/ data/qdrant_storage/
# File phụ
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/index/ data/index/
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/s2t/ data/s2t/
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/features/ data/features/
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/train_anno.json data/
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/val_anno.json data/
rsync -avz tuannt@<SERVER_CU>:/workspace/tuannt/random42_aic/data/weights/gating_mlp_v3.pt data/weights/
```

⚠️ **Bắt buộc tạo symlink keyframes** (nếu chưa có):
```bash
# data/0/frames/autoshot phải là symlink tới KEYFRAMES_DIR (nginx/hub resolve thumbnail)
ln -s "$KEYFRAMES_DIR" data/0/frames/autoshot
```

### 5.5 Lựa chọn B — dựng lại từ đầu (chỉ khi không rsync được data)

```bash
# 1) Models vào data/weights/: siglip2-giant-opt-patch16-384, jina-clip-v2,
#    keepitreal/vietnamese-sbert, minhnguyent546/viclip-ot, gating_mlp_v3.pt (copy từ server cũ)
# 2) Videos AIC vào data/0/videos/...
# 3) Keyframes: python src/pre_processing/shot_detection/run_pipeline.py ...
# 4) SigLIP2 features: python src/pre_processing/feature_extraction/clip_features.py ...
# 5) jina collection (EXPERT_B_V1):
#    python -m research.expert_fusion.build_expert_collection \
#       --frames-root data/0/frames/autoshot --collection EXPERT_B_V1 --expert jina-clip-v2
#    (⚠️ research/ không có trong git -> copy `research/` từ server cũ trước)
# 6) SIGLIP_V2 collection: ingest từ .npy (script AIC baseline gốc)
```

---

## 6. KHỞI ĐỘNG

```bash
# 1) Docker infra (Qdrant + media_server)
docker compose -f docker-compose-server.yml up -d qdrant-siglip-alpha media_server
# ⏳ Qdrant recover shards vài phút ("unhealthy" là BÌNH THƯỜNG). Chờ API:
until curl -s --max-time 3 http://localhost:6333/collections >/dev/null 2>&1; do sleep 10; done

# 2) Services GPU (thủ công)
./start_services.sh
# ⏳ fusion_model cần ~2-3 phút load 2 models.
```

**Lưu ý quan trọng**: `start_services.sh` mặc định dùng `PYTHON_BIN=/workspace/tuannt/miniconda3/envs/random42_aic/bin/python`. Nếu server mới có path conda khác:
```bash
export PYTHON_BIN=<path>/miniconda3/envs/random42_aic/bin/python
./start_services.sh
```

### Verify
```bash
curl -s http://localhost:9021/hub/ping          # hub
curl -s http://localhost:9029/siglip_alpha/ping  # siglip
curl -s http://localhost:9032/fusion_model/ping  # fusion
# -> tất cả trả "status":200
```

### Test search
```bash
curl -X POST http://localhost:9032/fusion_model/text_search \
  -H 'Content-Type: application/json' \
  -d '{"text":"con dê","k":20,"sort_to_news":false}'
# UI: http://localhost:9021 -> radio FUSION_MODEL
# Hub proxy: http://localhost:9021/hub/fusion_model_text_search
```

---
## 7. TROUBLESHOOTING (các lỗi đã gặp trên server cũ)

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| Search error: 500 | fusion/siglip chưa chạy | `./start_services.sh` + chờ load models |
| `.venv/bin/python: No module named uvicorn` | terminal đang activate `.venv` che python | Dùng `$PYTHON_BIN` tường minh (script đã fix) |
| Qdrant "unhealthy" | Đang recover shards | Chờ (poll `curl localhost:6333/collections`) |
| `curl exit 56` tới 6333 | Qdrant chưa xong recover | Chờ thêm |
| Thumbnail 404 | `KEYFRAMES_DIR`/`KEYFRAMES_MOUNT_DIR` sai hoặc symlink thiếu | Sửa `.env` + `ln -s` |
| GPU OOM | GPU bị chiếm (shared server) | `nvidia-smi` kiểm tra, đổi GPU trong `.env` |
| Port đã dùng (Address already in use) | Server mới đã chạy project trùng port | Xem section 9 ĐỔI PORT |

---

## 8. VẬN HÀNH

```bash
# Restart 1 service (vd fusion_model)
pkill -f "uvicorn src.main:app --host 0.0.0.0 --port 9032"
cd <repo> && SERVICE=fusion_model nohup $PYTHON_BIN -m uvicorn src.main:app --host 0.0.0.0 --port 9032 > logs/fusion_model.log 2>&1 &

# Logs
ls logs/
tail -50 logs/fusion_model.log    # hoặc siglip_alpha.log, hub.log

# Tắt toàn bộ
pkill -f "uvicorn src.main:app"
docker compose -f docker-compose-server.yml stop
```

---

## 9. ĐỔI PORT (khi server mới đã chạy project trùng port — thi, tránh xung đột)

### 9.1 Kiểm tra port nào đang bị chiếm
```bash
for p in 9021 9029 9032 6333 9027; do
  ss -tln | grep -q ":$p " && echo "PORT $p ĐANG DÙNG" || echo "PORT $p trống"
done
```

### 9.2 Cách đổi — phải sửa ĐỒNG BỘ (ví dụ: siglip 9029->9139, fusion 9032->9142, hub 9021->9131)

**a) `.env`** (nơi quan trọng nhất — hub proxy đọc từ đây):
```
HUB_PORT=9131
BASE_URL=http://localhost:9131/
SIGLIP_V2_PORT=9139
SIGLIP_V2_HOST_PUBLIC=http://localhost:9139
FUSION_MODEL_PORT=9142
FUSION_MODEL_HOST_PUBLIC=http://localhost:9142
```

**b) `start_services.sh`**: thay mọi chỗ `9029`->`9139`, `9032`->`9142`, `9021`->`9131`
(port trong lệnh uvicorn `--port`, ping URL, echo thông báo).

**c) `docker-compose-server.yml`**: đổi port mapping `"9029:9029"` -> `"9139:9139"` (và service tương ứng).

**d) `src/services/hub_service.py` + `src/apis/hub_api.py`**: không hardcode port — dùng `*_HOST_PUBLIC`
từ `.env`, nên chỉ cần `.env` đúng là hub proxy đúng.

### 9.3 Sau khi đổi — verify
```bash
./start_services.sh        # script tự dùng port mới
curl -s http://localhost:9139/siglip_alpha/ping && echo
curl -s http://localhost:9142/fusion_model/ping && echo
curl -s http://localhost:9131/hub/ping && echo
# Hub proxy với port mới:
curl -s -X POST http://localhost:9131/hub/fusion_model_text_search -F 'text=con dê' -F 'k=5' | head -c 200
```

### 9.4 Qdrant RIÊNG cho bản test (không đụng 6333 của project đang chạy)

Nếu cần Qdrant riêng để build/test EXPERT_B_V1 mà không ảnh hưởng project đang chạy:
```bash
# .env: đổi SIGLIP_V2_QDRANT_PORT / FUSION_MODEL_QDRANT_PORT (vd 6433/6434)
# docker-compose-server.yml: đổi port mapping qdrant-siglip-alpha "6333:6333" -> "6433:6433"
docker compose -f docker-compose-server.yml up -d qdrant-siglip-alpha
# Build jina collection vào Qdrant mới:
python -m research.expert_fusion.build_expert_collection \
  --frames-root data/0/frames/autoshot --collection EXPERT_B_V1 --expert jina-clip-v2
# (Nhớ đổi FUSION_MODEL_DATABASE_B/URL trỏ đúng Qdrant mới nếu dùng service này để test)
```

---

## 10. GHI CHÚ THÊM

- **Gating**: `FUSION_MODEL_GATING_MODE=context` (deployed, không cần train). MLP v3 collapsed — chỉ fallback.
- **Dataset mới (vòng 2/3)**: không cần retrain — chỉ index frame mới (Lựa chọn B bước 5) + đổi `FUSION_MODEL_DATABASE_A/B` trong `.env`.
- **Paper/tài liệu**: `research/` không push lên git. Nếu cần (eval, ablation, H1 negative result) copy từ server cũ:
  gồm `eval_queries.json`, `FINAL_RESULTS.md`, `H1_ADAPTATION_NEGATIVE.md`, `aic_captions/`, `build_expert_collection.py`.
- **Commit README**: `git add README.md && git commit -m "docs: setup guide + pre-flight checks + port change" && git push`

---

## CHECKLIST CUỐI (AI đối chiếu sau khi setup)

- [ ] GPU + Docker + nvidia-toolkit OK
- [ ] Disk >= 60GB
- [ ] `data/weights/` đủ models; keyframes đủ (~873 folders); symlink đúng
- [ ] `data/qdrant_storage/` có sẵn HOẶC đã build xong `EXPERT_B_V1` (177k points)
- [ ] `.env` điền đủ + port không xung đột (hoặc đã đổi theo section 9)
- [ ] `PYTHON_BIN` đúng, deps import OK
- [ ] 3 pings 200 + search trả kết quả + thumbnail hiện qua media_server
