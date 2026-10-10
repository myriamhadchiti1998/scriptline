"""Gate red-team: push the client's own known-bad scripts through the real
quality gate and prove they are held.

The Reference Pack ships three losing scripts (§09). They are placed into the
required skeleton exactly as written and reviewed by BOTH gate layers. A healthy
gate holds all three; the report shows which layer caught what.
"""
from __future__ import annotations

import re

from . import db
from .clientcfg import ClientConfig
from .schemas import OpenLoop, ScriptBody, ScriptDraft
from .stages import review
from .stages.review import sentences

LOSING_RE = re.compile(r"Losing Script (\d+) — ([^\n]+?)\.\s*\n\s*\"(.+?)\"\s*\n", re.S)


def losing_scripts(client: ClientConfig) -> list[dict]:
    return [{"n": int(n), "title": t.strip(), "text": body.strip()} for n, t, body in LOSING_RE.findall(client.reference_pack)]


def to_draft(title: str, text: str) -> ScriptDraft:
    s = sentences(text)
    pad = s + ["(missing)"] * max(0, 7 - len(s))
    return ScriptDraft(
        title=title,
        production_notes=[],
        hook_1=pad[0], hook_2=pad[1], hook_3=pad[2],
        body=ScriptBody(pain=" ".join(s[3:]) or "(missing)", promise="(missing)", proof="(missing)", cta="(missing)"),
        open_loop=OpenLoop(opened_with="", closed_with=""),
        claims=[],
    )


def run(client: ClientConfig) -> dict:
    idea = {"concept_hook": "red-team", "creative_type": "talking-head", "angle": "n/a", "lead_type": "problem-led",
            "target_avatar": client.avatar_ids[0], "pain_addressed": "n/a", "funnel_stage": "cold", "proof_point_ids": []}
    results = []
    for ls in losing_scripts(client):
        draft = to_draft(f"Losing Script {ls['n']} — {ls['title']}", ls["text"])
        report = review.review(client, idea, draft)
        caught_by_code = sorted({f["item"] for it in report["items"] for f in it["code_checks"] if f["level"] == "hard"})
        results.append({
            "script": draft.title,
            "text": ls["text"],
            "held": not report["passed"],
            "failed_items": report["failed_items"],
            "caught_by_code_items": caught_by_code,
            # compliance (voice #7, fabrication #8) first — those are the failures that matter for this client
            "top_reasons": [f"#{it['id']} {r}" for it in sorted(report["items"], key=lambda i: (i["id"] not in (7, 8), i["id"]))
                            if not it["passed"] for r in it["fail_reasons"] if not r.startswith("AI reviewer")][:10],
        })
    ok = all(r["held"] for r in results) and bool(results)
    db.event("gate", f"Gate red-team: {sum(r['held'] for r in results)}/{len(results)} known-bad scripts held"
                     + (" ✔" if ok else " — GATE LEAK"), client_id=client.id, level="success" if ok else "error")
    return {"all_held": ok, "results": results}
