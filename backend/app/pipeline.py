"""Orchestration: the two triggers and everything they set in motion.

TRIGGER 1  start_ideation_run()  — dashboard button / POST /api/runs / CLI / cron
           → Stage 1 ideation → guards + idea memory → Stage 2 ICE scoring
           → ideas stored as `pending` (the human approval gate)

TRIGGER 2  decide()  — the human clicks Approve on an idea
           → script row created atomically → background job:
             Stage 5 scripting → Stage 6 review gate
               pass → Stage 7 delivery (.docx + .md)              → `delivered`
               fail → one automatic revision with the failure report → re-review
                      still failing                                → `held`
Jobs run on a small worker pool; state lives in SQLite, so a restart resumes
any unfinished script job instead of losing it.
"""
from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from . import db
from .clientcfg import ClientConfig, load_client
from .config import settings
from .llm import LLMError
from .schemas import ScriptDraft
from .stages import delivery, ideation, review, scoring, scripting

log = logging.getLogger("scriptline.pipeline")
_pool = ThreadPoolExecutor(max_workers=max(1, settings.script_workers), thread_name_prefix="pipeline")


def _logger(kind: str, client_id: str, ref_id: int | None) -> Callable[..., None]:
    def emit(message: str, level: str = "info", meta: dict | None = None) -> None:
        log.info("[%s %s] %s", kind, ref_id, message)
        db.event(kind, message, client_id=client_id, ref_id=ref_id, level=level, meta=meta)
    return emit


# ── TRIGGER 1: ideation run ──────────────────────────────────────────────────
def start_ideation_run(client_id: str, batch_size: int | None = None, trigger: str = "dashboard",
                       background: bool = True) -> int:
    client = load_client(client_id)
    n = max(1, min(int(batch_size or settings.batch_size), 30))
    run_id = db.create_run(client.id, n, trigger)
    db.event("run", f"Run #{run_id} started via {trigger}: generating {n} concepts", client_id=client.id, ref_id=run_id)
    if background:
        _pool.submit(_safe_run, client, run_id, n)
    else:
        _safe_run(client, run_id, n)
    return run_id


def _safe_run(client: ClientConfig, run_id: int, n: int) -> None:
    emit = _logger("run", client.id, run_id)
    try:
        ideas, stats = ideation.generate(client, n, emit)
        if not ideas:
            raise LLMError("ideation produced no usable concepts after guards")
        emit(f"Stage 1 complete: {stats.kept} kept · {stats.duplicates_dropped} duplicates dropped · "
             f"{stats.invalid_dropped} invalid dropped")
        scoring.score(client, ideas, emit)
        for idea in sorted(ideas, key=lambda i: -i["ice_total"]):
            db.insert_idea(run_id, client.id, idea)
        db.update_run(run_id, status="completed", generated=stats.generated, kept=stats.kept,
                      duplicates_dropped=stats.duplicates_dropped, invalid_dropped=stats.invalid_dropped,
                      finished_at=db.now())
        emit(f"Run #{run_id} complete: {len(ideas)} scored concepts are waiting for approval", "success")
    except Exception as e:  # noqa: BLE001 — every failure is recorded, never silent
        db.update_run(run_id, status="failed", error=str(e)[:500], finished_at=db.now())
        emit(f"Run #{run_id} failed: {e}", "error", {"traceback": traceback.format_exc()[-2000:]})


# ── TRIGGER 2: human decision ────────────────────────────────────────────────
def decide(idea_id: int, decision: str, note: str | None = None, background: bool = True) -> dict:
    idea, should_trigger = db.decide_idea(idea_id, decision, note)
    emit = _logger("idea", idea["client_id"], idea_id)
    if decision == "approved" and idea["status"] == "approved" and not should_trigger:
        emit("Approval received again — script already exists, ignoring duplicate trigger", "warn")
    elif decision == "approved":
        emit(f"Idea #{idea_id} APPROVED by human → script generation triggered", "success")
    else:
        emit(f"Idea #{idea_id} rejected" + (f": {note}" if note else ""))
    if should_trigger:
        script = db.get_script_by_idea(idea_id)
        enqueue_script(script["id"], background=background)
    return idea


def enqueue_script(script_id: int, background: bool = True) -> None:
    if background:
        _pool.submit(process_script, script_id)
    else:
        process_script(script_id)


def process_script(script_id: int) -> None:
    script = db.get_script(script_id)
    idea = db.get_idea(script["idea_id"])
    client = load_client(script["client_id"])
    emit = _logger("script", client.id, script_id)
    try:
        previous: ScriptDraft | None = None
        previous_review: dict | None = None
        max_versions = 1 + max(0, settings.max_revisions)
        for version in range(1, max_versions + 1):
            db.update_script(script_id, status="writing" if version == 1 else "revising", current_version=version, error=None)
            emit(f"Stage 5: writing script v{version} for idea #{idea['id']}" + (" (revision)" if previous else ""))
            draft = scripting.write(client, idea, script_id=script_id,
                                    previous=previous.model_dump() if previous else None,
                                    previous_review=previous_review, log=emit)
            db.add_version(script_id, version, draft.model_dump(), None, None)

            db.update_script(script_id, status="reviewing")
            emit(f"Stage 6: quality gate reviewing v{version} (10-point checklist + voice)")
            report = review.review(client, idea, draft, log=emit)
            db.add_version(script_id, version, draft.model_dump(), report, report["passed"])

            if report["passed"]:
                docx_path, md_path = delivery.deliver(client, idea, script_id, draft, report)
                db.update_script(script_id, status="delivered", review_score=report["score"],
                                 docx_path=docx_path, md_path=md_path)
                emit(f"PASSED 10/10 (score {report['score']}/5) → delivered as .docx + .md", "success",
                     {"docx": docx_path, "md": md_path})
                return
            emit(f"v{version} FAILED items {report['failed_items']} — "
                 + "; ".join(i["summary"] for i in report["items"] if not i["passed"])[:400], "warn")
            previous, previous_review = draft, report

        hold_path = delivery.write_hold_report(client, idea, script_id, previous, previous_review)  # type: ignore[arg-type]
        db.update_script(script_id, status="held", review_score=previous_review["score"], md_path=hold_path)  # type: ignore[index]
        emit(f"HELD after {max_versions} attempt(s): still failing items {previous_review['failed_items']}. "  # type: ignore[index]
             "Not delivered.", "error")
    except Exception as e:  # noqa: BLE001
        db.update_script(script_id, status="failed", error=str(e)[:500])
        emit(f"Script job failed: {e}", "error", {"traceback": traceback.format_exc()[-2000:]})


def retry_script(script_id: int) -> None:
    script = db.get_script(script_id)
    if script is None:
        raise KeyError(script_id)
    if script["status"] not in ("failed", "held"):
        raise ValueError(f"script #{script_id} is {script['status']}; only failed or held scripts can be retried")
    db.update_script(script_id, status="queued", error=None)
    db.event("script", f"Script #{script_id} re-queued by user", client_id=script["client_id"], ref_id=script_id)
    enqueue_script(script_id)


def recover_on_startup() -> None:
    """Resume work interrupted by a crash or restart."""
    n_runs = db.mark_interrupted_runs()
    pending = db.unfinished_scripts()
    for s in pending:
        db.event("system", f"Resuming script #{s['id']} after restart", client_id=s["client_id"], ref_id=s["id"], level="warn")
        enqueue_script(s["id"])
    if n_runs or pending:
        log.warning("Recovered %s interrupted runs, resumed %s script jobs", n_runs, len(pending))
