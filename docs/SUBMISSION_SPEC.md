# Final-round submission spec (AIC 2025 Chung Kết) — authoritative

Source: HD-ChungKet.pdf + Slides-HD-ChungKet.pdf. All tasks are Known-Item
Search (KIS) family; **3 submission payload formats**.

## DRES server (VBS standard, dres-dev/DRES)
- Base: `https://eventretrieval.oj.io.vn` (final may differ — BTC gives it live).
- **Test server open 12:00 2025-11-01 → 23:59 2025-11-07; accounts sent 2025-11-01.**
  => cannot live-test before then; build to spec, verify payloads offline.
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
  => UI must track submitted answers per active eval and block/warn dupes.

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

## Our code status
- Backend `submission_service` + `dres_client` already implement all 3 formats + the
  v2 flow correctly. FIX: make `official_video_id` name_map-driven + strip extension.
- UI: only KIS CSV export today. TO BUILD: live 1-button submit (KIS default) on every
  card/modal/player, one-click direct + settings confirm-toggle, QA/TRAKE panels,
  session/eval bootstrap, per-eval dup-submission guard, CORRECT/WRONG feedback.
