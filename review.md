# Review: known issues, hardcoded values, and open questions

Running list of things found during the `SIU_Pumpking` -> `random42_aic` port that need a human decision or
follow-up before this is production-ready. See [`migration.md`](migration.md) for the full old-path -> new-path
mapping and what was intentionally dropped.

## Secrets — rotate before doing anything else

The legacy `.env` had real, live secrets committed to a working tree (not pushed to this repo, but they existed
in plaintext on disk and were read during this port). Rotate all three before reusing them anywhere public:

- `HUGGINGFACE_HUB_TOKEN` — a live HF access token
- `GG_TRANSLATE_API_KEY` — a live Google Cloud Translate API key
- `SUBMIT_PASSWORD` (with `SUBMIT_USERNAME=team037`) — live DRES competition login

The old README also told contributors to `scp` data from `ai_intern@14.224.156.113` — a real internal server/
account. That instruction was not carried into the new README; if that box is still reachable, treat its
exposure here as something to review with whoever administers it.

## Insecure / permissive defaults carried over

- `create_app(enable_cors=True, ...)` for `hub`/`result_manager` sets `allow_origins=["*"]`, matching legacy
  behavior. Fine for a competition demo behind a firewall, not fine if this is ever exposed publicly — tighten
  to a real origin list before that happens (`src/apis/base.py`).
- Every service's config still allows the DRES/Translate/HF secrets to be empty strings at startup (no fail-fast
  validation) — the legacy code used to hard-`assert`/`FileNotFoundError` on missing required paths for some
  services (SIGLIP/METACLIP feature paths, dummy vectors) but that validation lived inconsistently across the
  10 old config classes. `Settings` currently does not re-implement those checks; a bad `.env` will fail at
  first use (e.g. Qdrant connection error) rather than at startup. Worth adding explicit startup validation per
  service if fast failure matters more than lenient defaults.

## Design assumptions made during the port — please verify against real infra/data

1. **Qdrant topology**: the legacy `.env` has 3 different Qdrant port pairs (alpha 6333/6334, beta 7333/7334)
   with no explicit note on whether that's 2 separate Qdrant *server instances* or 1 instance with 2 exposed
   port sets. `docker-compose-local.yml`/`docker-compose-server.yml` assume **3 separate Qdrant containers**
   (one per model variant, including a new one for `metaclip`). If production actually ran one shared Qdrant
   server with multiple collections, simplify the compose files accordingly.
2. **`QdrantSearchClient`'s dup/unique data paths** (`src/externals/qdrant_client.py`): legacy hardcoded
   `/dataset/AIC2024/pumkin_dataset/Vinh/...`-style absolute paths for these. The port defaults them to
   `{DATASET_PATH_TEAM}/utils/duplicate1` and `{DATASET_PATH_TEAM}/utils/unique1` as a **guess** — the original
   folder names/locations were never confirmed. Verify against the real dataset layout and adjust
   `Settings`/constructor args if wrong.
3. **`add_database`'s `unique_json_path`** has no dedicated `Settings` field — it's a required caller-supplied
   argument. Add a proper env var per variant if this needs to be config-driven rather than passed at call time.
4. **`UtilService.get_vector`** needs *some* Qdrant collection to query. Legacy hardcoded a
   `PUMPKING_SIGLIP_V2`-named client bypassing all config (a bug in itself). The port wires it to the
   `siglip_alpha` collection as "the closest equivalent" (`src/main.py::_build_util_app`) — confirm that's
   actually the right collection for this endpoint's use case, or make it configurable per-request instead.
