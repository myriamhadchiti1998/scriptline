"""The quality gate's deterministic layer must catch fabrication and off-brand copy
on its own — these tests never call a model."""
import copy

import pytest

from app import mock_llm, redteam
from app.clientcfg import load_client
from app.schemas import ScriptDraft
from app.stages.review import code_checks

CLIENT = load_client("sovereign_storefront")


class _P:  # minimal stand-in for llm.Prompt
    def __init__(self, idea, revision=False):
        self.mock_context = {"idea": idea, "revision": revision, "client": CLIENT}


IDEA = {"id": 1, "concept_hook": "Somebody got paid the day you bought that last course. It wasn't you.",
        "funnel_stage": "cold"}


def good_draft(stage: str = "cold") -> ScriptDraft:
    return ScriptDraft.model_validate(mock_llm.scripting(_P({**IDEA, "funnel_stage": stage})))


def hard_items(draft: ScriptDraft, stage: str = "cold") -> set[int]:
    return {f.item for f in code_checks(CLIENT, draft, stage).findings if f.level == "hard"}


def with_proof(extra: str) -> ScriptDraft:
    d = copy.deepcopy(good_draft())
    d.body.proof += " " + extra
    return d


def test_compliant_script_has_no_hard_findings():
    assert hard_items(good_draft("cold")) == set()
    assert hard_items(good_draft("retargeting"), "retargeting") == set()


@pytest.mark.parametrize("ls", redteam.losing_scripts(CLIENT), ids=lambda x: x["title"])
def test_reference_pack_losing_scripts_fail_compliance_items_in_code(ls):
    items = hard_items(redteam.to_draft(ls["title"], ls["text"]))
    assert {7, 8} & items, f"{ls['title']} must fail voice or fabrication in code"


def test_three_losing_scripts_present():
    assert len(redteam.losing_scripts(CLIENT)) == 3


@pytest.mark.parametrize("planted", [
    "Over 10,000 members have joined.",                  # inflated scale
    "Nearly 87% of members list a lot in week one.",     # invented statistic
    "Members make $5,000 a month.",                      # earnings claim
    "One member, Greg, built a store in a weekend.",     # invented person
    "Greg T. said it changed his life.",                 # invented testimonial attribution
    "As seen on Forbes.",                                # invented media
    "We partner with Walmart.",                          # named partner / invented entity
    "It started in 2019.",                               # invented date
])
def test_fabrications_fail_item_8(planted):
    assert 8 in hard_items(with_proof(planted))


def test_altered_testimonial_quote_fails():
    d = copy.deepcopy(good_draft())
    d.body.proof = d.body.proof.replace("you have to actually do the weekly work", "it practically runs itself")
    assert 8 in hard_items(d)


@pytest.mark.parametrize("planted,item", [
    ("Our students love it.", 7),
    ("This is passive income.", 7),
    ("Only 3 spots left.", 7),
    ("It works on autopilot.", 7),
    ("This changes everything!", 7),
    ("This is HUGE news.", 7),
])
def test_off_brand_language_fails_item_7(planted, item):
    assert item in hard_items(with_proof(planted))


def test_negated_passive_is_flag_not_fail():
    findings = code_checks(CLIENT, good_draft(), "cold").findings
    passive = [f for f in findings if "passive" in f.message.lower()]
    assert passive and all(f.level == "flag" for f in passive)


def test_cold_cta_without_front_end_offer_fails():
    d = copy.deepcopy(good_draft())
    d.body.cta = "Click the link below to learn more about how this works for you."
    assert 5 in hard_items(d)


def test_cold_cta_with_upsell_price_fails():
    d = copy.deepcopy(good_draft())
    d.body.cta += " The Core program is $1,450 after that."
    assert 5 in hard_items(d)


def test_length_out_of_range_fails():
    d = copy.deepcopy(good_draft())
    d.body.proof = "I ran a depot for 14 years. Ray C. went in looking for the catch."
    d.body.promise = "Liquidators pay me when stores move product."
    d.body.pain = "You've been burned before. What's the catch this time?"
    assert 6 in hard_items(d)


def test_duplicate_hooks_fail_item_1():
    d = copy.deepcopy(good_draft())
    d.hook_2 = d.hook_1
    assert 1 in hard_items(d)


def test_missing_claim_ledger_fails_item_8():
    d = copy.deepcopy(good_draft())
    d.claims = []
    assert 8 in hard_items(d)


def test_adjacent_testimonials_are_attributed_to_the_nearest_name():
    # regression: found in the first real run — Ray's verbatim quote sat near Dana's name
    d = copy.deepcopy(good_draft())
    d.body.proof = ('Dana R. in Ohio said, "Then he explained who actually pays him and it clicked." '
                    'And Ray C., an analyst in Canada, said, "I went in looking for the catch. '
                    'The catch is that you have to actually do the weekly work." ' + d.body.proof)
    assert 8 not in hard_items(d)


def test_misattributed_testimonial_fails():
    d = copy.deepcopy(good_draft())
    d.body.proof = 'Theo M. said, "Then he explained who actually pays him and it clicked." ' + d.body.proof
    findings = code_checks(CLIENT, d, "cold").findings
    assert any("attributed to Theo M." in f.message and f.level == "hard" for f in findings)


def test_production_notes_cannot_invent_arrangements():
    # regression: found in the first real run (UGC note claimed a signed release)
    d = copy.deepcopy(good_draft())
    d.production_notes = ["Dana R. (the real member, with a signed release) reads the hook to camera."]
    assert 8 in hard_items(d)
    d.production_notes = ["Shoot at the 2019 Walmart store."]
    assert 8 in hard_items(d)


def test_conditional_member_direction_and_pacing_numbers_are_allowed():
    # regressions from the real run: conditional casting direction and "150 words per minute" are fine
    d = copy.deepcopy(good_draft())
    d.production_notes = ["Calm delivery, about 150 words per minute.",
                          "If Ray C. is available and has agreed to film, he speaks only his verbatim quote."]
    assert 8 not in hard_items(d)
    d.production_notes = ["Cut to the 12,000 members graphic."]
    assert 8 in hard_items(d)


def test_hook_plan_must_use_three_interrupt_types():
    d = copy.deepcopy(good_draft())
    for h in d.hook_plan:
        h.interrupt_type = "contrarian-admission"
    assert 1 in hard_items(d)
