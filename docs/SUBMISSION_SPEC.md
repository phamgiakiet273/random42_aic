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
- **Time = "the time at which the found frame appears in the original video, in ms"** (the PDF's
  words; it gives no formula). We send round(frame_idx / fps * 1000), which IS that time on
  constant-frame-rate video: all of L (873), M, S, and 176 of the 298 N traffic cams.
  The other 122 N cams use a per-frame real-time table (see "Frame timing" below).
- **No duplicate submissions for one query** (each wrong submit = -10 pts).
  => the central service refuses a repeat team-wide (HTTP 409, nothing sent).

## Payloads
KIS (Textual + Video KIS):
  {"answerSets":[{"answers":[{"mediaItemName":"<VIDEO_ID>","start":<ms>,"end":<ms>}]}]}
QA:    {"answerSets":[{"answers":[{"text":"QA-<ANSWER>-<VIDEO_ID>-<ms>"}]}]}
TRAKE: {"answerSets":[{"answers":[{"text":"TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,..."}]}]}
  (TRAKE uses FRAME numbers, one per event stage, same video; not ms.)

## Frame timing on 122 traffic cams (found + fixed 2026-09-24)
- Our frame numbers are OpenCV's decode counter (batch1/keyframes.py) and our fps is
  decoded-frames / duration (batch1/fix_fps.py). On 122 N videos OpenCV skips corrupt
  frames and/or the frame rate varies, so frame / fps drifted from the frame's real time:
  N029_V002 up to 21.6 s (mean 11.5 s), N030_V001 up to 8.3 s. L, M, S, other N: exact.
- **Fix:** batch1/frame_ms/ decoded those 122 videos once with the same OpenCV and recorded
  every frame's real time -> `data/1/fps/frame_ms/<video>.json` + `index.json` (served under
  /media/frames/1/fps/frame_ms/). The UI (src/ui/aic/src/api/timing.js) sends that time for
  KIS / Q&A and seeks / marks by it in the viewer; other videos keep frame / fps.
  Validated: the video frame at the table's time matches the keyframe image (noise-level
  difference) on N029_V002 / N007_V003 / N030_V001 / N004_V001; frame / fps hit other frames.
  Ops + publish step: batch1/frame_ms/OPS.md.
- **Still open (ask BTC):** DRES 2.0.4 stores KIS targets in ms; a target entered as a FRAME
  number is converted with the NOMINAL fps (ffprobe r_frame_rate,
  MediaCollectionCommand.kt:481), e.g. 12.5 for N029_V002 (real 10.95). We follow the PDF
  ("time the frame appears in the original video" = real time). And TRAKE FRAME_IDs on these
  videos are right only if BTC counts frames as OpenCV does (it skips corrupt frames).

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
- submits use the service's own session; the evaluation is the one the user picked in the
  header when DRES runs several at once (must be ACTIVE; with several ACTIVE and none picked
  the service refuses, 409), else the only ACTIVE one
- a submit rejected with 401/403 is resent once after re-login (not recorded by DRES)
- team-wide dup guard: same eval + same answer text within `SUBMIT_DEDUP_SECONDS`
  (300) -> 409, nothing sent; DRES errors release the guard (not scored)
- audit: `<LOG_DIR>/submissions.jsonl`

## Our code status (2026-09-23)
- Backend: all 3 formats + the v2 flow; `official_video_id` reads `name_map.json`
  (bundled `src/utils/name_map.json`, 614 batch-1 names, + the live per-batch maps)
  and strips the extension. Verified live: login + evaluation list against
  eventretrieval.one (no submit sent).
- UI (no mode switch): each result card has K (submit this frame as KIS, one click), Q (Q&A
  dialog, answer box always empty, Enter submits) and TR (the frame viewer on an empty TRAKE
  timeline). The viewer (opens paused) has KIS / Q&A / TRAKE panels acting on the frame
  showing; TRAKE events are draggable markers on the video timeline (wavesurfer.js); a temporal
  chain's "Use as TRAKE" opens it pre-marked. Header "confirm" toggle asks before every submit.
  Q&A answers are sent NFC-normalised with single spaces; Enter while an IME is composing does
  not submit. A video with unknown fps cannot be submitted.
- Service: a DRES timeout AFTER sending keeps the duplicate guard (504 "may have been
  recorded"); only "could not connect" is safe to retry (502).
- Verified 2026-09-24 end to end (real UI -> submission service -> local DRES 2.0.4 judge,
  dres_test/): KIS wrong/duplicate-blocked/correct, VKIS, Q&A (incl. "Cá Sòng"), TRAKE
  partial + full: all verdicts as expected.
- Remote teammates reach it through the ngrok gateway (docs/LOCAL.md).
