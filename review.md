# Architecture & code-quality review — `random42_aic`

Not a line-by-line bug list. This is about the *shape* of the code: hardcoding, duplicated logic,
stringly-typed data flow, config that lives in five places, and an unstructured, un-built frontend. Ordered by
how much they'll hurt maintenance.

---

## 1. Dataset-path logic is re-implemented in 5 places — the core structural debt

The string `"{batch}/frames/{split}/Keyframes_{L|K}{level}/keyframes/{video}/{frame}"` (and its `Videos_`
sibling) is rebuilt independently in:

- [`utils/metadata.py:35`](src/utils/metadata.py#L35) `get_frame_path` / `get_video_path`
- [`services/result_manager_service.py:57`](src/services/result_manager_service.py#L57) (3 variants, with a
  zero-pad special case for batch-1 levels)
- [`utils/video_batch.py:33`](src/utils/video_batch.py#L33) (`video_name[1:3]` slicing)
- [`externals/qdrant_client.py:154`](src/externals/qdrant_client.py#L154) (ingest side)
- [`services/rerank_service.py:57`](src/services/rerank_service.py#L57) (color JSON path)

Each uses slightly different rules (`split('_')[0]` vs `[1:3]` slice vs `int()`+re-pad vs raw string). They only
work today because the on-disk naming happens to line up; any change to the dataset layout means editing five
files and hoping you found them all. **There should be one `DatasetLayout` module** that owns
"video_name → (batch, level, prefix, dirs)" and every consumer calls it. This is the single highest-value
refactor here.

## 2. Frontend has two competing config systems, and neither is used consistently

- `hub.html` server-injects `window.BASE_URL = "{{ base_url }}"`
  ([`hub.html:331`](src/ui/static/js/../templates/hub.html#L331)).
- `api.js` has a *separate* hand-edited constant `const API_PREFIX = ''`
  ([`api.js:6`](src/ui/static/js/api.js#L6)) — comment still references the old `'siu_pumpking_2'` deploy.
- [`thumbnailView.js:265`](src/ui/static/js/thumbnailView.js#L265) and
  [`:450`](src/ui/static/js/thumbnailView.js#L450) **ignore both** and hardcode the *old production domain*
  `https://api.siu.edu.vn/siu_pumpking_1/hub/send_img_original/...`. This is dead SIU_Pumpking deployment config
  that will silently point the new system at the old server.
- [`chatbotHandler.js:6`](src/ui/static/js/chatbotHandler.js#L6) hardcodes an n8n webhook
  `http://localhost:5678/webhook/<uuid>`.

Pick one mechanism (the server-injected `window.BASE_URL` is the right one — it's already wired to backend
`Settings.base_url`) and route *every* request through `prefixedFetch`. Delete the hardcoded domains.

## 3. Frontend/backend route drift: metaclip exists on the server, not in the UI

Backend generates `siglip_alpha` / `siglip_beta` / **`metaclip`** passthrough routes
([`apis/hub_api.py:24`](src/apis/hub_api.py#L24)), but the UI's `ROUTES` table only knows
`SIGLIP_ALPHA` / `SIGLIP_BETA` ([`searchHandler.js:22`](src/ui/static/js/searchHandler.js#L22)). The third model
variant the backend was extended to support is unreachable from the app. Symptom of routes being duplicated as
string literals on both sides instead of discovered.

## 4. The frontend is unstructured and has no build tooling

- **No `package.json`, no bundler, no lockfile.** jQuery 3.6, jszip, FontAwesome (`all.min.css`), and a
  **13,400-line pre-compiled Vue/n8n chat widget** (`chat.bundle.es.js`) are all committed as raw vendored files
  and pulled in via `<script>` tags. Unauditable, unpinnable, unupdatable.
- **Two module systems coexist:** `main.js` is loaded as `type="module"` (ES imports), while jQuery/jszip are
  loaded as globals — so the codebase mixes `import {...}` with implicit `window.$`.
- **God files with module-level mutable state:** `resultManager.js` (1141 lines), `submissionButtons.js`
  (1063), `searchHandler.js` (714), `thumbnailView.js` (600). Direct DOM manipulation over shared top-level
  `let` state (`let temporalEvents = []`, `let mainEventIndex = 0`), no view/state separation. These need to be
  split by concern before anyone can safely change them.

## 5. Backend config: 3x copy-pasted variant blocks + a config surface with holes

- `Settings` ([`utils/settings.py`](src/utils/settings.py)) has three near-identical ~10-field blocks
  (`siglip_v2_*`, `siglip_v2_b_*`, `metaclip_*`). Adding a fourth model = copy-paste another block, plus a new
  branch in `main.py`'s if/elif ladder ([`main.py:162`](src/main.py#L162)), plus a new entry in
  `_host_port_workers` ([`main.py:223`](src/main.py#L223)), plus a `_VARIANT_SETTINGS_FIELDS` row
  ([`apis/clip_api.py:23`](src/apis/clip_api.py#L23)). A `list[VariantConfig]` (or nested model keyed by variant
  name) would collapse all four touch-points into one.
- **Config surface is inconsistent:** almost everything is a `Settings` field, but `unique_json_path` has none
  and must be threaded through as a caller argument ([`clip_api.py:57`](src/apis/clip_api.py#L57)). Either it's
  config or it isn't.

## 6. Stringly-typed data flow and hardcoded magic numbers

- **Everything is stringified then re-parsed.** `_format_search_results`
  ([`qdrant_client.py:552`](src/externals/qdrant_client.py#L552)) coerces every field to `str(...)` (including
  the placeholder score `"0.273"`), and downstream code re-parses with `int()`/`float()` in `merge_scores`,
  `_sort_to_news`, `rerank_service`, `_add_paths`. Typed models (or at least keeping numbers numeric) would kill
  a whole class of conversion bugs.
- **The hub API takes JSON-in-a-form-string:** `frame_class_filter: str = Form("[]")` then `ujson.loads(...)`
  ([`hub_api.py:39`](src/ui/static/js/../../apis/hub_api.py#L39)) instead of a typed request body — the only
  service that does this; the CLIP/util/submission routers use proper pydantic bodies. Two API conventions in
  one app.
- **Sample data baked into the API contract:** hub `Form(...)` defaults are real-looking values
  (`mediaItemName="K19_V006"`, `video_id="L11_V018"`, `time="359960"` at
  [`hub_api.py:184`](src/apis/hub_api.py#L184)). Demo fixtures don't belong in endpoint signatures.
- **Unnamed magic constants** scattered across the backend: Qdrant `shard_number=90`,
  `default_segment_number=16`, `max_segment_size=20000000`, `indexing_threshold=1000`
  ([`qdrant_client.py:97`](src/externals/qdrant_client.py#L97)); temporal window `frame ± 1000`
  ([`qdrant_client.py:397`](src/externals/qdrant_client.py#L397)); news-grouping cap `count <= 10`; rerank
  `repetitions=8`; `_MAX_UPLOAD_BYTES = 50MB`. None named or configurable — pull the tuning knobs into named
  constants / `Settings`.

## 7. Smaller structural smells

- `main.py` mixes import-time side effects (reads `SERVICE`, builds `app`, `setup_logger` at module top,
  [`main.py:265`](src/main.py#L265)) with a `__main__` block — importing the module for any reason (tests,
  tooling) triggers full app construction and a hard `raise` on a missing env var.
- Legacy naming leaked into config: `summuray_prompt_path` / `SUMMURAY_PROMPT_PATH` (typo), `base_output_craw_path`
  ([`settings.py:173`](src/utils/settings.py#L173)) — will bite anyone matching on the correct spelling.
- Method naming is inconsistent within one class: `deleteDatabase` / `getCount` (camelCase) next to
  `scroll_video` / `search_temporal` (snake_case) in `QdrantSearchClient`.

---

## Suggested order of attack

1. Extract a single **dataset-layout module** (#1) — unblocks correctness and removes the 5-way duplication.
2. Unify **frontend config** on `window.BASE_URL` + `prefixedFetch`, delete hardcoded `api.siu.edu.vn` /
   localhost webhook URLs (#2), and add the missing metaclip routes (#3).
3. Introduce a **`VariantConfig` list** to collapse the 4-place CLIP-variant duplication (#5).
4. Give the **frontend a `package.json` + bundler** and start splitting the 1000-line god-files (#4).
5. Name the magic numbers and drop the stringly-typed form-JSON pattern (#6) as you touch each area.

Secrets/infra caveats from the port (rotate committed HF/Translate/DRES creds, `allow_origins=["*"]`, no
startup validation, untested metaclip/pre_processing) are tracked in `migration.md` — not repeated here.
</content>
