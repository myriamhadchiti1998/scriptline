"""STAGE 1 — Idea generation (AI call #1, its own prompt and purpose).

Generates a batch of structured concepts from the Reference Pack, then applies
code-level guards before anything is stored:
  • every field validated against the client's enums (avatars, types, proof IDs)
  • hard compliance language in a concept → dropped
  • procedural/mechanism hooks on cold traffic → dropped (pack §07 rule)
  • near-duplicates of past concepts (idea memory) or of each other → dropped
If guards drop too much, one top-up call asks for replacements.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import db, memory
from ..clientcfg import ClientConfig
from ..config import settings
from ..llm import Prompt, get_llm
from ..prompts import system_blocks
from ..schemas import IdeationOutput, ideation_schema
from .review import scan_language


@dataclass
class IdeationStats:
    generated: int = 0
    kept: int = 0
    duplicates_dropped: int = 0
    invalid_dropped: int = 0
    calls: int = 0
    notes: list[str] = field(default_factory=list)


def _user_message(client: ClientConfig, n: int, extra_memory: list[dict]) -> str:
    parts = [
        f"Generate {n} new, distinct video ad concepts for this client.",
        "",
        memory.idea_memory_text(client.id),
    ]
    if extra_memory:
        parts.append("Also already accepted in THIS batch (do not repeat):")
        parts += [f"- ({i['target_avatar']}, {i['creative_type']}) {i['concept_hook']}" for i in extra_memory]
    parts += ["", memory.approver_signal_text(client.id), "",
              f"Return exactly {n} ideas. Every idea must cite proof_point_ids from the PROOF BANK only."]
    return "\n".join(parts)


def _invalid_reason(client: ClientConfig, idea: dict) -> str | None:
    if idea["target_avatar"] not in client.avatar_ids:
        return f"unknown avatar {idea['target_avatar']}"
    if idea["creative_type"] not in client.creative_types:
        return f"unknown creative type {idea['creative_type']}"
    if idea["lead_type"] not in client.lead_types:
        return f"unknown lead type {idea['lead_type']}"
    bad = [p for p in idea["proof_point_ids"] if p not in client.proof_ids]
    if bad:
        return f"proof IDs not in proof bank: {bad}"
    if idea["funnel_stage"] == "cold" and idea["hook_family"].lower().startswith("mechanism"):
        return "procedural/mechanism hook on cold traffic (Reference Pack §07)"
    if idea["creative_type"] == "UGC" and not any(p.startswith("T") for p in idea["proof_point_ids"]):
        return "UGC concept without a real proof-bank testimonial"
    hard = [f for f in scan_language(client, f"{idea['concept_hook']} {idea['angle']}") if f["level"] == "hard"]
    if hard:
        return f"compliance: {hard[0]['message']}"
    return None


def generate(client: ClientConfig, batch_size: int, log) -> tuple[list[dict], IdeationStats]:
    stats = IdeationStats()
    prior = [(i["id"], memory.idea_signature(i)) for i in db.list_ideas(client.id)]
    kept: list[dict] = []

    for attempt in (1, 2):  # main call + at most one top-up
        need = batch_size - len(kept)
        if need <= 0 or (attempt == 2 and len(kept) >= max(1, int(batch_size * 0.75))):
            break
        if attempt == 2:
            log(f"Guards dropped too many ideas; requesting {need} replacements", "warn")
        result = get_llm().run(Prompt(
            stage="ideation",
            system_blocks=system_blocks("ideation", client),
            user=_user_message(client, need, kept),
            schema=ideation_schema(client),
            model_cls=IdeationOutput,
            stage_model=settings.ideation,
            mock_context={"client": client, "n": need, "attempt": attempt},
        ))
        stats.calls += 1
        drafts = [d.model_dump() for d in result.data.ideas]  # type: ignore[attr-defined]
        stats.generated += len(drafts)
        log(f"Ideation call returned {len(drafts)} concepts ({result.model}, {result.seconds}s, "
            f"{result.usage.get('cache_read_input_tokens', 0)} cached tokens)")

        for d in drafts:
            reason = _invalid_reason(client, d)
            if reason:
                stats.invalid_dropped += 1
                log(f"Dropped invalid concept: {reason} — “{d['concept_hook'][:70]}”", "warn")
                continue
            sig = memory.idea_signature(d)
            prior_id, prior_sim = memory.nearest(sig, prior)
            _, batch_sim = memory.nearest(sig, [(None, memory.idea_signature(k)) for k in kept])
            if max(prior_sim, batch_sim) >= settings.duplicate_threshold:
                stats.duplicates_dropped += 1
                where = f"idea #{prior_id}" if prior_sim >= batch_sim else "another idea in this batch"
                log(f"Dropped near-duplicate of {where} (similarity {max(prior_sim, batch_sim):.2f}) — "
                    f"“{d['concept_hook'][:70]}”", "warn")
                continue
            d["nearest_prior_id"] = prior_id
            d["nearest_prior_similarity"] = prior_sim if prior_id else None
            kept.append(d)
            if len(kept) >= batch_size:
                break

    stats.kept = len(kept)
    return kept, stats
