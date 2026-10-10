"""Loads a client folder (client.yaml + reference_pack.md) into one object.

A client is pure configuration. Every stage receives a ClientConfig and nothing
in the code or prompts is specific to one client.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import settings


@dataclass(frozen=True)
class ClientConfig:
    id: str
    raw: dict[str, Any]
    reference_pack: str

    # ── convenience accessors ────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return self.raw["display_name"]

    @property
    def member_term(self) -> str:
        return self.raw.get("member_term", "members")

    @property
    def proof_bank(self) -> list[dict[str, Any]]:
        return self.raw["proof_bank"]

    @property
    def proof_ids(self) -> set[str]:
        return {p["id"] for p in self.proof_bank}

    def proof(self, pid: str) -> dict[str, Any] | None:
        return next((p for p in self.proof_bank if p["id"] == pid), None)

    def proof_text(self, pid: str) -> str:
        p = self.proof(pid)
        if not p:
            return f"[unknown proof id {pid}]"
        if p["type"] == "testimonial":
            return f'{p["person"]} ({p["descriptor"]}): "{p["quote"]}"'
        return p["text"]

    @property
    def avatars(self) -> list[dict[str, Any]]:
        return self.raw["avatars"]

    @property
    def avatar_ids(self) -> list[str]:
        return [a["id"] for a in self.avatars]

    def avatar_label(self, aid: str) -> str:
        return next((a["label"] for a in self.avatars if a["id"] == aid), aid)

    @property
    def creative_types(self) -> list[str]:
        return self.raw["creative_types"]

    @property
    def lead_types(self) -> list[str]:
        return self.raw["lead_types"]

    @property
    def hook_families(self) -> list[str]:
        return self.raw["hook_families"]

    @property
    def funnel_stages(self) -> dict[str, Any]:
        return self.raw["funnel"]["stages"]

    @property
    def facts(self) -> dict[str, Any]:
        return self.raw["facts"]

    @property
    def language_rules(self) -> list[dict[str, Any]]:
        return self.raw["language_rules"]

    @property
    def voice(self) -> dict[str, Any]:
        return self.raw["voice"]

    @property
    def script_rules(self) -> dict[str, Any]:
        return self.raw["script"]

    # ── prompt context ───────────────────────────────────────────────────────
    def structured_context(self) -> str:
        """Machine-structured client context appended to every stage prompt."""
        lines: list[str] = ["## CLIENT STRUCTURED CONTEXT", ""]
        lines.append(f"Spokesperson: {self.raw['spokesperson']} · Product: {self.raw['product']}")
        lines.append(f"Audience term: always \"{self.member_term}\".")
        lines.append(f"Landing page: {self.raw['funnel']['landing_page']} · Front-end offer: {self.raw['funnel']['front_end_offer']}")
        lines += ["", "### FUNNEL STAGES"]
        for stage, spec in self.funnel_stages.items():
            lines.append(f"- `{stage}` — {spec['description'].strip()}")
            lines.append(f"  Primary CTA: \"{spec['primary_cta']}\" · Alternates: {', '.join(repr(c) for c in spec['alternate_ctas'])}")
        lines += ["", "### AVATARS (use the id)"]
        for a in self.avatars:
            lines.append(f"- `{a['id']}` — {a['label']} · key phrase: \"{a['key_phrase']}\" · pains: {'; '.join(a['core_pains'])}")
        lines += ["", f"### CREATIVE TYPES: {', '.join(self.creative_types)}",
                  f"### LEAD TYPES: {', '.join(self.lead_types)}",
                  "### HOOK FAMILIES:", *[f"- {h}" for h in self.hook_families]]
        lines += ["", "### PROOF BANK (the ONLY usable proof — cite by ID)"]
        for p in self.proof_bank:
            lines.append(f"- **{p['id']}** [{p['type']}] {self.proof_text(p['id'])}")
        return "\n".join(lines)


@functools.lru_cache(maxsize=32)
def load_client(client_id: str) -> ClientConfig:
    folder: Path = settings.clients_dir / client_id
    if not folder.is_dir():
        raise KeyError(f"Unknown client '{client_id}'. Expected folder {folder}")
    raw = yaml.safe_load((folder / "client.yaml").read_text(encoding="utf-8"))
    pack = (folder / "reference_pack.md").read_text(encoding="utf-8")
    if raw.get("id") != client_id:
        raise ValueError(f"client.yaml id '{raw.get('id')}' does not match folder '{client_id}'")
    return ClientConfig(id=client_id, raw=raw, reference_pack=pack)


def list_clients() -> list[dict[str, str]]:
    out = []
    for folder in sorted(settings.clients_dir.iterdir()):
        if (folder / "client.yaml").exists():
            cfg = load_client(folder.name)
            out.append({"id": cfg.id, "name": cfg.name})
    return out
