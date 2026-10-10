"""SQLite store: ideas, approval state, scripts, review history, and an event log.

Why SQLite: zero setup for the reviewer, ACID transactions for the approval
handoff (an idea can only be approved once → exactly one script job), and it is
the same SQL that would move to Postgres for multi-client production volume.
Every row carries `client_id`, so many clients share one store.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import settings

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',          -- running | completed | failed
    trigger TEXT NOT NULL DEFAULT 'dashboard',       -- dashboard | api | cli | schedule
    batch_size INTEGER NOT NULL,
    generated INTEGER DEFAULT 0,
    kept INTEGER DEFAULT 0,
    duplicates_dropped INTEGER DEFAULT 0,
    invalid_dropped INTEGER DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    client_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',          -- pending | approved | rejected
    concept_hook TEXT NOT NULL,
    creative_type TEXT NOT NULL,
    angle TEXT NOT NULL,
    lead_type TEXT NOT NULL,
    hook_family TEXT NOT NULL,
    proof_point_ids TEXT NOT NULL,                   -- JSON list of proof-bank IDs
    target_avatar TEXT NOT NULL,
    pain_addressed TEXT NOT NULL,
    funnel_stage TEXT NOT NULL,
    strategist_note TEXT,
    ice_impact INTEGER,
    ice_confidence INTEGER,
    ice_ease INTEGER,
    ice_total REAL,
    ice_reasoning TEXT,                              -- JSON: per-dimension reasoning, verdict, risk flags
    nearest_prior_id INTEGER,                        -- idea memory: closest earlier concept
    nearest_prior_similarity REAL,
    decision_note TEXT,
    decided_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ideas_client_status ON ideas(client_id, status);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id INTEGER NOT NULL UNIQUE REFERENCES ideas(id),   -- one script per approved idea (idempotent trigger)
    client_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',           -- queued | writing | reviewing | revising | delivered | held | failed
    current_version INTEGER DEFAULT 0,
    review_score REAL,
    docx_path TEXT,
    md_path TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS scripts_client_status ON scripts(client_id, status);

CREATE TABLE IF NOT EXISTS script_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL REFERENCES scripts(id),
    version INTEGER NOT NULL,
    content TEXT NOT NULL,                           -- JSON ScriptDraft
    review TEXT,                                     -- JSON review report
    passed INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(script_id, version)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    client_id TEXT,
    kind TEXT NOT NULL,                              -- run | idea | script | gate | system
    ref_id INTEGER,
    level TEXT NOT NULL DEFAULT 'info',              -- info | success | warn | error
    message TEXT NOT NULL,
    meta TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init() -> None:
    with tx() as c:
        c.executescript(SCHEMA)


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r else None


# ── events ───────────────────────────────────────────────────────────────────
def event(kind: str, message: str, *, client_id: str | None = None, ref_id: int | None = None,
          level: str = "info", meta: dict | None = None) -> None:
    with tx() as c:
        c.execute("INSERT INTO events(ts, client_id, kind, ref_id, level, message, meta) VALUES (?,?,?,?,?,?,?)",
                  (now(), client_id, kind, ref_id, level, message, json.dumps(meta) if meta else None))


def list_events(client_id: str, limit: int = 200) -> list[dict]:
    with tx() as c:
        rows = c.execute("SELECT * FROM events WHERE client_id = ? OR client_id IS NULL ORDER BY id DESC LIMIT ?",
                         (client_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ── runs ─────────────────────────────────────────────────────────────────────
def create_run(client_id: str, batch_size: int, trigger: str) -> int:
    with tx() as c:
        cur = c.execute("INSERT INTO runs(client_id, batch_size, trigger, created_at) VALUES (?,?,?,?)",
                        (client_id, batch_size, trigger, now()))
        return int(cur.lastrowid)


def update_run(run_id: int, **fields: Any) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with tx() as c:
        c.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))


def get_run(run_id: int) -> dict | None:
    with tx() as c:
        return _row(c.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())


def list_runs(client_id: str, limit: int = 20) -> list[dict]:
    with tx() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM runs WHERE client_id = ? ORDER BY id DESC LIMIT ?", (client_id, limit)).fetchall()]


# ── ideas ────────────────────────────────────────────────────────────────────
IDEA_JSON_FIELDS = ("proof_point_ids", "ice_reasoning")


def _idea(r: sqlite3.Row | dict | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in IDEA_JSON_FIELDS:
        if d.get(k):
            d[k] = json.loads(d[k])
    return d


def insert_idea(run_id: int, client_id: str, idea: dict) -> int:
    with tx() as c:
        cur = c.execute(
            """INSERT INTO ideas(run_id, client_id, concept_hook, creative_type, angle, lead_type, hook_family,
                   proof_point_ids, target_avatar, pain_addressed, funnel_stage, strategist_note,
                   ice_impact, ice_confidence, ice_ease, ice_total, ice_reasoning,
                   nearest_prior_id, nearest_prior_similarity, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, client_id, idea["concept_hook"], idea["creative_type"], idea["angle"], idea["lead_type"],
             idea["hook_family"], json.dumps(idea["proof_point_ids"]), idea["target_avatar"],
             idea["pain_addressed"], idea["funnel_stage"], idea.get("strategist_note", ""),
             idea.get("ice_impact"), idea.get("ice_confidence"), idea.get("ice_ease"), idea.get("ice_total"),
             json.dumps(idea.get("ice_reasoning")) if idea.get("ice_reasoning") else None,
             idea.get("nearest_prior_id"), idea.get("nearest_prior_similarity"), now()))
        return int(cur.lastrowid)


