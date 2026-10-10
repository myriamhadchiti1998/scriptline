# Loom walkthrough — talk track (target 14–16 min)

Speak to the bullets; don't read them. **Bold** = say it close to verbatim. Times are cumulative.

## Before you hit record (5 minutes)

- [ ] `./start.sh` running. Dashboard open at localhost:3000 in one tab, the repo open in VS Code in another, `docs/architecture.png` open in a third.
- [ ] Start from a database that already holds one earlier run with a few decisions, so the learning-loop numbers aren't zero. Do **not** wipe `backend/data/`.
- [ ] Batch size 8 (faster on camera). Close notifications. Set the Loom link to *anyone with the link can view*.
- [ ] Have one delivered `.docx` from an earlier run ready to open, in case Word is slow.

---

## 0:00 – 1:30 · The business problem (they are listening for this)

- **"Right now scripts are written by hand, 8 in 10 need structural rework, and senior people lose hours reviewing drafts. The brief says the cause is structural: no enforced framework, no automated quality gate, and no standard client context at ideation. So I built the structure."**
- Three ideas in one sentence each:
  1. The client's context is injected into every AI call from one source of truth.
  2. The winning structure is a data contract the model must fill, not a suggestion.
  3. Nothing reaches the client unless it passes a gate that code enforces.
- **"The one thing I treated as zero-tolerance is fabricated proof, and I'll show you five separate controls for it."**

## 1:30 – 2:30 · Kick off the live run (Trigger 1), then explain while it works

- Click **▶ Generate & score ideas**. Point at the pipeline strip and the live activity log.
- **"That's trigger one. It can also be a cron job, an API call, or the CLI. Stage 1 is now generating concepts. While it runs, here's the architecture."**

## 2:30 – 5:00 · Architecture (switch to the diagram)

- Walk it top to bottom:
  - **Context sources** on the left feed every stage. Point out *reference_pack verbatim* and *client.yaml* (proof bank with IDs and the allowlists).
  - **Stage 1**, then the **code guards**, then **Stage 2** (a separate scorer).
  - **SQLite**, then the **human gate**, then **trigger 2**, then the **atomic handoff**.
  - **Stage 5**, then the **quality gate** (two layers), then the **delivered / revise / held** branches.
- **"Ideation and scripting are two separate calls with separate prompts, schemas and roles. Scoring and review are also separate calls, because the model that wrote something should never be the one grading it."**
- Learning memory on the right: ① idea memory ② approver signal ③ exemplars ④ watch-outs. **"Every run starts warm, not cold."**
- **Scaling:** **"A new client is a folder: a reference pack and a YAML file. No prompt contains client text, and every database row is keyed by client."**
- **Why this stack.** A custom Python service, rather than n8n or Make, because the quality gate is real logic: allowlists, quote matching, per-item rules. Here it's readable, version-controlled and covered by 39 tests. Prompts are still plain markdown files a strategist can edit. Next.js plus SQLite rather than Sheets, because the approver needs reasoning, proof text and script status on one screen, and because the approval is a database transaction, not a polled spreadsheet cell. Claude, because it handles long brand context well, has structured outputs, and prompt caching makes the reference pack cheap to resend.

## 5:00 – 7:00 · Ideas landed: the approval gate

- Back to the dashboard and the approval queue (sorted by ICE). Open one card:
  - Hook, creative type, lead type, funnel stage, angle, avatar and pain.
  - **Proof shown by ID with the exact pack text**: "the approver can see the proof is real."
  - Open **Why these scores**: a rationale for each of I, C and E, a verdict, and risk flags. **"Nobody has to trust a bare number."**
  - Point at *memory: closest prior #…*. **"Idea memory. This run dropped N near-duplicates."** Show the Last run panel.
- **Reject one** and type a note (e.g. "too close to our usual angle"). **"That note and the decision feed the next run."**
- **Approve two.** **"That click is trigger two. The approval and the job are created in one database transaction, so a double-click can't create two scripts."** Point at the strip moving to *Script*.

## 7:00 – 8:30 · Prompt approach and anti-fabrication (switch to the code)

