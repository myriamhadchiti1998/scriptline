"""End-to-end pipeline behaviour with the offline mock model: triggers, gate,
revision loop, delivery, idempotent approval, idea memory, learning loop."""
from pathlib import Path

from app import db, memory, pipeline
from app.config import settings

CID = "sovereign_storefront"


def setup_module(_):
    db.init()


def test_full_pipeline_end_to_end():
    run_id = pipeline.start_ideation_run(CID, 8, trigger="test", background=False)
    run = db.get_run(run_id)
    assert run["status"] == "completed", run["error"]
    assert run["duplicates_dropped"] >= 1  # mock plants one near-duplicate

    ideas = [i for i in db.list_ideas(CID) if i["run_id"] == run_id]
    assert ideas and all(i["status"] == "pending" for i in ideas)
    for i in ideas:  # required idea fields + ICE with reasoning
        for f in ("concept_hook", "creative_type", "angle", "lead_type", "proof_point_ids", "target_avatar",
                  "pain_addressed", "ice_impact", "ice_confidence", "ice_ease", "ice_total"):
            assert i[f] not in (None, "", []), f
        assert i["ice_reasoning"]["impact"] and i["ice_reasoning"]["verdict"]

    # human gate: approve one, reject one
    a, r = ideas[0], ideas[1]
    pipeline.decide(r["id"], "rejected", "too generic", background=False)
    assert db.get_script_by_idea(r["id"]) is None
    pipeline.decide(a["id"], "approved", background=False)
    s = db.get_script_by_idea(a["id"])
    assert s["status"] == "delivered"
    assert Path(s["docx_path"]).exists() and Path(s["md_path"]).exists()

    # idempotent trigger: approving again creates no second script/job
    pipeline.decide(a["id"], "approved", background=False)
    assert len([x for x in db.list_scripts(CID) if x["idea_id"] == a["id"]]) == 1


def test_failing_draft_is_revised_then_delivered_and_never_shipped_first():
    idea = next(i for i in db.list_ideas(CID, "pending") if i["id"] % 4 == 0)  # mock plants a fabrication
    pipeline.decide(idea["id"], "approved", background=False)
    s = db.get_script_by_idea(idea["id"])
    versions = db.list_versions(s["id"])
    assert versions[0]["passed"] == 0 and 8 in versions[0]["review"]["failed_items"]
    assert versions[-1]["passed"] == 1 and s["status"] == "delivered"
    assert "10,000" not in Path(s["md_path"]).read_text()


def test_script_held_when_revisions_exhausted():
    object.__setattr__(settings, "max_revisions", 0)  # settings is frozen; tests override explicitly
    try:
        if not any(i["id"] % 4 == 0 for i in db.list_ideas(CID, "pending")):
            pipeline.start_ideation_run(CID, 6, background=False)
        idea = next(i for i in db.list_ideas(CID, "pending") if i["id"] % 4 == 0)
        pipeline.decide(idea["id"], "approved", background=False)
        s = db.get_script_by_idea(idea["id"])
        assert s["status"] == "held"
        assert s["docx_path"] is None                      # nothing delivered
        assert "_HELD" in s["md_path"] and "/held/" in s["md_path"]
    finally:
        object.__setattr__(settings, "max_revisions", 1)


def test_second_run_does_not_repeat_concepts():
    before = {i["concept_hook"] for i in db.list_ideas(CID)}
    run_id = pipeline.start_ideation_run(CID, 4, background=False)
    new = [i["concept_hook"] for i in db.list_ideas(CID) if i["run_id"] == run_id]
    assert new and not (set(new) & before)


def test_learning_loop_inputs_reflect_history():
    assert "APPROVED" in memory.approver_signal_text(CID) or "approved" in memory.approver_signal_text(CID)
    assert "Exemplar" in memory.exemplars_text(CID)
    assert "failed" in memory.watchouts_text(CID)  # the planted fabrication was recorded
    snap = memory.learning_snapshot(CID)
    assert snap["human_decisions"] >= 2 and snap["exemplars_available"] >= 1


def test_similarity_calibration():
    a = "Somebody got paid the day you bought that last course. It wasn't you."
    assert memory.similarity(a, a.replace("It wasn't you.", "And it wasn't you.")) >= settings.duplicate_threshold
    assert memory.similarity(a, "A corner of the garage. A few labeled bins.") < 0.3
