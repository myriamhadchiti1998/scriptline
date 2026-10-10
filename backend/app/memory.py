"""Self-improvement layer: idea memory (no repeats) + learning loop.

1. Idea memory — every concept ever generated for a client is (a) shown to the
   ideation prompt so it avoids repeats, and (b) checked in code after
   generation: anything too similar to a prior concept, or to another idea in the
   same batch, is dropped before a human ever sees it. Similarity is a local
   hybrid of word-level and character-level cosine similarity — no extra API,
   deterministic, explainable, and fast enough for thousands of ideas per client.
   (An embeddings API can be swapped in behind `similarity()` without touching
   anything else.)

2. Learning loop — the human's approve/reject decisions become an "approver
   signal" fed to ideation and scoring; delivered scripts with the highest review
   scores become exemplars for the scripting stage; the checklist items past
   scripts failed most become "watch-outs". Each round starts from what the
   system has already learned instead of starting cold.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable

from . import db
from .schemas import CHECKLIST

_STOP = set("""a an the and or but if then so of to in on at for with from by as is are was were be been being it
its this that these those you your yours i me my we our they them their he him his she her not no do does did
done have has had just about into over than too very can will would should could what whats who how why when
there here one all any some more most out up down only own same s t don dont im ive youre youve thats""".split())


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("'", ""))


def _words(text: str) -> Counter:
    return Counter(w for w in _norm(text).split() if w not in _STOP and len(w) > 2)


def _grams(text: str, n: int = 4) -> Counter:
    t = " ".join(_norm(text).split())
    return Counter(t[i:i + n] for i in range(max(len(t) - n + 1, 0)))


def _cos(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def similarity(a: str, b: str) -> float:
    """0..1. ~0.15 unrelated, ~0.4 same topic, > 0.6 same concept reworded."""
    return round(0.5 * _cos(_words(a), _words(b)) + 0.5 * _cos(_grams(a), _grams(b)), 3)


def idea_signature(idea: dict) -> str:
    return f"{idea['concept_hook']} {idea['angle']}"


def nearest(sig: str, pool: Iterable[tuple[int | None, str]]) -> tuple[int | None, float]:
    best_id, best = None, 0.0
    for pid, other in pool:
        s = similarity(sig, other)
        if s > best:
            best_id, best = pid, s
    return best_id, best


# ── prompt context builders ──────────────────────────────────────────────────
def idea_memory_text(client_id: str, limit: int = 150) -> str:
    prior = db.list_ideas(client_id)[:limit]
    if not prior:
        return "IDEA MEMORY: empty — this is the first run for this client."
    lines = [f"IDEA MEMORY — {len(prior)} concepts already generated for this client. Do NOT repeat or reword any of them:"]
    for i in prior:
        lines.append(f"- [{i['status']}] ({i['target_avatar']}, {i['creative_type']}, {i['funnel_stage']}) "
                     f"{i['concept_hook']} — angle: {i['angle']}")
    return "\n".join(lines)


def approver_signal_text(client_id: str) -> str:
    decided = [i for i in db.list_ideas(client_id) if i["status"] in ("approved", "rejected")]
    if not decided:
        return "APPROVER SIGNAL: no human decisions yet."
    lines = [f"APPROVER SIGNAL — {len(decided)} past human decisions."]
    for dim in ("target_avatar", "creative_type", "lead_type", "hook_family", "funnel_stage"):
        stats: dict[str, list[int]] = {}
        for i in decided:
            s = stats.setdefault(i[dim], [0, 0])
            s[0 if i["status"] == "approved" else 1] += 1
        parts = [f"{k}: {a} approved / {r} rejected" for k, (a, r) in sorted(stats.items(), key=lambda kv: -sum(kv[1]))]
        lines.append(f"- by {dim.replace('_', ' ')}: " + "; ".join(parts))
    approved = [i for i in decided if i["status"] == "approved"][:6]
    rejected = [i for i in decided if i["status"] == "rejected"][:6]
    if approved:
        lines.append("Recently APPROVED (more like these, but new):")
        lines += [f"  + {i['concept_hook']}" for i in approved]
    if rejected:
        lines.append("Recently REJECTED (avoid these patterns):")
        lines += [f"  - {i['concept_hook']}" + (f"  [approver note: {i['decision_note']}]" if i.get("decision_note") else "")
                  for i in rejected]
    return "\n".join(lines)


def exemplars_text(client_id: str, k: int = 2, exclude_script_id: int | None = None) -> str:
    delivered = [s for s in db.list_scripts(client_id, "delivered") if s["id"] != exclude_script_id]
    delivered.sort(key=lambda s: s.get("review_score") or 0, reverse=True)
    picks = delivered[:k]
    if not picks:
        return "EXEMPLARS: none yet — this client has no delivered scripts."
    out = ["EXEMPLARS — the highest-scoring scripts already delivered for this client "
           "(match the quality bar and voice; do not reuse their lines):"]
    for s in picks:
        versions = db.list_versions(s["id"])
        content = versions[-1]["content"]
        out.append(f"\n### Exemplar (review score {s['review_score']}/5)\n"
                   f"HOOK 1: {content['hook_1']}\nPAIN: {content['body']['pain']}\nPROMISE: {content['body']['promise']}\n"
                   f"PROOF: {content['body']['proof']}\nCTA: {content['body']['cta']}")
    return "\n".join(out)


def watchouts_text(client_id: str, top: int = 3) -> str:
    fails: Counter = Counter()
    reasons: dict[int, str] = {}
    for s in db.list_scripts(client_id):
        for v in db.list_versions(s["id"]):
            review = v.get("review") or {}
            for item in review.get("items", []):
                if not item.get("passed"):
                    fails[item["id"]] += 1
                    reasons.setdefault(item["id"], item.get("summary", ""))
    if not fails:
        return "WATCH-OUTS: no recurring review failures recorded yet."
    lines = ["WATCH-OUTS — checklist items past drafts for this client failed most often:"]
    for item_id, n in fails.most_common(top):
        lines.append(f"- #{item_id} {CHECKLIST[item_id]} — failed {n}x. Example reason: {reasons[item_id]}")
    return "\n".join(lines)


def learning_snapshot(client_id: str) -> dict:
    """Numbers shown on the dashboard so the learning loop is visible."""
    ideas = db.list_ideas(client_id)
    decided = [i for i in ideas if i["status"] != "pending"]
    scripts = db.list_scripts(client_id)
    versions = [v for s in scripts for v in db.list_versions(s["id"]) if v.get("review")]
    first_pass = [v for v in versions if v["version"] == 1]
    return {
        "ideas_in_memory": len(ideas),
        "human_decisions": len(decided),
        "approval_rate": round(sum(i["status"] == "approved" for i in decided) / len(decided), 2) if decided else None,
        "exemplars_available": sum(s["status"] == "delivered" for s in scripts),
        "first_pass_rate": round(sum(bool(v["passed"]) for v in first_pass) / len(first_pass), 2) if first_pass else None,
        "watchouts": watchouts_text(client_id),
    }
