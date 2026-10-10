"""STAGE 5 — Script generation (AI call #2 of the two generation stages).

Separate prompt, separate purpose: it receives ONE approved idea record (all
fields + ICE + the full text of every cited proof point) plus the full client
context, the learning-loop inputs (exemplars + watch-outs), and — on a
revision — the reviewer's failure report for the previous draft.
"""
from __future__ import annotations

import json

from .. import memory
from ..clientcfg import ClientConfig
from ..config import settings
from ..llm import Prompt, get_llm
from ..prompts import system_blocks
from ..schemas import ScriptDraft, scripting_schema


def _idea_record(client: ClientConfig, idea: dict) -> dict:
    stage = client.funnel_stages[idea["funnel_stage"]]
    return {
        "idea_id": idea["id"],
        "concept_hook": idea["concept_hook"],
        "creative_type": idea["creative_type"],
        "angle": idea["angle"],
        "lead_type": idea["lead_type"],
        "hook_family": idea["hook_family"],
        "target_avatar": client.avatar_label(idea["target_avatar"]),
        "pain_addressed": idea["pain_addressed"],
        "funnel_stage": idea["funnel_stage"],
        "funnel_stage_rules": stage["description"].strip(),
        "primary_cta": stage["primary_cta"],
        "alternate_ctas": stage["alternate_ctas"],
        "supporting_proof": {pid: client.proof_text(pid) for pid in idea["proof_point_ids"]},
        "ice": {"impact": idea.get("ice_impact"), "confidence": idea.get("ice_confidence"),
                "ease": idea.get("ice_ease"), "reasoning": idea.get("ice_reasoning")},
        "approver_note": idea.get("decision_note") or "",
    }


def _revision_block(previous: dict, review: dict) -> str:
    failures = [f"- #{i['id']} {i['name']}: " + " | ".join(i["fail_reasons"]) for i in review["items"] if not i["passed"]]
    return ("REVISION REQUEST — the previous draft below FAILED the quality gate and was held.\n"
            "Fix every failure, keep what passed, and return a complete new script.\n\n"
            "FAILURES:\n" + "\n".join(failures) +
            f"\n\nREVIEWER'S TOP FIX: {review.get('top_fix', '')}\n\n"
            f"PREVIOUS DRAFT (JSON):\n{json.dumps(previous, indent=2)}")


def write(client: ClientConfig, idea: dict, *, script_id: int | None = None,
          previous: dict | None = None, previous_review: dict | None = None, log=None) -> ScriptDraft:
    parts = [
        "Write the full script for this APPROVED concept.",
        "",
        "APPROVED IDEA RECORD:",
        json.dumps(_idea_record(client, idea), indent=2),
        "",
        "You may use any proof-bank item that fits (not only the supporting proof above), "
        "but every claim must be listed in `claims` with its proof ID.",
        "",
        memory.exemplars_text(client.id, exclude_script_id=script_id),
        "",
        memory.watchouts_text(client.id),
    ]
    if previous and previous_review:
        parts += ["", _revision_block(previous, previous_review)]
    result = get_llm().run(Prompt(
        stage="scripting",
        system_blocks=system_blocks("scripting", client),
        user="\n".join(parts),
        schema=scripting_schema(client),
        model_cls=ScriptDraft,
        stage_model=settings.scripting,
        mock_context={"client": client, "idea": idea, "revision": bool(previous)},
    ))
    if log:
        log(f"Script drafted ({result.model}, {result.seconds}s, attempt {result.attempts})")
    return result.data  # type: ignore[return-value]
