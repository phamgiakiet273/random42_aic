# Final-round submission spec (AIC 2025 Chung Kết) — authoritative

Source: HD-ChungKet-2026.pdf (2026 final; same formats as 2025, NEW server URL). All tasks are Known-Item
Search (KIS) family; **3 submission payload formats**.

## DRES server (VBS standard, dres-dev/DRES)
- Base: `https://eventretrieval.one` (final may differ — BTC gives it live).
- 2026 doc gives no test-window dates. Team creds are in the gitignored .env
  (SUBMIT_USERNAME / SUBMIT_PASSWORD).
- Flow: POST `/api/v2/login` {username,password} -> `sessionId`;
  GET `/api/v2/client/evaluation/list?session=` -> pick the `status=="ACTIVE"` id;
  POST `/api/v2/submit/{evalId}?session=` with the body below.

## PRECISION RULES (must be exact)
- **mediaItemName = video file name WITHOUT extension.** No `.mp4`.
  Source = authoritative `name_map.json` (organiser zip names), NOT a rule:
  N -> `N001-V001`, S -> `S01-V001` (hyphen); M -> `M05_V001` (underscore);
  L (no map) -> `L21_V001` as-is.
- **Time = ms of the frame in the ORIGINAL video = round(frame_idx / fps * 1000).**
- **No duplicate submissions for one query** (each wrong submit = -10 pts).
  => the central service refuses a repeat team-wide (HTTP 409, nothing sent).

## Payloads
KIS (Textual + Video KIS):
  {"answerSets":[{"answers":[{"mediaItemName":"<VIDEO_ID>","start":<ms>,"end":<ms>}]}]}
QA:    {"answerSets":[{"answers":[{"text":"QA-<ANSWER>-<VIDEO_ID>-<ms>"}]}]}
TRAKE: {"answerSets":[{"answers":[{"text":"TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,..."}]}]}
  (TRAKE uses FRAME numbers, one per event stage, same video; not ms.)

## Scoring (for submit strategy in the UI)
Pmax=100, Pbase=50, penalty=10/wrong; f(t)=1 - t_submit/T_task.
Score_full = max(0, 50 + 50*f(t) - 10*k). TRAKE partial (50-99% kf) = full/2.
T_task: Video KIS 4 min; Textual KIS / QA / TRAKE 5 min. Submit early = more points.

## Architecture (central, like legacy — but the service owns the session)
ONE `submission` service on the server (1 worker process, forced in main.py) is the
team's only DRES client. Hubs forward `/submission/*` to it
(`src/apis/submission_proxy.py`); the public gateway routes `/submission/` to it.
- login once; re-login only on 401/403 from DRES (never per request -- legacy's
  per-hub `/relogin` loop minted a new session every minute from every hub worker)
- ACTIVE evaluation re-read every `SUBMIT_POLL_SECONDS` (10); UI polls the cached
  state every 10 s (no DRES call)
- submits use the service's own session/eval; client-sent ids are ignored
- a submit rejected with 401/403 is resent once after re-login (not recorded by DRES)
- team-wide dup guard: same eval + same answer text within `SUBMIT_DEDUP_SECONDS`
  (300) -> 409, nothing sent; DRES errors release the guard (not scored)
- audit: `<LOG_DIR>/submissions.jsonl`

## Our code status (2026-09-23)
- Backend: all 3 formats + the v2 flow; `official_video_id` reads `name_map.json`
  (bundled `src/utils/name_map.json`, 614 batch-1 names, + the live per-batch maps)
  and strips the extension. Verified live: login + evaluation list against
  eventretrieval.one (no submit sent).
- UI: 1-button submit on every result card and in the frame modal (KIS/Q&A/TRAKE
  mode in the header bar), one-click by default + Settings "confirm before submit",
  TRAKE sequence from marks or "Use as TRAKE" on a temporal chain, DRES badge
  (polls the service every 10 s), CORRECT/WRONG toast. A video with unknown fps
  cannot be submitted (its time cannot be computed).
- Remote teammates reach it through the ngrok gateway (docs/LOCAL.md).