def get_idea(idea_id: int) -> dict | None:
    with tx() as c:
        return _idea(c.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone())


def list_ideas(client_id: str, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM ideas WHERE client_id = ?"
    args: list[Any] = [client_id]
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY run_id DESC, ice_total DESC, id ASC"
    with tx() as c:
        return [_idea(r) for r in c.execute(q, args).fetchall()]  # type: ignore[misc]


def decide_idea(idea_id: int, decision: str, note: str | None) -> tuple[dict, bool]:
    """Atomically record the human decision.

    Returns (idea, should_trigger_script). The script row is created inside the
    same transaction as the approval, so a double-click or a retried request can
    never create two scripts for one idea.
    """
    assert decision in ("approved", "rejected")
    with tx() as c:
        row = c.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        if row is None:
            raise KeyError(idea_id)
        if row["status"] == "approved":
            return _idea(row), False  # type: ignore[return-value]  # already approved → idempotent no-op
        c.execute("UPDATE ideas SET status = ?, decision_note = ?, decided_at = ? WHERE id = ?",
                  (decision, note, now(), idea_id))
        trigger = False
        if decision == "approved":
            cur = c.execute("INSERT OR IGNORE INTO scripts(idea_id, client_id, created_at, updated_at) VALUES (?,?,?,?)",
                            (idea_id, row["client_id"], now(), now()))
            trigger = cur.rowcount == 1
        updated = c.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        return _idea(updated), trigger  # type: ignore[return-value]


# ── scripts ──────────────────────────────────────────────────────────────────
def get_script_by_idea(idea_id: int) -> dict | None:
    with tx() as c:
        return _row(c.execute("SELECT * FROM scripts WHERE idea_id = ?", (idea_id,)).fetchone())


def get_script(script_id: int) -> dict | None:
    with tx() as c:
        return _row(c.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone())


def update_script(script_id: int, **fields: Any) -> None:
    fields["updated_at"] = now()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with tx() as c:
        c.execute(f"UPDATE scripts SET {cols} WHERE id = ?", (*fields.values(), script_id))


def add_version(script_id: int, version: int, content: dict, review: dict | None, passed: bool | None) -> None:
    with tx() as c:
        c.execute("""INSERT OR REPLACE INTO script_versions(script_id, version, content, review, passed, created_at)
                     VALUES (?,?,?,?,?,?)""",
                  (script_id, version, json.dumps(content), json.dumps(review) if review else None,
                   None if passed is None else int(passed), now()))


def list_versions(script_id: int) -> list[dict]:
    with tx() as c:
        rows = c.execute("SELECT * FROM script_versions WHERE script_id = ? ORDER BY version", (script_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["content"] = json.loads(d["content"])
        d["review"] = json.loads(d["review"]) if d["review"] else None
        out.append(d)
    return out


def list_scripts(client_id: str, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM scripts WHERE client_id = ?"
    args: list[Any] = [client_id]
    if status:
        q += " AND status = ?"
        args.append(status)
    q += " ORDER BY id DESC"
    with tx() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def unfinished_scripts() -> list[dict]:
    with tx() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM scripts WHERE status IN ('queued','writing','reviewing','revising')").fetchall()]


def mark_interrupted_runs() -> int:
    with tx() as c:
        cur = c.execute("UPDATE runs SET status='failed', error='interrupted by restart', finished_at=? "
                        "WHERE status='running'", (now(),))
        return cur.rowcount
