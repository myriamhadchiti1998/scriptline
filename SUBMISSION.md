# Submission checklist and email

## 0 · Before anything: add API credits

The key used during the build ran out of credits during the final run. The Loom needs a live end-to-end run, so top up at console.anthropic.com → Plans & Billing. Also **rotate the key** you shared in chat, and put the new one in `backend/.env`.

## 1 · Sample outputs: already produced

`samples/` already holds real output from the live API: 22 ICE-scored ideas, 8 delivered scripts and every review report. You can submit it as-is.

**Optional: open the dashboard with this real history** (so the learning-loop numbers aren't zero in your Loom):

```bash
mkdir -p backend/data output/sovereign_storefront
cp samples/pipeline_seed.db backend/data/pipeline.db
cp -r samples/delivered output/sovereign_storefront/
```

Script #7 will show "job error" (from the credits running out). Clicking **Retry job** on camera is a good moment to show error recovery.

If you'd rather generate fresh samples on your own machine:

1. Run `./start.sh` (or `.\start.ps1` on Windows) with your `ANTHROPIC_API_KEY` in `backend/.env`.
2. In the dashboard, click **Generate & score ideas** (batch 12).
3. Approve the 4–5 strongest ideas and reject 2–3 of them with a short note.
4. Wait for the scripts to finish, then click **Generate** again. This second run shows idea memory and the learning loop at work.
5. Click **Red-team the gate** once.
6. Export the samples:

   ```bash
   cd backend && python -m app.cli export-samples
   ```

   This fills `samples/`. Open two of the delivered `.docx` files and read them yourself before sending anything.

## 2 · Publish the repo

```bash
cd scriptline
git init && git add . && git commit -m "Scriptline: AI ideation + scripting pipeline"
# create an empty repo on GitHub (public, or private with access granted), then:
git remote add origin https://github.com/<you>/scriptline.git
git branch -M main && git push -u origin main
```

`.gitignore` already excludes `.env`, `node_modules`, the database and `output/`. The `samples/` folder **is** committed.

## 3 · Record the Loom

Follow `docs/LOOM_SCRIPT.md`. Aim for 10–20 minutes in one continuous live run. Set the link to **Anyone with the link can view**.

## 4 · Pre-send check

- [ ] The repo opens in a private/incognito window, and the prompts are visible in `backend/prompts/` and the review logic in `backend/app/stages/review.py`.
- [ ] `samples/` contains ICE-scored ideas and at least 3 delivered scripts.
- [ ] The diagram link or attachment opens without requesting access (`docs/architecture.png` or `.pdf`).
- [ ] The Loom is 10–20 minutes, its link is public-view, and it covers the live run, architecture, prompts, quality review and troubleshooting.
- [ ] One email goes to both addresses.

## 5 · Email

**To:** jahan@clientaccelerators.com, balaj.sikander@clientaccelerators.com
**Subject:** AI Systems Specialist Assessment, [Your Full Name]

> Hi Jahan, hi Balaj,
>
> Please find my submission for the AI Systems Specialist build below.
>
> 1. **Loom walkthrough:** [Loom link]
> 2. **Architecture diagram:** [GitHub link to docs/architecture.png] (also attached as PDF)
> 3. **Pipeline (code repo):** [GitHub repo link]. The four prompts are in `backend/prompts/`, the quality-review logic is in `backend/app/stages/review.py`, and setup is one command (see README).
> 4. **Sample outputs:** [GitHub link to /samples]. This includes the ICE-scored ideas with reasoning, delivered scripts (.docx and .md), and every review report.
>
> **In short:** it is a Python service with a Next.js approval dashboard on the Claude API. It has two triggers: "generate" and the approve click. Ideation and scripting are separate AI stages, and ICE scoring and review are run by independent prompts. The quality gate is a hybrid. Deterministic code checks every number, name and testimonial quote against the Reference Pack. An AI reviewer scores each checklist item against written anchors. Code makes the pass/fail decision, and failing scripts get one automatic revision before they are held. The system also learns from approvals, delivered exemplars and recurring failures, and never repeats a concept.
>
> Thanks for the opportunity. I'm happy to walk through any part of it live.
>
> Best,
> [Your Full Name]
