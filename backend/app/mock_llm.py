"""Deterministic offline stand-in for the model (LLM_PROVIDER=mock).

Used by the automated tests and for working on the dashboard without an API key.
It returns schema-valid outputs so every non-AI part of the pipeline (guards,
idea memory, approval trigger, review gate, revision loop, delivery) is exercised
for real. It is NEVER used to produce the submitted sample outputs.
"""
from __future__ import annotations

import hashlib
from typing import Any

from . import db

F1, F2, F3, F4 = ("F1 Identity & Belonging", "F2 Cost of Inaction & Fear",
                  "F3 Story & Transformation (Marcus, first person)", "F4 Enemy / Contrarian")
BELIEF, AVATAR, LAB, MECH = ("Belief hooks (Hopeless / Helpless / Worthless)", "Avatar hooks", "LAB profile hooks",
                             "Mechanism / procedural (retargeting only)")

IDEA_BANK: list[dict[str, Any]] = [
    dict(concept_hook="Somebody got paid the day you bought that last course. It wasn't you.", creative_type="talking-head",
         angle="Who gets paid, and when: course sellers vs. liquidator placement fees", lead_type="curiosity-led",
         hook_family=F4, proof_point_ids=["M1", "T1"], target_avatar="dana", pain_addressed="Burned by a prior course; distrusts own judgment", funnel_stage="cold"),
    dict(concept_hook="I ran a depot for 14 years. Here's what happened to the returns.", creative_type="founder-confessional",
         angle="Warehouse truth: the constant river of overstock that needs clearing", lead_type="proof-led",
         hook_family=F3, proof_point_ids=["C1", "M2"], target_avatar="ray", pain_addressed="Needs the economics to make sense", funnel_stage="cold"),
    dict(concept_hook="You don't have six months to guess at products. Good. Neither did Theo.", creative_type="UGC",
         angle="Evenings-sized system; the guessing is done by the match sheet", lead_type="problem-led",
         hook_family=AVATAR, proof_point_ids=["T2", "M2", "M3"], target_avatar="theo", pain_addressed="No spare hours; product paralysis", funnel_stage="cold"),
    dict(concept_hook="He never promised me money. That's why I trusted him.", creative_type="story",
         angle="The anti-claim as proof of honesty for the anxious near-retiree", lead_type="proof-led",
         hook_family=AVATAR, proof_point_ids=["T3", "M4"], target_avatar="lorraine", pain_addressed="Can someone like me actually do this?", funnel_stage="cold"),
    dict(concept_hook="A corner of the garage. A few labeled bins. A store with your name on it.", creative_type="story",
         angle="Dignity and ownership: a thing that's yours again", lead_type="problem-led",
         hook_family=F1, proof_point_ids=["T5", "C4"], target_avatar="marisol", pain_addressed="Worthless belief: something real isn't for people like me", funnel_stage="cold"),
    dict(concept_hook="Three questions everyone asks before paying a dollar. Let me answer all three.", creative_type="listicle",
         angle="Pre-answer the objections: is it real, why so cheap, what do I pay later", lead_type="offer-led",
         hook_family=MECH, proof_point_ids=["O1", "C2"], target_avatar="ray", pain_addressed="What's the catch this time?", funnel_stage="retargeting"),
    dict(concept_hook="Think back one year. Be honest about how much changed.", creative_type="talking-head",
         angle="Cost of inaction: a year moves whether you do or not", lead_type="problem-led",
         hook_family=F2, proof_point_ids=["M3", "C4"], target_avatar="dana", pain_addressed="Hopeless belief; stuck", funnel_stage="cold"),
    dict(concept_hook="This week's matched lots are already on the sheet. Here's how to read one.", creative_type="demo",
         angle="Show the Liquidator Match sheet: demand before the store", lead_type="offer-led",
         hook_family=MECH, proof_point_ids=["M2", "O2"], target_avatar="theo", pain_addressed="Product paralysis", funnel_stage="retargeting"),
    dict(concept_hook="Somewhere you decided this is for younger people. Look who's actually doing it.", creative_type="talking-head",
         angle="Not too late: the membership skews 45 to 55", lead_type="curiosity-led",
         hook_family=F1, proof_point_ids=["M5", "C4"], target_avatar="lorraine", pain_addressed="I'm too old for this", funnel_stage="cold"),
    dict(concept_hook="I went in looking for the catch. I found it.", creative_type="UGC",
         angle="Skeptic confirms: the catch is the weekly work", lead_type="curiosity-led",
         hook_family=LAB, proof_point_ids=["T4", "M1"], target_avatar="ray", pain_addressed="Looks for the catch; reads the fine print", funnel_stage="retargeting"),
    dict(concept_hook="The reason you froze last time wasn't you. It was step one.", creative_type="objection-handler",
         angle="Helpless belief reframe: they handed you a mountain", lead_type="problem-led",
         hook_family=BELIEF, proof_point_ids=["M3", "T3"], target_avatar="marisol", pain_addressed="Helpless: too complicated", funnel_stage="cold"),
    dict(concept_hook="Anytime something costs a dollar, ask who's really paying for it.", creative_type="talking-head",
         angle="Structural transparency about the $1 workshop", lead_type="offer-led",
         hook_family=F4, proof_point_ids=["O1", "M1"], target_avatar="ray", pain_addressed="Cost-of-entry fear", funnel_stage="cold"),
    dict(concept_hook="You feel it at the pump. You feel it at the register.", creative_type="talking-head",
         angle="Small dream: breathing room, not a fortune", lead_type="problem-led",
         hook_family=F2, proof_point_ids=["M4", "C3"], target_avatar="dana", pain_addressed="Security: buffer that doesn't depend on the employer", funnel_stage="cold"),
    dict(concept_hook="Nobody throws a party the day you list your first matched lot.", creative_type="founder-confessional",
         angle="The quiet win: one real thing done", lead_type="curiosity-led",
         hook_family=F3, proof_point_ids=["T3", "M2"], target_avatar="lorraine", pain_addressed="Quiet belief she can't pull this off", funnel_stage="cold"),
]


