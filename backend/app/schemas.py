"""Output contracts for every AI stage.

Two layers, on purpose:
1. JSON Schemas sent to the API as structured outputs (`output_config.format`).
   They are built per client, so enums (proof IDs, avatars, creative types) are
   enforced by constrained decoding: the model cannot emit a proof ID that is not
   in the proof bank.
2. Pydantic models that re-validate everything in code (ranges, counts, non-empty
   text), because the API's schema subset cannot express min/max constraints.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .clientcfg import ClientConfig

FUNNEL_STAGES = ["cold", "retargeting"]
INTERRUPT_TYPES = ["contrarian-admission", "private-thought-callout", "unexpected-specific",
                   "direct-challenge", "mid-story-open", "implicating-question"]


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _int(desc: str) -> dict:
    return {"type": "integer", "description": desc}


def _enum(values: list[str], desc: str = "") -> dict:
    return {"type": "string", "enum": values, "description": desc}


# ── Stage 1: ideation ────────────────────────────────────────────────────────
def ideation_schema(c: ClientConfig) -> dict:
    idea = _obj({
        "concept_hook": _str("The opening concept / draft hook line, in the client's voice."),
        "creative_type": _enum(c.creative_types),
        "angle": _str("The persuasion angle, one sentence."),
        "lead_type": _enum(c.lead_types),
        "hook_family": _enum(c.hook_families),
        "proof_point_ids": {"type": "array", "minItems": 1, "items": _enum(sorted(c.proof_ids)),
                            "description": "1-3 proof bank IDs that support this concept."},
        "target_avatar": _enum(c.avatar_ids),
        "pain_addressed": _str("The specific pain or limiting belief from the Reference Pack."),
        "funnel_stage": _enum(FUNNEL_STAGES),
        "strategist_note": _str("One sentence: why this should work for this avatar."),
    })
    return _obj({"ideas": {"type": "array", "minItems": 1, "items": idea}})


class IdeaDraft(BaseModel):
    concept_hook: str = Field(min_length=10)
    creative_type: str
    angle: str = Field(min_length=5)
    lead_type: str
    hook_family: str
    proof_point_ids: list[str] = Field(min_length=1, max_length=4)
    target_avatar: str
    pain_addressed: str = Field(min_length=3)
    funnel_stage: Literal["cold", "retargeting"]
    strategist_note: str = ""


class IdeationOutput(BaseModel):
    ideas: list[IdeaDraft] = Field(min_length=1)


# ── Stage 2: ICE scoring ─────────────────────────────────────────────────────
def scoring_schema(_: ClientConfig) -> dict:
    row = _obj({
        "idea_key": _str("The key of the concept being scored, exactly as given."),
        "impact": _int("1-10"),
        "impact_reasoning": _str("1-2 sentences citing evidence."),
        "confidence": _int("1-10"),
        "confidence_reasoning": _str("1-2 sentences citing evidence."),
        "ease": _int("1-10"),
        "ease_reasoning": _str("1-2 sentences citing evidence."),
        "verdict": _str("One line the approver can read in three seconds."),
        "risk_flags": {"type": "array", "items": {"type": "string"}},
    })
    return _obj({"scores": {"type": "array", "minItems": 1, "items": row}})


class IceScore(BaseModel):
    idea_key: str
    impact: int = Field(ge=1, le=10)
    impact_reasoning: str = Field(min_length=5)
    confidence: int = Field(ge=1, le=10)
    confidence_reasoning: str = Field(min_length=5)
    ease: int = Field(ge=1, le=10)
    ease_reasoning: str = Field(min_length=5)
    verdict: str = Field(min_length=3)
    risk_flags: list[str] = []

    @property
    def total(self) -> float:
        return round((self.impact + self.confidence + self.ease) / 3, 1)


class ScoringOutput(BaseModel):
    scores: list[IceScore] = Field(min_length=1)


# ── Stage 3: scripting ───────────────────────────────────────────────────────
def scripting_schema(c: ClientConfig) -> dict:
    return _obj({
        "title": _str("Short internal working title for the script."),
        "production_notes": {"type": "array", "items": {"type": "string"},
                             "description": "Helper notes for the videographer: setting, B-roll, on-screen text, pace."},
        "hook_plan": {"type": "array", "minItems": 1, "items": _obj({
            "hook": _enum(["hook_1", "hook_2", "hook_3"]),
            "interrupt_type": _enum(INTERRUPT_TYPES),
            "door": _str("The distinct emotional entry this hook uses, in a few words."),
        }), "description": "Plan BEFORE writing: one entry per hook, three different interrupt types and doors."},
        "hook_1": _str("Pattern-interrupt opening; first sentence lands in 3 seconds."),
        "hook_2": _str("A different angle on the same idea."),
        "hook_3": _str("A third distinct option."),
        "body": _obj({
            "pain": _str("PAIN section of the main body."),
            "promise": _str("PROMISE section: reframe + unique mechanism."),
            "proof": _str("PROOF section: checkable proof-bank elements only."),
            "cta": _str("CTA matched to the funnel stage."),
        }),
        "open_loop": _obj({
            "opened_with": _str("The exact line that opens the loop."),
            "closed_with": _str("The exact line that closes it."),
        }),
        "claims": {"type": "array", "minItems": 1, "items": _obj({
            "claim": _str("A factual statement made in the script."),
            "proof_id": _enum(sorted(c.proof_ids)),
        }), "description": "Every factual claim in the script with the proof ID it relies on."},
    })


class ScriptBody(BaseModel):
    # Lengths are judged by the review gate (item 10), not rejected at parse time.
    pain: str = Field(min_length=1)
    promise: str = Field(min_length=1)
    proof: str = Field(min_length=1)
    cta: str = Field(min_length=1)


class OpenLoop(BaseModel):
    opened_with: str
    closed_with: str


class HookPlan(BaseModel):
    hook: str
    interrupt_type: str
    door: str


class Claim(BaseModel):
    claim: str
    proof_id: str


class ScriptDraft(BaseModel):
    title: str
    production_notes: list[str] = []
    hook_plan: list[HookPlan] = []
    hook_1: str = Field(min_length=1)
    hook_2: str = Field(min_length=1)
    hook_3: str = Field(min_length=1)
    body: ScriptBody
    open_loop: OpenLoop
    claims: list[Claim] = []  # emptiness is a hard fail in the review gate, not a parse error

    @property
    def hooks(self) -> list[str]:
        return [self.hook_1, self.hook_2, self.hook_3]

    def body_text(self) -> str:
        b = self.body
        return "\n\n".join([b.pain, b.promise, b.proof, b.cta])

    def spoken_text(self) -> str:
        return "\n\n".join([*self.hooks, self.body_text()])


# ── Stage 4: quality review (AI judge half) ──────────────────────────────────
def review_schema(c: ClientConfig) -> dict:
    return _obj({
        "items": {"type": "array", "minItems": 1, "items": _obj({
            "id": _int("Checklist item number 1-10."),
            "score": _int("1-5 against the anchors."),
            "evidence": _str("Short exact quote from the script, or 'none found'."),
            "reasoning": _str("One or two sentences."),
        })},
        "voice": _obj({
            "plainspoken": _int("1-5"),
            "unhurried_rhythm": _int("1-5"),
            "operational_specificity": _int("1-5"),
            "anti_hype": _int("1-5"),
            "avatar_language": _int("1-5"),
            "notes": _str("One or two sentences on voice/rhythm."),
        }),
        "claim_audit": {"type": "array", "items": _obj({
            "claim": _str("A factual statement found in the script."),
            "proof_id": _enum(sorted(c.proof_ids) + ["UNSUPPORTED"]),
        })},
        "flag_rulings": {"type": "array", "items": _obj({
            "phrase": _str("The flagged phrase."),
            "acceptable": {"type": "boolean"},
            "reason": _str("Why, in context."),
        })},
        "top_fix": _str("The single most important change, as an instruction to the writer."),
    })


class ReviewItem(BaseModel):
    id: int = Field(ge=1, le=10)
    score: int = Field(ge=1, le=5)
    evidence: str
    reasoning: str


class VoiceScores(BaseModel):
    plainspoken: int = Field(ge=1, le=5)
    unhurried_rhythm: int = Field(ge=1, le=5)
    operational_specificity: int = Field(ge=1, le=5)
    anti_hype: int = Field(ge=1, le=5)
    avatar_language: int = Field(ge=1, le=5)
    notes: str = ""

    @property
    def minimum(self) -> int:
        return min(self.plainspoken, self.unhurried_rhythm, self.operational_specificity,
                   self.anti_hype, self.avatar_language)


class AuditedClaim(BaseModel):
    claim: str
    proof_id: str


class FlagRuling(BaseModel):
    phrase: str
    acceptable: bool
    reason: str


class JudgeOutput(BaseModel):
    items: list[ReviewItem]
    voice: VoiceScores
    claim_audit: list[AuditedClaim] = []
    flag_rulings: list[FlagRuling] = []
    top_fix: str = ""

    @field_validator("items")
    @classmethod
    def _all_ten(cls, v: list[ReviewItem]) -> list[ReviewItem]:
        ids = sorted(i.id for i in v)
        if ids != list(range(1, 11)):
            raise ValueError(f"review must contain checklist items 1-10 exactly once, got {ids}")
        return sorted(v, key=lambda i: i.id)


CHECKLIST = {
    1: "Hook opens with a pattern interrupt in the first 3 seconds",
    2: "Clear problem or pain statement present",
    3: "Unique mechanism or differentiator explained",
    4: "Social proof or credibility element included",
    5: "CTA matches funnel stage (cold traffic vs. retargeting)",
    6: "Script length within target range (60 to 180 seconds A-roll)",
    7: "Client brand voice / rhythm alignment",
    8: "No fabricated claims or unverifiable statistics",
    9: "Curiosity or open loop used to maintain watch time",
    10: "VSL structure followed: Pain > Promise > Proof > CTA",
}
