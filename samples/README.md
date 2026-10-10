# Sample outputs

Everything in this folder was produced by a **real run of the pipeline** with the Claude API (not the offline mock). Regenerate it at any time with:

```bash
cd backend && python -m app.cli export-samples
```

| File | What it is |
|---|---|
| `ideas_ice_scored.md` | Every generated idea with all of its fields, the full text of its cited proof, ICE scores with the reasoning for each, the verdict, and the human decision. |
| `ideas_ice_scored.csv` | The same data as a spreadsheet. |
| `delivered/*.docx` + `*.md` | Scripts that passed the 10-point gate, in their final delivered format. |
| `held/*_HELD.md` | Scripts the gate held, with the failure report. This folder only exists if a script was held. |
| `review_reports.json` | Every review of every script version: item scores, evidence, code findings, claim audit, and voice scores. |
| `pipeline_seed.db` | The real run's database. Optional: copy it to `backend/data/pipeline.db` to open the dashboard with this history (see SUBMISSION.md). |

## What's in this export (real run, Claude Sonnet 5.5)

- **22 ICE-scored ideas from 2 runs.** 13 human decisions were made with notes. Run 2 shows the learning loop at work: verbatim testimonials only, no invented specifics, and more emotional cold openers. It also shows idea memory: nothing in run 2 is more than 30% similar to a run-1 idea.
- **8 delivered scripts.** All passed 10/10. Three passed only after an automatic revision, and their failed first drafts and reviews are in `review_reports.json`.
- **Script #7 shows "job error".** The API account ran out of credits during its revision. Its first draft had genuinely failed review, because it invented an anecdote that the claim audit marked UNSUPPORTED. Retry it from the dashboard once credits are added.
- **No `held/` folder in this export.** In an earlier real run, the gate held a script that paraphrased Marisol V.'s testimonial in the third person. That database was reset for these clean samples. The held branch is demonstrated live by **Red-team the gate** and covered by tests.