def _h(*parts: Any) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest(), 16)


def ideation(p) -> dict:
    ctx = p.mock_context
    used = {i["concept_hook"] for i in db.list_ideas(ctx["client"].id)}
    fresh = [dict(i, strategist_note="Mock note: fits the avatar's dominant belief.") for i in IDEA_BANK
             if i["concept_hook"] not in used]
    picks = fresh[: ctx["n"]]
    if ctx["attempt"] == 1 and picks:
        # deliberately include one near-duplicate so the idea-memory guard is exercised
        dup = dict(picks[0])
        dup["concept_hook"] = dup["concept_hook"].replace("It wasn't you.", "And it wasn't you.")
        picks = picks[: ctx["n"] - 1] + [dup] if ctx["n"] > 1 else picks
    return {"ideas": picks}


def scoring(p) -> dict:
    out = []
    for c in p.mock_context["cards"]:
        h = _h(c["concept_hook"])
        out.append({
            "idea_key": c["idea_key"],
            "impact": 5 + h % 5, "impact_reasoning": "Mock: hits the avatar's dominant limiting belief (pack §03).",
            "confidence": 4 + (h >> 4) % 6, "confidence_reasoning": "Mock: angle matches the pack's guidance for this funnel stage.",
            "ease": 4 + (h >> 8) % 6, "ease_reasoning": "Mock: talking-head with simple B-roll.",
            "verdict": "Mock verdict: solid concept, checkable proof.", "risk_flags": [],
        })
    return {"scores": out}


