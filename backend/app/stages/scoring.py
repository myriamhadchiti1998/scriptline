"""STAGE 2 — ICE scoring (a separate AI call from ideation).

The scorer is a different prompt with a different role ("independent analyst")
so the generator never grades its own work. Scores are integers 1–10 per
dimension, each with its own written rationale, so the approver can see *why*.
"""
from __future__ import annotations

import json

from .. import memory
from ..clientcfg import ClientConfig
from ..config import settings
from ..llm import LLMError, Prompt, get_llm
from ..prompts import system_blocks
from ..schemas import ScoringOutput, scoring_schema


def _idea_card(key: str, client: ClientConfig, i: dict) -> dict:
    return {
        "idea_key": key,
        "concept_hook": i["concept_hook"],
        "creative_type": i["creative_type"],
        "angle": i["angle"],
        "lead_type": i["lead_type"],
        "hook_family": i["hook_family"],
        "target_avatar": client.avatar_label(i["target_avatar"]),
        "pain_addressed": i["pain_addressed"],
        "funnel_stage": i["funnel_stage"],
        "proof_points": {pid: client.proof_text(pid) for pid in i["proof_point_ids"]},
    }


def score(client: ClientConfig, ideas: list[dict], log) -> list[dict]:
    keyed = {f"I{n + 1}": idea for n, idea in enumerate(ideas)}
    pending = dict(keyed)
    for attempt in (1, 2):
        if not pending:
            break
        cards = [_idea_card(k, client, i) for k, i in pending.items()]
        user = (f"Score these {len(cards)} concepts. Return one entry per idea_key.\n\n"
                f"{memory.approver_signal_text(client.id)}\n\nCONCEPTS:\n{json.dumps(cards, indent=2)}")
        result = get_llm().run(Prompt(
            stage="scoring",
            system_blocks=system_blocks("scoring", client),
            user=user,
            schema=scoring_schema(client),
            model_cls=ScoringOutput,
            stage_model=settings.scoring,
            mock_context={"cards": cards},
        ))
        log(f"ICE scoring call scored {len(result.data.scores)} concepts ({result.model}, {result.seconds}s)")  # type: ignore[attr-defined]
        for s in result.data.scores:  # type: ignore[attr-defined]
            idea = pending.pop(s.idea_key, None)
            if idea is None:
                continue
            idea.update({
                "ice_impact": s.impact,
                "ice_confidence": s.confidence,
                "ice_ease": s.ease,
                "ice_total": s.total,
                "ice_reasoning": {
                    "impact": s.impact_reasoning,
                    "confidence": s.confidence_reasoning,
                    "ease": s.ease_reasoning,
                    "verdict": s.verdict,
                    "risk_flags": s.risk_flags,
                },
            })
        if pending:
            log(f"{len(pending)} concepts came back unscored; re-asking for those only", "warn")
    if pending:
        raise LLMError(f"ICE scoring failed for {len(pending)} concepts after a retry")
    return ideas
