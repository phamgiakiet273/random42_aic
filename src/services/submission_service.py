"""The team's ONE DRES client: submits KIS/QA/TRAKE answers for everybody.

Like the legacy `services/submission_service.py`, this runs once, on the server,
and every UI -- the server's and each teammate's -- reaches it (via its hub or the
public gateway). Unlike legacy, it owns the session and evaluation outright:

  * logs in once, and again only when DRES rejects the session. Never per client
    request: every login mints a new session, which is how the legacy hub's
    periodic /relogin churned session ids between teammates;
  * re-reads the ACTIVE evaluation every SUBMIT_POLL_SECONDS in the background;
  * submits with ITS session/evaluation -- ids a client sends are ignored;
  * refuses a byte-identical answer to the same evaluation within
    SUBMIT_DEDUP_SECONDS, team-wide (a repeat never scores and can cost points);
  * appends every attempt to <LOG_DIR>/submissions.jsonl.

Run it with ONE worker process (main.py forces this): each process would hold its
own session, poll and duplicate guard.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import time
from http import HTTPStatus

import httpx

from src.common.schemas.api import APIResponse
from src.common.schemas.submission import (
    SubmitKISRequest,
    SubmitQARequest,
    SubmitTRAKERequest,
)
from src.externals.dres_client import DRESClient
from src.utils.logger import get_logger
from src.utils.settings import get_settings

logger = get_logger()

# ---------------------------------------------------------------------------
# Video name -> the DRES mediaItemName.
#
# The final-round spec (docs/SUBMISSION_SPEC.md) is explicit: mediaItemName is
# the ORIGINAL video file name WITHOUT extension. The original names differ per
# batch (N001-V001 / S01-V001 use a hyphen, M05_V001 uses an underscore, L21_V001
# has no separate map), so we DO NOT reconstruct them with a rule -- we read the
# authoritative `name_map.json` the extractor built from the organiser's zips
# ({internal_stem: official_stem}) and fall back to the internal stem as-is for
# anything not in the map (e.g. batch-0 L). Never append the extension.
# ---------------------------------------------------------------------------
# Colon-separated globs. The live per-batch maps (server, mounted, authoritative
# + current) AND a repo-bundled copy under src/ (rides the ./src mount, so client
# deployments that have no dataset still resolve the exact names). Merged; the
# live maps win where both exist.
_NAME_MAP_GLOB = os.getenv(
    "NAME_MAP_GLOB",
    "/app/src/utils/name_map.json" + os.pathsep + "/app/data/*/_meta/name_map.json",
)
_name_map: dict[str, str] = {}
_name_map_mtime: float = -1.0


def _load_name_map() -> dict[str, str]:
    """Merge every name_map.json under the configured globs; reload on change."""
    global _name_map, _name_map_mtime
    paths = [p for g in _NAME_MAP_GLOB.split(os.pathsep) for p in sorted(glob.glob(g))]
    mtime = max((os.path.getmtime(p) for p in paths), default=0.0)
    if mtime != _name_map_mtime:
        merged: dict[str, str] = {}
        for p in paths:
            try:
                merged.update(json.load(open(p, encoding="utf-8")))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"name_map load failed for {p}: {e}")
        _name_map, _name_map_mtime = merged, mtime
        logger.info(f"name_map loaded: {len(merged)} videos from {len(paths)} file(s)")
    return _name_map


def official_video_id(name: str) -> str:
    """Internal video name -> DRES mediaItemName (authoritative, no extension)."""
    stem = str(name).partition(".")[0]  # drop any extension
    return _load_name_map().get(stem, stem)


class _NotSent(Exception):
    """The answer never reached DRES (no connection): safe to send again."""


class _NoReply(Exception):
    """The answer was (at least partly) sent but DRES did not reply: it MAY be recorded."""


class DRESSubmitError(RuntimeError):
    """Raised when a DRES `/submit` call returns a non-2xx response."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class SubmissionService:
    def __init__(self, dres_client: DRESClient | None = None) -> None:
        settings = get_settings()
        self.dres_client = dres_client or DRESClient()
        self.eval_id: str | None = None
        self.eval_name: str | None = None
        self.last_refresh: float | None = None
        self.last_error: str | None = None
        self._poll_seconds = settings.submit_poll_seconds
        self._dedup_seconds = settings.submit_dedup_seconds
        self._recent: dict[str, tuple[float, str]] = {}  # answer key -> (time, verdict)
        self._lock = asyncio.Lock()
        self._log_path = os.path.join(settings.log_dir, "submissions.jsonl")

    @property
    def configured(self) -> bool:
        return bool(self.dres_client.username and self.dres_client.password)

    # ---- session + ACTIVE evaluation (owned here, shared by the whole team) ----

    async def _login(self) -> None:
        await self.dres_client.login()

    async def refresh(self) -> None:
        """Re-read the ACTIVE evaluation. Logs in only when there is no session, or
        once more when DRES says the session is no longer valid."""
        if not self.configured:
            self.last_error = "DRES credentials not set (SUBMIT_USERNAME / SUBMIT_PASSWORD)"
            return
        if not self.dres_client.session_id:
            await self._login()
        try:
            evaluations = await self.dres_client.get_evaluations(self.dres_client.session_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (401, 403):
                raise
            logger.warning("DRES rejected the session; logging in again")
            await self._login()
            evaluations = await self.dres_client.get_evaluations(self.dres_client.session_id)
        active = [e for e in evaluations if e.get("status") == "ACTIVE"]
        if len(active) > 1:
            logger.warning(f"{len(active)} ACTIVE evaluations; using the first: {[e.get('name') for e in active]}")
        new_id = active[0]["id"] if active else None
        if new_id != self.eval_id:
            logger.info(f"ACTIVE evaluation changed: {self.eval_id} -> {new_id} ({active[0].get('name') if active else '-'})")
        self.eval_id = new_id
        self.eval_name = active[0].get("name") if active else None
        self.last_refresh = time.time()
        self.last_error = None

    async def poll_forever(self) -> None:
        """Background task (started by main.py): keep session + evaluation current."""
        while True:
            try:
                await self.refresh()
            except Exception as exc:  # DRES down / network: keep polling
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(f"DRES refresh failed: {self.last_error}")
            await asyncio.sleep(self._poll_seconds)

    def _state(self) -> dict:
        return {
            "session_id": self.dres_client.session_id,
            "eval_id": self.eval_id,
            "eval_name": self.eval_name,
            "refreshed_s_ago": None if self.last_refresh is None else round(time.time() - self.last_refresh, 1),
            "error": self.last_error,
        }

    async def ping(self) -> APIResponse:
        return APIResponse(status=HTTPStatus.OK.value, message="Running (Healthy)", data="ping")

    async def get_session_and_eval(self) -> APIResponse:
        """UI bootstrap/badge. Served from the shared state -- no DRES call unless
        this process has never refreshed (the poll normally keeps it current)."""
        if not self.configured:
            return APIResponse(
                status=HTTPStatus.BAD_REQUEST.value,
                message="DRES credentials not set (SUBMIT_USERNAME / SUBMIT_PASSWORD)",
                data=self._state(),
            )
        if self.last_refresh is None:
            try:
                await self.refresh()
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
        if not self.dres_client.session_id:
            return APIResponse(
                status=HTTPStatus.SERVICE_UNAVAILABLE.value,
                message=f"not logged in to DRES: {self.last_error}",
                data=self._state(),
            )
        return APIResponse(
            status=HTTPStatus.OK.value,
            message="ok" if self.eval_id else "logged in, but no ACTIVE evaluation",
            data=self._state(),
        )

    # Legacy-shaped reads, kept for old callers; all served from the shared state.
    async def get_session_id(self) -> APIResponse:
        r = await self.get_session_and_eval()
        return APIResponse(status=r.status, message=r.message, data={"session_id": self.dres_client.session_id})

    async def get_eval_id(self, session_id: str | None = None) -> APIResponse:
        r = await self.get_session_and_eval()
        return APIResponse(status=r.status, message=r.message, data={"eval_id": self.eval_id})

    async def relogin(self) -> APIResponse:
        """Manual recovery only. Nothing calls this automatically any more."""
        await self._login()
        await self.refresh()
        return APIResponse(status=HTTPStatus.OK.value, message="Re-login successful", data=self._state())

    # ---- submit ----

    async def submit_kis(self, request: SubmitKISRequest) -> APIResponse:
        name = official_video_id(request.mediaItemName)
        payload = {"answerSets": [{"answers": [{"mediaItemName": name, "start": request.start, "end": request.end}]}]}
        return await self._submit(f"KIS-{name}-{request.start}-{request.end}", payload)

    async def submit_qa(self, request: SubmitQARequest) -> APIResponse:
        text = f"QA-{request.answer}-{official_video_id(request.video_id)}-{request.time}"
        return await self._submit(text, {"answerSets": [{"answers": [{"text": text}]}]})

    async def submit_trake(self, request: SubmitTRAKERequest) -> APIResponse:
        elements = [e.strip() for e in request.frame_ids.split(",") if e.strip()]
        text = f"TR-{official_video_id(request.video_id)}-{','.join(elements)}"
        return await self._submit(text, {"answerSets": [{"answers": [{"text": text}]}]})

    async def _send(self, payload: dict) -> httpx.Response:
        """POST to DRES, telling "never sent" apart from "sent, no reply"."""
        try:
            return await self.dres_client.submit(self.eval_id, self.dres_client.session_id, payload)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise _NotSent(f"could not reach DRES ({type(exc).__name__})") from exc
        except httpx.HTTPError as exc:  # ReadTimeout, WriteTimeout, RemoteProtocolError, ...
            raise _NoReply(type(exc).__name__) from exc

    def _log(self, answer: str, outcome: str, detail: str = "") -> None:
        try:
            os.makedirs(os.path.dirname(self._log_path) or ".", exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "eval_id": self.eval_id,
                                    "answer": answer, "outcome": outcome, "detail": detail},
                                   ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(f"could not append to {self._log_path}: {exc}")

    async def _submit(self, answer: str, payload: dict) -> APIResponse:
        """POST one answer with the shared session/evaluation, team-wide dup-guarded."""
        if not self.eval_id or not self.dres_client.session_id:
            await self.refresh()  # e.g. the evaluation opened since the last poll
        if not self.eval_id:
            raise DRESSubmitError(HTTPStatus.CONFLICT.value, "No ACTIVE evaluation on DRES -- nothing submitted")
        key = f"{self.eval_id}|{answer}"
        async with self._lock:  # a teammate's simultaneous identical click is refused too
            hit = self._recent.get(key)
            if hit and time.time() - hit[0] < self._dedup_seconds:
                self._log(answer, "refused-duplicate", hit[1])
                raise DRESSubmitError(
                    HTTPStatus.CONFLICT.value,
                    f"Already submitted by the team {int(time.time() - hit[0])}s ago ({hit[1]}) -- not resent",
                )
            self._recent[key] = (time.time(), "in flight")
        logger.info(f"SUBMIT {answer} -> eval {self.eval_id}")
        try:
            resp = await self._send(payload)
            if resp.status_code in (401, 403):  # session rejected => nothing was recorded; safe to resend once
                logger.warning("DRES rejected the session on submit; logging in again and resending once")
                try:
                    await self._login()
                except Exception as exc:
                    raise _NotSent(f"DRES login failed ({type(exc).__name__})") from exc
                resp = await self._send(payload)
        except _NotSent as exc:
            self._recent.pop(key, None)  # never reached DRES: allow a retry
            self._log(answer, "not-sent", str(exc))
            raise DRESSubmitError(HTTPStatus.BAD_GATEWAY.value, f"{exc} -- nothing submitted, safe to retry") from exc
        except _NoReply as exc:
            # A timeout AFTER sending is not "never reached DRES": it may be recorded,
            # and resending a wrong answer costs another -10. Keep the guard.
            self._recent[key] = (time.time(), "NO REPLY")
            self._log(answer, "no-reply", str(exc))
            raise DRESSubmitError(
                HTTPStatus.GATEWAY_TIMEOUT.value,
                f"No reply from DRES ({exc}): it MAY have been recorded. The same answer stays blocked for "
                f"{self._dedup_seconds}s -- check the DRES page before submitting again",
            ) from exc
        except Exception as exc:
            self._recent.pop(key, None)
            self._log(answer, "error", repr(exc))
            raise

        if resp.status_code == 200:
            result = resp.json()
            verdict = str(result.get("submission") or result.get("status") or "")
            self._recent[key] = (time.time(), verdict or "sent")
            self._log(answer, verdict or "sent", result.get("description", ""))
            return APIResponse(
                status=HTTPStatus.OK.value,
                message="Submit successful" if result.get("status") else "Submit failed",
                data=result,
            )

        self._recent.pop(key, None)  # DRES refused it (e.g. no running task): not scored, may resend
        error_message = resp.text
        try:
            detail_str = resp.json().get("detail")
            if detail_str and isinstance(detail_str, str):
                specific = json.loads(detail_str).get("description")
                if specific:
                    error_message = specific
        except Exception:
            try:
                error_message = resp.json().get("description") or error_message
            except Exception:
                pass
        self._log(answer, f"http-{resp.status_code}", error_message)
        logger.error(f"Submit failed ({resp.status_code}): {error_message}")
        raise DRESSubmitError(resp.status_code, error_message)