def scripting(p) -> dict:
    idea = p.mock_context["idea"]
    stage = idea["funnel_stage"]
    proof_extra = ""
    if idea["id"] % 4 == 0 and not p.mock_context["revision"]:
        proof_extra = " Over 10,000 members have joined."  # planted fabrication → gate must catch it
    cta = ("Watch the First Pallet workshop for $1. It's two hours, and you'll see exactly how the machine works. Then decide."
           if stage == "cold" else
           "See this week's matched inventory. Grab a $1 seat in the First Pallet workshop, look at the lots, then decide.")
    return {
        "title": f"{idea['concept_hook'][:40].rstrip('. ')} (mock)",
        "production_notes": ["Single talking-head take in a quiet garage corner with labeled bins.",
                             "B-roll: the match sheet on screen during the promise section.",
                             "Calm, unhurried delivery. No music stings."],
        "hook_plan": [{"hook": "hook_1", "interrupt_type": "unexpected-specific", "door": "the concept"},
                      {"hook": "hook_2", "interrupt_type": "direct-challenge", "door": "who pays"},
                      {"hook": "hook_3", "interrupt_type": "contrarian-admission", "door": "built backwards"}],
        "hook_1": idea["concept_hook"],
        "hook_2": "Don't trust my word. Look at who actually pays me, and decide for yourself.",
        "hook_3": "Every store pitch you've seen wanted money up front. This one is built backwards on purpose.",
        "body": {
            "pain": ("You've been burned before. Maybe it was a course that left you with a login and nothing else. "
                     "You saw the red flags and wanted it to work anyway. Now every new offer gets the same question. "
                     "What's the catch this time? There's one question nobody in this space wants you to ask. I'll get to it."),
            "promise": ("Here's how this one is built. Regional liquidators always have overstock and returned inventory to clear. "
                        "They pay placement fees to move it through reliable small stores. I'm paid by those liquidators, "
                        "and only when a member's store actually moves product. You don't pay me for results. "
                        "Every week, members get a match sheet of lots that already have demand behind them. "
                        "So you're not guessing at products. It takes a few evenings a week. "
                        "I'm not going to insult you by calling it passive."),
            "proof": ("I ran a regional wholesale depot for 14 years. We work with 11 vetted regional partners under signed "
                      "placement agreements. The program has run for 5 years, and 9,400+ members have enrolled." + proof_extra +
                      " Ray C. went in looking for the catch. In his words, \"The catch is that you have to actually do the weekly work.\" "
                      "So here's the question I said I'd answer. Who's actually paying the person selling you this? "
                      "In my case, it's the liquidators, and only when your store works."),
            "cta": cta,
        },
        "open_loop": {"opened_with": "There's one question nobody in this space wants you to ask.",
                      "closed_with": "So here's the question I said I'd answer."},
        "claims": [
            {"claim": "Ran a regional wholesale depot for 14 years", "proof_id": "C1"},
            {"claim": "11 vetted regional partners under signed placement agreements", "proof_id": "C2"},
            {"claim": "Program has run 5 years", "proof_id": "C3"},
            {"claim": "9,400+ members enrolled", "proof_id": "C4"},
            {"claim": "Liquidators pay Marcus only when member stores move product", "proof_id": "M1"},
            {"claim": "Weekly match sheet of lots with demand", "proof_id": "M2"},
            {"claim": "A few evenings a week", "proof_id": "M3"},
            {"claim": "Ray C. testimonial", "proof_id": "T4"},
            {"claim": "$1 two-hour First Pallet workshop", "proof_id": "O1"},
        ],
    }


def review(p) -> dict:
    code = p.mock_context["code"]
    draft = p.mock_context["draft"]
    items = []
    for i in range(1, 11):
        hard = code.hard(i)
        items.append({"id": i, "score": 2 if hard else 5,
                      "evidence": hard[0].excerpt or hard[0].message if hard else draft.hook_1[:80],
                      "reasoning": "Mock: code check failed." if hard else "Mock: item met."})
    flags = [f for f in code.findings if f.level == "flag"]
    return {
        "items": items,
        "voice": {"plainspoken": 5, "unhurried_rhythm": 5, "operational_specificity": 4, "anti_hype": 5,
                  "avatar_language": 4, "notes": "Mock voice assessment."},
        "claim_audit": [{"claim": c.claim, "proof_id": c.proof_id} for c in draft.claims],
        "flag_rulings": [{"phrase": f.message.split("“")[-1].rstrip("”") if "“" in f.message else f.message[:30],
                          "acceptable": True, "reason": "Mock: negated / contrastive use."} for f in flags],
        "top_fix": "Mock: tighten the proof section.",
    }


HANDLERS = {"ideation": ideation, "scoring": scoring, "scripting": scripting, "review": review}
