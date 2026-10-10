"""Prompt assembly. Prompts live as Markdown files in backend/prompts/ so a
strategist can edit them without touching code."""
from __future__ import annotations

import functools
import re

from .clientcfg import ClientConfig
from .config import settings

PROMPT_FILES = {
    "ideation": "1_ideation.md",
    "scoring": "2_ice_scoring.md",
    "scripting": "3_scripting.md",
    "review": "4_quality_review.md",
}


@functools.lru_cache(maxsize=8)
def _template(stage: str) -> str:
    return (settings.prompts_dir / PROMPT_FILES[stage]).read_text(encoding="utf-8")


@functools.lru_cache(maxsize=1)
def _playbook() -> str:
    return (settings.knowledge_dir / "craft_playbook.md").read_text(encoding="utf-8")


def render(stage: str, client: ClientConfig) -> str:
    sr = client.script_rules
    values = {
        "client_name": client.name,
        "client_context": client.structured_context(),
        "member_term": client.member_term,
        "hook_max_words": sr["hook_first_sentence_max_words"],
        "target_words_min": sr["target_words"][0],
        "target_words_max": sr["target_words"][1],
        "min_seconds": sr["min_seconds"],
        "max_seconds": sr["max_seconds"],
        "pass_score": settings.review_pass_score,
    }
    text = _template(stage)
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    leftover = re.findall(r"\{\{(\w+)\}\}", text)
    if leftover:
        raise ValueError(f"Unfilled prompt placeholders in {stage}: {leftover}")
    return text


def system_blocks(stage: str, client: ClientConfig) -> list[str]:
    """Stable, cacheable prefix: stage instructions → craft playbook → Reference Pack."""
    return [
        render(stage, client),
        "# CRAFT PLAYBOOK (client-agnostic technique — never a source of client facts)\n\n" + _playbook(),
        "# CLIENT REFERENCE PACK (single source of truth for every client fact)\n\n" + client.reference_pack,
    ]
