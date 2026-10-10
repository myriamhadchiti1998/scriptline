"""STAGE 6 — Quality review: a hybrid gate.

Layer A — deterministic code checks (cannot be talked out of a verdict):
    numbers/dollars/percentages vs. the client's fact allowlist, forbidden
    entities, invented member names, altered testimonial quotes, banned
    compliance language, length, hook rules, CTA terms per funnel stage,
    section presence, voice metrics (exclamations, all-caps, sentence length).

Layer B — an independent AI reviewer (separate prompt, did not write the
    script) scores each of the 10 checklist items 1–5 against written anchors,
    quotes evidence, audits every factual claim against proof-bank IDs, scores
    five voice dimensions, and rules on context-dependent "flag" phrases.

Decision (code, not the model):
    item passes  ⇔  no HARD code finding on it  AND  AI score ≥ pass threshold
                    (+ item 7: every voice dimension ≥ 3 and no rejected voice flag)
                    (+ item 8: zero UNSUPPORTED claims and no rejected claim flag)
    script passes ⇔ all 10 items pass. Anything else is HELD, never delivered.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .. import memory
from ..clientcfg import ClientConfig
from ..config import settings
from ..llm import Prompt, get_llm
from ..prompts import system_blocks
from ..schemas import CHECKLIST, JudgeOutput, ScriptDraft, review_schema

NEGATORS = {"not", "no", "never", "won't", "wont", "isn't", "isnt", "aren't", "don't", "dont", "doesn't",
            "without", "insult", "nobody", "nothing", "instead", "told", "sold", "promised", "promise",
            "promises", "they", "gurus", "pretend", "call", "calling", "called", "forget", "stop", "lie", "fantasy"}

UPSELL_PRICE_RE = re.compile(r"\$\s?(?:1,?450|6,?800|197|497)\b")
NUMBER_RE = re.compile(r"(\$\s?)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(\s?[kK]\b)?(\+)?(\s?%|\s?percent\b)?")
QUOTE_RE = re.compile(r"[“\"]([^”\"]{12,}?)[”\"]")
INITIAL_NAME_RE = re.compile(r"\b([A-Z][a-z]+) ([A-Z])\.(?=\s|,|$|”|\")")
NAMED_PERSON_RE = re.compile(r"\b(?:member|student|guy|woman|man|lady|customer|client|friend|neighbor)(?: named| called)?,?\s+([A-Z][a-z]+)\b")


@dataclass
class Finding:
    level: str          # hard | flag
    item: int           # checklist item it belongs to
    message: str
    excerpt: str = ""

    def as_dict(self) -> dict:
        return {"level": self.level, "item": self.item, "message": self.message, "excerpt": self.excerpt}


@dataclass
class CodeReport:
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def add(self, level: str, item: int, message: str, excerpt: str = "") -> None:
        self.findings.append(Finding(level, item, message, excerpt[:160]))

    def hard(self, item: int) -> list[Finding]:
        return [f for f in self.findings if f.item == item and f.level == "hard"]


# ── text helpers ─────────────────────────────────────────────────────────────
def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])[”\"]?\s+|\n+", text.strip())
    return [p.strip() for p in parts if p and len(p.split()) > 0]


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9$][A-Za-z0-9$'’,.+-]*", text))


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9$ ]+", " ", text.lower().replace("’", "'").replace("'", "")).split())


def _context(text: str, start: int, end: int, pad: int = 50) -> str:
    return text[max(0, start - pad):min(len(text), end + pad)].replace("\n", " ")


def _negated(text: str, start: int) -> bool:
    before = text[:start]
    sent_start = max(before.rfind("."), before.rfind("?"), before.rfind("!"), before.rfind("\n"))
    window = before[sent_start + 1:].lower().replace("’", "'").split()[-8:]
    return any(w.strip(",;:\"“”") in NEGATORS or w.endswith("n't") for w in window)


# ── language scan (shared with ideation guards) ──────────────────────────────
def scan_language(client: ClientConfig, text: str) -> list[dict]:
    out = []
    for rule in client.language_rules:
        for m in re.finditer(rule["pattern"], text, flags=re.IGNORECASE):
            level = rule["level"]
            msg = rule["reason"]
            if rule.get("negatable") and _negated(text, m.start()):
                level = "flag"
                msg += " — appears negated/contrasted; confirm in context"
            out.append({"level": level, "item": rule["item"], "message": f"{msg}: “{m.group(0)}”",
                        "excerpt": _context(text, m.start(), m.end())})
    return out


# ── Layer A: deterministic checks ────────────────────────────────────────────
def code_checks(client: ClientConfig, draft: ScriptDraft, funnel_stage: str) -> CodeReport:
    r = CodeReport()
    sr, voice, facts = client.script_rules, client.voice, client.facts
    hooks, body = draft.hooks, draft.body
    spoken = draft.spoken_text()

    # Item 1 — hooks: first sentence short enough to land in ~3s; three distinct hooks
    first_lens = []
    for n, h in enumerate(hooks, 1):
        first = sentences(h)[0] if sentences(h) else h
        wc = word_count(first)
        first_lens.append(wc)
        if wc > sr["hook_first_sentence_max_words"]:
            r.add("hard", 1, f"Hook {n} first sentence is {wc} words — too long to land in 3 seconds "
                             f"(max {sr['hook_first_sentence_max_words']})", first)
    sims = {}
    for a, b in ((0, 1), (0, 2), (1, 2)):
        s = memory.similarity(hooks[a], hooks[b])
        sims[f"{a + 1}-{b + 1}"] = s
        if s > sr["max_hook_similarity"]:
            r.add("hard", 1, f"Hooks {a + 1} and {b + 1} are near-duplicates (similarity {s:.2f}) — need distinct options")
    r.metrics["hook_first_sentence_words"] = first_lens
    if draft.hook_plan:
        types = [h.interrupt_type for h in draft.hook_plan]
        r.metrics["hook_plan"] = [f"{h.hook}: {h.interrupt_type} — {h.door}" for h in draft.hook_plan]
        if len(set(types)) < 3:
            r.add("hard", 1, f"Hook plan reuses an interrupt type ({', '.join(types)}) — three hooks must open three different doors")
    r.metrics["hook_similarity"] = sims

    # Item 4 — at least one checkable credibility element in the claim ledger
    proof_types = {client.proof(c.proof_id)["type"] for c in draft.claims if client.proof(c.proof_id)}
    if not proof_types & {"credential", "scale", "testimonial"}:
        r.add("hard", 4, "No credential, scale, or testimonial proof cited in the claim ledger")

    # Item 5 — CTA matches funnel stage
    stage = client.funnel_stages.get(funnel_stage)
    cta = body.cta.lower()
    if stage is None:
        r.add("hard", 5, f"Unknown funnel stage '{funnel_stage}'")
    else:
        for group in stage["required_cta_terms"]:
            if not any(t.lower() in cta for t in group):
                r.add("hard", 5, f"CTA is missing a required {funnel_stage} element (one of: {', '.join(group)})", body.cta)
        if funnel_stage == "cold" and UPSELL_PRICE_RE.search(spoken):
            r.add("hard", 5, "Cold-traffic script mentions upsell pricing", UPSELL_PRICE_RE.search(spoken).group(0))

    # Item 6 — length (every hook variant + body must fit the range)
    body_words = word_count(draft.body_text())
    totals = [word_count(h) + body_words for h in hooks]
    secs = [round(t / sr["words_per_second"]) for t in totals]
    r.metrics.update({"body_words": body_words, "total_words_range": [min(totals), max(totals)],
                      "seconds_range": [min(secs), max(secs)],
                      "target_seconds": [sr["min_seconds"], sr["max_seconds"]]})
    if min(secs) < sr["min_seconds"] or max(secs) > sr["max_seconds"]:
        r.add("hard", 6, f"Estimated A-roll length {min(secs)}–{max(secs)}s is outside "
                         f"{sr['min_seconds']}–{sr['max_seconds']}s")

    # Item 7 — voice & rhythm metrics
    sents = sentences(spoken)
    lens = [word_count(s) for s in sents] or [0]
    avg = round(sum(lens) / len(lens), 1)
    excl = spoken.count("!")
    caps = [w for w in re.findall(r"\b[A-Z]{2,}\b", spoken) if w not in voice["caps_exempt"]]
    r.metrics.update({"sentences": len(sents), "avg_sentence_words": avg, "max_sentence_words": max(lens),
                      "exclamation_marks": excl, "all_caps_words": caps})
    lo, hi = voice["avg_sentence_words"]
    if not lo <= avg <= hi:
        r.add("hard", 7, f"Average sentence length {avg} words is outside the brand rhythm range {lo}–{hi}")
    if max(lens) > voice["max_sentence_words"]:
        longest = sents[lens.index(max(lens))]
        r.add("hard", 7, f"A {max(lens)}-word sentence breaks the plainspoken rhythm (max {voice['max_sentence_words']})", longest)
    if excl > voice["max_exclamation_marks"]:
        r.add("hard", 7, f"{excl} exclamation mark(s) — brand voice is calm, none allowed")
    if len(caps) > voice["max_all_caps_words"]:
        r.add("hard", 7, f"All-caps words used: {', '.join(caps[:5])}")

    # Items 7/8 — compliance language rules from the client config
    for f in scan_language(client, spoken):
        r.add(f["level"], f["item"], f["message"], f["excerpt"])

    # Item 8 — fabrication: numbers, dollars, percentages
    allowed_n = {int(x) for x in facts["allowed_numbers"]}
    allowed_usd = {int(x) for x in facts["allowed_dollar_amounts"]}
    allowed_pct = {int(x) for x in facts["allowed_percentages"]}
    for m in NUMBER_RE.finditer(spoken):
        dollar, digits, k_suffix, _plus, pct = m.groups()
        value = int(digits.replace(",", "")) * (1000 if k_suffix else 1)
        token = m.group(0).strip()
        if pct:
            if value not in allowed_pct:
                r.add("hard", 8, f"Percentage “{token}” is not in the Reference Pack fact list", _context(spoken, m.start(), m.end()))
        elif dollar:
            if value not in allowed_usd:
                r.add("hard", 8, f"Dollar figure “{token}” is not in the Reference Pack", _context(spoken, m.start(), m.end()))
        elif value not in allowed_n:
            r.add("hard", 8, f"Number “{token}” is not in the Reference Pack fact list", _context(spoken, m.start(), m.end()))

    # Item 8 — production notes are delivered too: fact-check the claims in them
    # (dollar figures, percentages, counts of members/partners/years — not pacing like "150 wpm")
    notes = " ".join(draft.production_notes)
    for m in NUMBER_RE.finditer(notes):
        dollar, digits, k_suffix, _plus, pct = m.groups()
        value = int(digits.replace(",", "")) * (1000 if k_suffix else 1)
        tail = notes[m.end():m.end() + 30].lower()
        factual = dollar or pct or re.match(r"\W{0,2}(?:\+\s*)?(?:vetted |regional |enrolled )*"
                                            r"(?:members?|partners?|liquidators?|years?|lots?|stores?|students?)\b", tail)
        ok = (value in allowed_pct) if pct else (value in allowed_usd) if dollar else (value in allowed_n)
        if factual and not ok:
            r.add("hard", 8, f"Production notes contain “{m.group(0).strip()}”, which is not in the Reference Pack",
                  _context(notes, m.start(), m.end()))
    for note in draft.production_notes:  # per note, so "If Ray C. is…" isn't split at the initial
        for m in re.finditer(r"\b(?:signed (?:a |the )?(?:release|waiver|consent)|has agreed to|agreed to (?:film|appear))\b", note, re.I):
            before = note[max(0, m.start() - 120):m.start()]
            if not re.search(r"\b(?:if|unless|whether|once|when|only after|confirm)\b", before, re.I):
                r.add("hard", 8, "Production notes state a member arrangement as fact (not in the Reference Pack)", note)

    # Item 8 — forbidden / invented entities and people
    for ent in facts["forbidden_entities"]:
        flags = re.IGNORECASE if ent.islower() else 0
        m = re.search(rf"(?<![A-Za-z]){re.escape(ent)}(?![A-Za-z])", spoken + "\n" + notes, flags)
        if m:
            r.add("hard", 8, f"Names an entity that is not in the Reference Pack: “{ent}”",
                  _context(spoken + "\n" + notes, m.start(), m.end()))
    m = re.search(r"\bAmazon\b(?!\s+FBA)", spoken)
    if m:
        r.add("hard", 8, "Names Amazon outside the pack's 'Amazon FBA' competitor context", _context(spoken, m.start(), m.end()))
    persons = {p["person"]: p for p in client.proof_bank if p["type"] == "testimonial"}
    first_names = {p.split()[0] for p in persons}
    for m in INITIAL_NAME_RE.finditer(spoken):
        full = f"{m.group(1)} {m.group(2)}."
        if full not in persons:
            r.add("hard", 8, f"Attributes something to “{full}”, who is not a proof-bank member", _context(spoken, m.start(), m.end()))
    for m in NAMED_PERSON_RE.finditer(spoken):
        if m.group(1) not in first_names:
            r.add("hard", 8, f"Invented named person “{m.group(1)}”", _context(spoken, m.start(), m.end()))

    # Item 8 — quote fidelity: a quote attributed to a member must be a verbatim excerpt
    # of THAT member's proof-bank testimonial. Attribution = the nearest member name,
    # preferring names just before the quote ("Ray C. said, \"…\"").
    pack_norm = _norm(client.reference_pack)
    for m in QUOTE_RE.finditer(spoken):
        quote = m.group(1)
        if word_count(quote) < 4:
            continue
        fragments = [_norm(f) for f in re.split(r"\.\.\.|…", quote) if _norm(f)]
        owner, best = None, 10 ** 9
        for p in persons.values():
            first = p["person"].split()[0]
            for nm in re.finditer(rf"\b{re.escape(first)}\b", spoken):
                if nm.end() <= m.start():
                    dist = m.start() - nm.end()          # name before the quote
                elif nm.start() >= m.end():
                    dist = (nm.start() - m.end()) + 40   # name after the quote (slight penalty)
                else:
                    continue
                if dist <= 160 and dist < best:
                    owner, best = p, dist
        if owner:
            if not all(f in _norm(owner["quote"]) for f in fragments):
                other = next((p for p in persons.values() if p is not owner
                              and all(f in _norm(p["quote"]) for f in fragments)), None)
                msg = (f"Quote is {other['person']}'s testimonial but is attributed to {owner['person']}" if other else
                       f"Quote attributed to {owner['person']} is not a verbatim excerpt of their proof-bank testimonial")
                r.add("hard", 8, msg, quote)
        elif not all(f in pack_norm for f in fragments):
            r.add("flag", 8, "Quoted line is not verbatim from the Reference Pack — confirm it is not presented as a real quote",
                  quote)

    # Item 8 — unknown proper nouns are flagged for the reviewer
    allowed_nouns = set(facts["allowed_proper_nouns"]) | first_names | set(voice["caps_exempt"])
    unknown = set()
    for s in sents:
        for m in list(re.finditer(r"[A-Za-z][A-Za-z'’]*", s))[1:]:
            t = m.group(0)
            prev = s[:m.start()].rstrip()[-1:]          # capital after a quote/colon/dash starts a new clause
            if t[0].isupper() and t not in allowed_nouns and not t.isupper() and prev not in ('"', "“", ":", "—", "(", "-"):
                unknown.add(t)
    for t in sorted(unknown):
        r.add("flag", 8, f"Unrecognised proper noun “{t}” — verify it exists in the Reference Pack")

    # Item 8 — the writer's claim ledger must exist and use real proof IDs
    if not draft.claims:
        r.add("hard", 8, "Writer provided no claim ledger (every factual claim must cite a proof ID)")
    for c in draft.claims:
        if c.proof_id not in client.proof_ids:
            r.add("hard", 8, f"Claim cites unknown proof ID {c.proof_id}", c.claim)

    # Item 9 — open loop declared and present
    ol = draft.open_loop
    if not ol.opened_with.strip() or not ol.closed_with.strip() or _norm(ol.opened_with) == _norm(ol.closed_with):
        r.add("hard", 9, "No distinct open loop declared (opened_with / closed_with)")
    else:
        for label, line in (("opening", ol.opened_with), ("closing", ol.closed_with)):
            if _norm(line)[:40] not in _norm(spoken):
                r.add("flag", 9, f"Declared open-loop {label} line not found verbatim in the script", line)

    # Item 10 — all four sections present with substance
    for name in ("pain", "promise", "proof", "cta"):
        wc = word_count(getattr(body, name))
        if wc < (8 if name == "cta" else 15):
            r.add("hard", 10, f"{name.upper()} section is only {wc} words — section missing or hollow")
    return r


# ── Layer B: AI reviewer ─────────────────────────────────────────────────────
def render_script(d: ScriptDraft) -> str:
    notes = "\n".join(f"- {n}" for n in d.production_notes) or "(none)"
    return (f"PRODUCTION NOTES (not spoken):\n{notes}\n\nHOOK 1: {d.hook_1}\nHOOK 2: {d.hook_2}\nHOOK 3: {d.hook_3}\n\n"
            f"BODY — PAIN:\n{d.body.pain}\n\nBODY — PROMISE:\n{d.body.promise}\n\n"
            f"BODY — PROOF:\n{d.body.proof}\n\nBODY — CTA:\n{d.body.cta}")


def _judge_user(client: ClientConfig, idea: dict, draft: ScriptDraft, code: CodeReport) -> str:
    m = code.metrics
    stage = idea["funnel_stage"]
    findings = "\n".join(
        f"- [{f.level.upper()}][item {f.item}] {f.message}" + (f"  …{f.excerpt}…" if f.excerpt else "")
        for f in code.findings) or "- none"
    concept = {k: idea[k] for k in ("concept_hook", "creative_type", "angle", "lead_type", "target_avatar",
                                    "pain_addressed", "funnel_stage", "proof_point_ids")}
    return (
        f"Review this script for funnel stage `{stage}`.\n"
        f"Funnel stage definition: {client.funnel_stages[stage]['description'].strip()}\n\n"
        f"APPROVED CONCEPT:\n{json.dumps(concept, indent=2)}\n\n"
        f"MEASURED LENGTH: {m['total_words_range'][0]}–{m['total_words_range'][1]} words per hook+body variant ≈ "
        f"{m['seconds_range'][0]}–{m['seconds_range'][1]} s (target {m['target_seconds'][0]}–{m['target_seconds'][1]} s).\n"
        f"RHYTHM METRICS: {m['sentences']} sentences, avg {m['avg_sentence_words']} words, longest {m['max_sentence_words']}, "
        f"{m['exclamation_marks']} exclamation marks, all-caps words: {m['all_caps_words'] or 'none'}.\n\n"
        f"DETERMINISTIC FINDINGS (HARD = already failing; FLAG = rule on it in flag_rulings):\n{findings}\n\n"
        f"SCRIPT:\n{render_script(draft)}\n\n"
        "Score all 10 checklist items, the voice sub-scores, audit every factual claim, rule on every FLAG, "
        "and give the top fix."
    )


def review(client: ClientConfig, idea: dict, draft: ScriptDraft, log=None) -> dict:
    code = code_checks(client, draft, idea["funnel_stage"])
    result = get_llm().run(Prompt(
        stage="review",
        system_blocks=system_blocks("review", client),
        user=_judge_user(client, idea, draft, code),
        schema=review_schema(client),
        model_cls=JudgeOutput,
        stage_model=settings.review,
        mock_context={"client": client, "draft": draft, "code": code},
    ))
    judge: JudgeOutput = result.data  # type: ignore[assignment]
    if log:
        log(f"AI reviewer scored the script ({result.model}, {result.seconds}s)")
    return combine(code, judge, judge_model=result.model)


def combine(code: CodeReport, judge: JudgeOutput, judge_model: str = "") -> dict:
    threshold = settings.review_pass_score
    rejected_flags = [f for f in judge.flag_rulings if not f.acceptable]
    unsupported = [c for c in judge.claim_audit if c.proof_id == "UNSUPPORTED"]
    items = []
    for ji in judge.items:
        hard = code.hard(ji.id)
        flags = [f for f in code.findings if f.item == ji.id and f.level == "flag"]
        reasons: list[str] = [f.message for f in hard]
        if ji.score < threshold:
            reasons.append(f"AI reviewer scored {ji.score}/5 (needs ≥ {threshold}): {ji.reasoning}")
        if ji.id == 7:
            if judge.voice.minimum < 3:
                reasons.append(f"A voice dimension scored {judge.voice.minimum}/5 (each needs ≥ 3)")
            for fr in rejected_flags:
                if any(fr.phrase.lower() in f.message.lower() for f in flags):
                    reasons.append(f"Reviewer ruled flagged phrase unacceptable: “{fr.phrase}” — {fr.reason}")
        if ji.id == 8:
            reasons += [f"Unsupported claim: “{c.claim}”" for c in unsupported]
            for fr in rejected_flags:
                if any(fr.phrase.lower() in f.message.lower() for f in flags):
                    reasons.append(f"Reviewer ruled flagged phrase unacceptable: “{fr.phrase}” — {fr.reason}")
        passed = not reasons
        items.append({
            "id": ji.id,
            "name": CHECKLIST[ji.id],
            "passed": passed,
            "ai_score": ji.score,
            "evidence": ji.evidence,
            "reasoning": ji.reasoning,
            "code_checks": [f.as_dict() for f in code.findings if f.item == ji.id],
            "fail_reasons": reasons,
            "summary": reasons[0] if reasons else ji.reasoning,
        })
    failed = [i["id"] for i in items if not i["passed"]]
    return {
        "passed": not failed,
        "failed_items": failed,
        "score": round(sum(i["ai_score"] for i in items) / len(items), 2),
        "items": items,
        "voice": judge.voice.model_dump(),
        "claim_audit": [c.model_dump() for c in judge.claim_audit],
        "flag_rulings": [f.model_dump() for f in judge.flag_rulings],
        "metrics": code.metrics,
        "top_fix": judge.top_fix,
        "judge_model": judge_model,
        "pass_rule": f"every item: no hard code finding AND AI score ≥ {threshold}",
    }