- Open `prompts/1_ideation.md` and `3_scripting.md` briefly. Each has one role and one job, and contains no client text.
- The five controls, one line each:
  1. **Schema enums**: "the model literally cannot output a proof ID that doesn't exist."
  2. **Claim ledger**: every claim must cite a proof ID.
  3. **Code fact gate**: every number, dollar figure and percentage is checked against `client.yaml`. Also forbidden entities, invented names, and verbatim testimonial quotes. Show `client.yaml` `facts:`.
  4. **Independent AI claim audit**: a claim with no proof ID is marked UNSUPPORTED and fails.
  5. **The pack's losing scripts** are in context as negatives, and the gate is red-teamed against them.

## 8:30 – 11:00 · Script lands: how the quality gate decides

- Scripts tab. The card shows *Approved ✓ → Scripted → Quality gate → Delivered*. Open **Show script & QA detail**.
- Read Hook 1 out loud, then point at the three hooks and the four body sections.
- The 10 cells: **"Each item passes only if there is no hard code finding AND the AI reviewer scored it 4 or more out of 5. Voice also needs every sub-score at 3 or above, and fabrication needs zero unsupported claims. The code makes that decision, not the model. I never ask 'is this good?'."**
- Show a **flag** row. For example, *"passive"* in Marcus's own line "I won't insult you by calling it passive". **"Code can't judge that context, so it's passed to the reviewer as a flag. A promise of 'passive' is a hard fail."**
- If a script went through **v1 ✕ → v2 ✓**, click v1 and show what failed and how the revision fixed it.
- Click **⬇ Download .docx** and open it. Page 1 is clean for the copy team (notes on top, three hooks, body). Page 2 is the QA scorecard and claim ledger. **"Zero manual steps between the approve click and this file."**

## 11:00 – 12:30 · The held branch

- Click **Red-team the gate**. **"These are the three losing scripts from the pack, pushed through the real gate. All three are held."** Point at the fabrication reasons: *$5,000 a month*, *40,000*, *Walmart*, *Greg*, *students*, *FIRE YOUR BOSS*. Also show *code caught*: **"the code layer catches them before the model is even consulted."**
- If a real script was held during your runs, show it: the held status, the hold report, and the Retry button. Otherwise say: **"Live scripts that fail get one automatic rewrite with the exact failure report. If they fail again they're held in a held folder and never delivered."**

## 12:30 – 13:30 · Self-improvement

- Point at the Learning loop panel: ideas in memory, decisions learned from, exemplars, first-draft pass rate.
- **"Approvals and rejections steer ideation and calibrate the scorer's Confidence. The best delivered scripts become exemplars for the next scripts. The checklist items drafts fail most become watch-outs in the scripting prompt. So the system gets better instead of starting cold."**

## 13:30 – 15:00 · Troubleshooting (real issues from real runs)

Pick three. These all came from reading real model output, which is the point.

- **My gate had a false positive.** Two correct scripts were failed for "altered testimonial": Ray's verbatim quote sat near Dana's name, and the check attributed it to Dana. I fixed attribution to use the nearest name, and made a genuine misattribution its own hard fail, with a regression test.
- **The reviewer caught something my code didn't.** A UGC script's production notes said Dana "has a signed release" and had her read a hook that wasn't her words. That's fabricated proof hiding in the notes. I fixed it at three levels: a writer rule (members only speak their verbatim testimonial, and casting is conditional), a reviewer rule, and code that fact-checks production notes.
- **Over-correction, then calibration.** The first-draft pass rate dropped to 0/6 because my new check flagged "150 words per minute" and "*if* Ray has agreed to film". I scoped the checks to factual claims and it recovered to 4/6. The remaining failures were real quality catches. **"A gate that fails everything is as useless as one that passes everything."**
- **Same-door hooks were the top failure.** So I fixed it upstream: the writer must commit to a hook plan with three different interrupt types before writing, and code checks the plan.
- **Model API changes.** Sonnet 5.5 rejects `temperature`, forced `tool_choice` and prefill, so I use native structured outputs and re-validate with Pydantic, feeding validation errors back to the model.
- **Billing.** The account ran out of credits mid-run. The job showed "job error" with the real message, nothing was half-delivered, and it's one click to retry.

## 15:00 – 15:30 · Close

- **"Two generation stages, scoring with reasoning, one human gate that triggers everything after it, a quality gate that holds rather than ships, and a system that learns from every decision. Repo, diagram and sample outputs are in the email. Thanks for watching."**
