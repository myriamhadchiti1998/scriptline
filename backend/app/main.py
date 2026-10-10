"""HTTP API consumed by the Next.js dashboard (and usable directly / by cron)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db, memory, pipeline, redteam
from .clientcfg import list_clients, load_client
from .config import settings
from .llm import LLMError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    pipeline.recover_on_startup()
    db.event("system", f"API started (provider={settings.llm_provider})")
    yield


app = FastAPI(title="Scriptline — AI ideation + scripting pipeline", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])


def _client(cid: str):
    try:
        return load_client(cid)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


class RunRequest(BaseModel):
    batch_size: int | None = None


class Decision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = None


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "provider": settings.llm_provider,
        "api_key_set": bool(settings.anthropic_api_key),
        "models": {s: getattr(settings, s).model for s in ("ideation", "scoring", "scripting", "review")},
        "max_revisions": settings.max_revisions,
        "pass_score": settings.review_pass_score,
    }


@app.get("/api/clients")
def clients() -> list[dict]:
    return list_clients()


@app.get("/api/clients/{cid}/summary")
def summary(cid: str) -> dict:
    _client(cid)
    ideas = db.list_ideas(cid)
    scripts = db.list_scripts(cid)
    count = lambda rows, st: sum(r["status"] == st for r in rows)  # noqa: E731
    return {
        "ideas": {s: count(ideas, s) for s in ("pending", "approved", "rejected")},
        "scripts": {s: count(scripts, s) for s in ("queued", "writing", "reviewing", "revising", "delivered", "held", "failed")},
        "runs": db.list_runs(cid, 5),
        "learning": memory.learning_snapshot(cid),
    }


@app.get("/api/clients/{cid}/proof-bank")
def proof_bank(cid: str) -> dict:
    c = _client(cid)
    return {p["id"]: {"type": p["type"], "text": c.proof_text(p["id"])} for p in c.proof_bank}


@app.get("/api/clients/{cid}/avatars")
def avatars(cid: str) -> dict:
    c = _client(cid)
    return {a["id"]: a["label"] for a in c.avatars}


@app.post("/api/clients/{cid}/runs")
def create_run(cid: str, body: RunRequest) -> dict:
    _client(cid)
    run_id = pipeline.start_ideation_run(cid, body.batch_size, trigger="dashboard")
    return {"run_id": run_id}


@app.get("/api/clients/{cid}/runs")
def runs(cid: str) -> list[dict]:
    return db.list_runs(cid, 50)


@app.get("/api/clients/{cid}/ideas")
def ideas(cid: str, status: str | None = None) -> list[dict]:
    rows = db.list_ideas(cid, status)
    for r in rows:
        s = db.get_script_by_idea(r["id"])
        r["script"] = {"id": s["id"], "status": s["status"]} if s else None
    return rows


@app.post("/api/ideas/{idea_id}/decision")
def decide(idea_id: int, body: Decision) -> dict:
    idea = db.get_idea(idea_id)
    if idea is None:
        raise HTTPException(404, "idea not found")
    if idea["status"] == "approved" and body.decision == "rejected":
        raise HTTPException(409, "idea is already approved and its script is in progress")
    return pipeline.decide(idea_id, body.decision, body.note)


def _local(path: str | None, client_id: str) -> Path | None:
    """Resolve a stored file path; fall back to this machine's output folder (e.g. a seeded database)."""
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return p
    for sub in ("delivered", "held"):
        alt = settings.output_dir / client_id / sub / p.name
        if alt.exists():
            return alt
    return None


def _script_view(s: dict, full: bool = False) -> dict:
    versions = db.list_versions(s["id"])
    latest = versions[-1] if versions else None
    out = {**s, "idea": db.get_idea(s["idea_id"]),
           "latest": latest, "version_count": len(versions)}
    out["docx_available"] = _local(s.get("docx_path"), s["client_id"]) is not None
    if full:
        out["versions"] = versions
    return out


@app.get("/api/clients/{cid}/scripts")
def scripts(cid: str, status: str | None = None) -> list[dict]:
    return [_script_view(s) for s in db.list_scripts(cid, status)]


@app.get("/api/scripts/{script_id}")
def script(script_id: int) -> dict:
    s = db.get_script(script_id)
    if s is None:
        raise HTTPException(404, "script not found")
    return _script_view(s, full=True)


@app.post("/api/scripts/{script_id}/retry")
def retry(script_id: int) -> dict:
    try:
        pipeline.retry_script(script_id)
    except KeyError as e:
        raise HTTPException(404, "script not found") from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True}


@app.get("/api/scripts/{script_id}/download")
def download(script_id: int, fmt: Literal["docx", "md"] = "docx"):
    s = db.get_script(script_id)
    if s is None:
        raise HTTPException(404, "script not found")
    path = _local(s.get("docx_path") if fmt == "docx" else s.get("md_path"), s["client_id"])
    if path is None:
        raise HTTPException(404, f"no {fmt} file for this script (status: {s['status']})")
    media = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt == "docx"
             else "text/markdown")
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/clients/{cid}/events")
def events(cid: str, limit: int = 150) -> list[dict]:
    return db.list_events(cid, limit)


@app.post("/api/clients/{cid}/gate-test")
def gate_test(cid: str) -> dict:
    try:
        return redteam.run(_client(cid))
    except LLMError as e:
        db.event("gate", f"Gate red-team could not run: {e}", client_id=cid, level="error")
        raise HTTPException(502, f"AI reviewer unavailable: {e}") from e