5. **`clip_api.py`'s `setup_database` endpoint** became a `GET` with query params sourced from `Settings` via a
   prefix-keyed lookup table, since the router is reused across 3 model variants but the legacy per-model
   handler took zero args (driven entirely by that process's own single-purpose config class). This is the
   piece of the port the implementing agent flagged as least certain — review the endpoint shape before relying
   on it to (re)build a collection.
6. **`hub_api.py` gained `metaclip` passthrough endpoints** that never existed in the legacy hub (which only
   proxied to SIGLIP alpha/beta) — added for parity with the "port all three model variants" decision. METACLIP
   was **never actually deployed** in the legacy system (no `.env` vars existed for it there either), so this
   whole path is untested end-to-end — don't assume it works until it's exercised against a real MetaCLIP-
   indexed Qdrant collection.

## Known behavior differences from the legacy code (intentional bug fixes)

- **Rerank sort-key scale mismatch, found while deduplicating**: the offline generator
  (`color_sort_gen.step_sort_key`) computed HSV from raw 0-255 RGB values; the live request-path duplicate
  (`rerank_handler._step`) normalized to 0-1 first. These aren't byte-for-byte the same function despite prior
  analysis calling them "an unmodified duplicate" — hue is scale-invariant so results were *usually* similar,
  but not guaranteed identical. The new shared `src/modules/rerank/color_sort.step_sort_key` uses the
  **normalized** (live-path) behavior as canonical. If dominant-color JSON files were pre-generated with the old
  offline script, regenerating them with the new shared function may reorder frames slightly differently than
  before.
- **`rerank_service`** now branches on `get_batch(video_name)` to read `Keyframes_L{level}` (batch 0) vs.
  `Keyframes_K{level}` (batch 1) color JSON paths — legacy only ever handled the `L` case, so batch-1 rerank
  requests were silently reading the wrong (or no) file before. Verify this against real batch-1 color data.
- **`result_manager_service`** intentionally *preserves* a pre-existing legacy inconsistency: `send_img_original`
  never branched to the `K` prefix for batch 1 the way the regular image path does. This was left as-is (not
  silently fixed) because the correct behavior wasn't clear from the code alone — flagged in a comment at the
  call site, decide and fix explicitly.
- **DRES login is no longer a side effect** of constructing `SubmissionService` — it now happens once at app
  startup via a FastAPI `lifespan`, and a failure is logged as a warning rather than crashing the process. There
  is currently **no automatic retry** if that initial login fails (e.g. DRES unreachable at boot) — submission
  endpoints will fail until the service is manually restarted or a retry path is added.
- **`get_vector` in `util_service.py`** was rewritten from scratch (legacy bypassed all config with a hardcoded
  `QdrantClient(url="http://localhost:6333")`) — the new implementation goes through the injected
  `QdrantSearchClient`, so behavior is not byte-for-byte identical to the old (undocumented, "maybe frame isn't
  in database?"-commented) implementation.

## Explicitly out of scope (not ported — see migration.md for the full list)

- `engine/Object_Detection/Detic/` + its `third_party/` (CenterNet2, Deformable-DETR) — a large vendored
  detectron2-based framework. If Detic-based object detection is needed, vendor it separately (git submodule or
  its own pip-installable package) rather than copying ~250 files into this repo.
- The legacy vendored, pre-built `nginx/` directory (full nginx 1.24.0 source tree + compiled binary + build
  objects checked into git — a real anti-pattern) was replaced with the official `nginx:alpine` Docker image in
  both compose files. Note the new `media_server` service uses nginx's default config, not the old
  `nginx.conf`'s specific directives (gzip, cache headers, `.avif` MIME type registration) — if `.avif` frames
  don't render correctly through the new media server, that's why; add a custom `nginx.conf` with the right
  MIME type mapping.
- `engine/speech_to_text/`, `engine/scene_classifier/`, and the VLM extractor were all **broken or unverified in
  the legacy repo** (real bugs: undefined-name crashes, missing `self` params) and, as far as this port could
  confirm, never actually wired into a working end-to-end run. They were fixed structurally (imports resolve,
  signatures are correct) during the port into `src/pre_processing/`, but functionally **none of them have been
  executed against real data** — treat as "should work" not "known to work."

## requirements.txt

Reconstructed by statically scanning every import actually used across the ported `src/` tree (the original
`requirements.txt` was empty in this repo). It has **not** been installed/run end-to-end — expect to need a
CUDA-specific `torch` install command (`--index-url https://download.pytorch.org/whl/cu128` or similar) rather
than the plain PyPI wheel, and to hit missing transitive deps on first real `pip install`.
