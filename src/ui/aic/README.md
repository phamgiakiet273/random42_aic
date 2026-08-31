# AIC 2026 frontend

React 19 + Vite + Tailwind 4 + daisyUI, with zustand for client state and
TanStack Query for server state.

```bash
bun install
bun dev      # http://localhost:10000
bun run build
bun run lint
```

Copy `.env.example` to `.env.local` if the backend is not on the default ports.

## Remote access

The dev server proxies `/hub`, `/img`, `/video` and `/result_manager` to the
backend, so **port 10000 is the only one that has to be reachable** and every
request the browser makes is same-origin.

That is not a convenience -- it is what makes remote use work at all. The hub
builds media URLs from `NGINX_IMAGE_HOST`, which is `http://localhost:9027/img`;
viewed from another machine `localhost` is the *viewer's* machine, so thumbnails
fail silently (nginx logs nothing, because the request never arrives).
`src/api/media.js` therefore keeps only the path component of the published base
URLs unless `VITE_MEDIA_BASE_URL` says otherwise.

To expose each service directly instead, set `VITE_API_BASE_URL`,
`VITE_MEDIA_BASE_URL` and `VITE_RESULT_MANAGER_BASE_URL` to absolute URLs on a
reachable address (not `localhost`) and open those ports too.

## How it talks to the backend

All retrieval goes through one `POST /hub/search`; `model` selects the backend
and `search_type` the mode (`text` / `image` / `temporal` / `scroll`).

Search records carry only identifiers — `idx_folder`, `video_name`,
`keyframe_id` — not media paths. `GET /hub/media_config` publishes the dataset
layout rule once, and `src/api/media.js` composes image/video URLs from it.
`src/utils/dataset_layout.py` owns the same rule server-side, so the layout is
defined in one place rather than copied into the client.

Temporal search answers with a list of *chains* (one array per matched event
sequence). `runSearch` flattens them for the grid and tags each record with
`chainId` / `chainPosition` so the sequence is still visible.

## Wired

- Text, image (file / paste / drag / URL), temporal (multi-event with a
  selectable main event), and scroll/browse search
- Result grid with pagination, thumbnail sizing, per-result score and rank
- Frame detail modal: video seeking to the clicked frame, live current-frame
  readout, ±1s / ±1 frame nav, transcript, neighbouring frames, frame marking
- Filters: video/batch selection, transcript filter, time range, excluded shots
  (exclusion sends `skip_frames`, and optionally re-runs the search)
- Settings: top-K, results per page, neighbour count, thumbnail size, download
  limit, frame-class filter, news grouping, S2T toggle
- CSV export in KIS and TRAKE formats, server-rendered (`POST /hub/download`)
  or built in the browser
- Result manager: upload a submission CSV, review/reorder/delete rows, re-export

## Not wired yet (TODO)

These need a design decision before they are worth building:

- **Auto-translate** — `POST /hub/translate` exists and `src/api/search.js`
  exposes `translate()`, but nothing calls it. Unclear whether it should rewrite
  the query box or translate silently on submit.
- **DRES submission** (KIS / QA / TRAKE buttons, session/eval id) — doc comment
  [b] defers this to the finals, and doc comment [q] wants the session/eval
  endpoints moved off the hub onto the submission service first.
- **Colour rerank** — doc comment [e] says rerank is dropped for 2026; the
  service and `POST /hub/rerank_color` still exist but nothing in the UI calls
  them.
- **Query history, voice input, chatbot** — present in the legacy UI, not ported.

## Known data gaps

- Only `siglip_alpha` has a populated Qdrant collection. `siglip_beta`,
  `metaclip` and `fusion_model` are shown in the model picker but disabled.
- Batch 1 (`K*`) source videos are not present on this machine
  (`data/original/1/videos` is empty), so video playback only works for batch 0
  (`L*`) results. Their keyframes are indexed and thumbnails render fine.
