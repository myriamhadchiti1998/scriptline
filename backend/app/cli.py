"""Command-line entry points (same pipeline as the dashboard).

    python -m app.cli run [--batch 12] [--client sovereign_storefront]   # trigger 1 (cron-friendly)
    python -m app.cli ideas [--status pending]
    python -m app.cli approve <idea_id> [<idea_id> ...]                   # trigger 2
    python -m app.cli reject <idea_id> [--note "..."]
    python -m app.cli gate-test                                          # red-team the quality gate
    python -m app.cli export-samples [--out ../samples]                  # package outputs for submission
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

from . import db, pipeline, redteam
from .clientcfg import load_client
from .config import BACKEND_DIR, settings


def _print_ideas(rows: list[dict]) -> None:
    for i in rows:
        print(f"#{i['id']:>4} [{i['status']:<8}] ICE {i['ice_total']:>4} (I{i['ice_impact']} C{i['ice_confidence']} "
              f"E{i['ice_ease']}) {i['target_avatar']:<8} {i['funnel_stage']:<11} {i['concept_hook']}")


def export_samples(client_id: str, out: Path) -> Path:
    client = load_client(client_id)
    out.mkdir(parents=True, exist_ok=True)
    ideas = db.list_ideas(client_id)

    with (out / "ideas_ice_scored.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "run", "status", "concept_hook", "creative_type", "angle", "lead_type", "hook_family",
                    "proof_point_ids", "proof_points_text", "target_avatar", "pain_addressed", "funnel_stage",
                    "ice_impact", "ice_confidence", "ice_ease", "ice_total", "impact_reasoning",
                    "confidence_reasoning", "ease_reasoning", "verdict"])
        for i in ideas:
            r = i.get("ice_reasoning") or {}
            w.writerow([i["id"], i["run_id"], i["status"], i["concept_hook"], i["creative_type"], i["angle"],
                        i["lead_type"], i["hook_family"], " ".join(i["proof_point_ids"]),
                        " || ".join(client.proof_text(p) for p in i["proof_point_ids"]),
                        client.avatar_label(i["target_avatar"]), i["pain_addressed"], i["funnel_stage"],
                        i["ice_impact"], i["ice_confidence"], i["ice_ease"], i["ice_total"], r.get("impact"),
                        r.get("confidence"), r.get("ease"), r.get("verdict")])

    md = [f"# ICE-scored ideas — {client.name}", "",
          f"{len(ideas)} concepts across {len({i['run_id'] for i in ideas})} run(s). Sorted by run, then ICE total.", ""]
    for i in ideas:
        r = i.get("ice_reasoning") or {}
        md += [f"## #{i['id']} · ICE {i['ice_total']} · {i['status'].upper()}", "",
               f"**Concept / hook:** {i['concept_hook']}  ", f"**Creative type:** {i['creative_type']} · "
               f"**Lead type:** {i['lead_type']} · **Funnel:** {i['funnel_stage']} · **Hook family:** {i['hook_family']}  ",
               f"**Angle:** {i['angle']}  ", f"**Target avatar / pain:** {client.avatar_label(i['target_avatar'])} — {i['pain_addressed']}  ",
               "**Supporting proof:** " + "; ".join(f"`{p}` {client.proof_text(p)}" for p in i["proof_point_ids"]), "",
               f"| ICE | Score | Reasoning |", "|---|---|---|",
               f"| Impact | {i['ice_impact']} | {r.get('impact', '')} |",
               f"| Confidence | {i['ice_confidence']} | {r.get('confidence', '')} |",
               f"| Ease | {i['ice_ease']} | {r.get('ease', '')} |", "",
               f"**Verdict:** {r.get('verdict', '')}" + (f"  \n**Risk flags:** {', '.join(r['risk_flags'])}" if r.get("risk_flags") else ""),
               ""]
    (out / "ideas_ice_scored.md").write_text("\n".join(md), encoding="utf-8")

    for sub in ("delivered", "held"):
        src = settings.output_dir / client_id / sub
        if src.exists():
            dst = out / sub
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    reviews = []
    for s in db.list_scripts(client_id):
        for v in db.list_versions(s["id"]):
            if v.get("review"):
                reviews.append({"script_id": s["id"], "idea_id": s["idea_id"], "version": v["version"],
                                "final_status": s["status"], "passed": v["review"]["passed"],
                                "failed_items": v["review"]["failed_items"], "review": v["review"], "script": v["content"]})
    (out / "review_reports.json").write_text(json.dumps(reviews, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    ap.add_argument("--client", default=settings.default_client)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--batch", type=int, default=settings.batch_size)
    i = sub.add_parser("ideas"); i.add_argument("--status")
    a = sub.add_parser("approve"); a.add_argument("ids", type=int, nargs="+")
    j = sub.add_parser("reject"); j.add_argument("ids", type=int, nargs="+"); j.add_argument("--note")
    sub.add_parser("gate-test")
    e = sub.add_parser("export-samples"); e.add_argument("--out", default=str(BACKEND_DIR.parent / "samples"))
    args = ap.parse_args(argv)

    db.init()
    if args.cmd == "run":
        run_id = pipeline.start_ideation_run(args.client, args.batch, trigger="cli", background=False)
        run = db.get_run(run_id)
        print(f"Run #{run_id}: {run['status']} — kept {run['kept']}, dupes dropped {run['duplicates_dropped']}, "
              f"invalid dropped {run['invalid_dropped']}" + (f" — {run['error']}" if run["error"] else ""))
        _print_ideas([x for x in db.list_ideas(args.client) if x["run_id"] == run_id])
    elif args.cmd == "ideas":
        _print_ideas(db.list_ideas(args.client, args.status))
    elif args.cmd == "approve":
        for idea_id in args.ids:
            pipeline.decide(idea_id, "approved", background=False)
            s = db.get_script_by_idea(idea_id)
            print(f"idea #{idea_id} → script #{s['id']}: {s['status']}  {s.get('docx_path') or s.get('md_path') or ''}")
    elif args.cmd == "reject":
        for idea_id in args.ids:
            pipeline.decide(idea_id, "rejected", args.note, background=False)
            print(f"idea #{idea_id} rejected")
    elif args.cmd == "gate-test":
        res = redteam.run(load_client(args.client))
        for x in res["results"]:
            print(f"{'HELD ✔' if x['held'] else 'LEAKED ✘'}  {x['script']}  failed items {x['failed_items']} "
                  f"(code caught {x['caught_by_code_items']})")
        return 0 if res["all_held"] else 1
    elif args.cmd == "export-samples":
        print(f"Samples written to {export_samples(args.client, Path(args.out))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
