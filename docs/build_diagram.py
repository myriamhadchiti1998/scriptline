"""Generates docs/architecture.svg and docs/architecture.png (the graded architecture diagram).

Hand-laid SVG (fixed coordinates) so the diagram stays readable; regenerate with:
    python docs/build_diagram.py
PNG export uses Playwright/Chromium if available.
"""
from __future__ import annotations

import html
from pathlib import Path

W, H = 1640, 2040
OUT = Path(__file__).resolve().parent

C = {
    "ink": "#1b1f27", "muted": "#6b7280", "line": "#4a5160",
    "blue": "#1d4e89", "blue_s": "#e8eef7",
    "amber": "#9a6200", "amber_s": "#fbf1dc", "gate_s": "#fff3d6",
    "violet": "#5b3fa8", "violet_s": "#efeafb",
    "red": "#b42318", "red_s": "#fbe9e7",
    "green": "#1e7b4f", "green_s": "#e5f3ec",
    "grey_s": "#f5f4ef", "grey": "#c9c6bc",
}
parts: list[str] = []


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def text(x, y, s, size=12, weight=400, color=None, anchor="middle", italic=False):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color or C["ink"]}" '
                 f'text-anchor="{anchor}"{" font-style=\"italic\"" if italic else ""}>{esc(s)}</text>')


def box(x, y, w, h, title, lines=(), *, fill="#fff", stroke=None, sw=1.4, tag=None, tag_color=None,
        title_color=None, dash=None, title_size=14, line_size=11.5, rx=10, align="middle"):
    stroke = stroke or C["grey"]
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{f" stroke-dasharray=\"{dash}\"" if dash else ""}/>')
    tx = x + w / 2 if align == "middle" else x + 14
    cy = y + 22
    if tag:
        text(tx, cy - 2, tag, 10, 700, tag_color or stroke, anchor=align)
        cy += 16
    text(tx, cy, title, title_size, 700, title_color or C["ink"], anchor=align)
    cy += 18
    for ln in lines:
        bold = ln.startswith("**")
        text(tx, cy, ln.strip("*"), line_size, 600 if bold else 400, C["ink"] if bold else "#3d4452", anchor=align)
        cy += line_size + 4.5


def arrow(points, color=None, width=2, dash=None, head=True, label=None, lx=None, ly=None, lcolor=None,
          lanchor="start", lsize=11):
    color = color or C["line"]
    d = "M " + " L ".join(f"{px},{py}" for px, py in points)
    marker = f' marker-end="url(#a-{color[1:]})"' if head else ""
    parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"'
                 f'{f" stroke-dasharray=\"{dash}\"" if dash else ""}{marker}/>')
    if label:
        text(lx, ly, label, lsize, 600, lcolor or color, anchor=lanchor)


def diamond(cx, cy, w, h, title, sub, stroke):
    pts = f"{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}"
    parts.append(f'<polygon points="{pts}" fill="#fff" stroke="{stroke}" stroke-width="2"/>')
    text(cx, cy - 4, title, 13.5, 700)
    text(cx, cy + 13, sub, 10.5, 400, "#3d4452")


# ── layout constants ─────────────────────────────────────────────────────────
MX, MW = 520, 600            # main column
MC = MX + MW / 2             # main column centre
LX, LW = 40, 330             # left column (context)
RX, RW = 1270, 330           # right column (learning)
BUS_L = 430                  # context injection bus x
BUS_R = 1190                 # learning bus x

# title
text(W / 2, 46, "Scriptline — AI ideation + scripting pipeline", 26, 800)
text(W / 2, 72, "Python (FastAPI · SQLite · worker pool)  +  Next.js approval dashboard  +  Claude API   ·   "
                "2 triggers · 1 human gate · 2 distinct generation stages · 0 manual steps from approval to delivery",
     13, 400, C["muted"])

# legend
lg_y = 104
for i, (lbl, col, dash) in enumerate([("main flow", C["line"], None), ("context injected into prompt / rules", C["amber"], "5 4"),
                                       ("learning loop (self-improvement)", C["violet"], "7 5"), ("AI call", C["blue"], None),
                                       ("deterministic code", C["grey"], None)]):
    x0 = 170 + i * 270
    if i < 3:
        arrow([(x0, lg_y), (x0 + 34, lg_y)], col, 2, dash, head=True)
    else:
        parts.append(f'<rect x="{x0}" y="{lg_y - 8}" width="34" height="16" rx="4" fill="#fff" stroke="{col}" stroke-width="2"/>')
    text(x0 + 44, lg_y + 4, lbl, 11.5, 500, C["muted"], anchor="start")

# ── LEFT: context sources ────────────────────────────────────────────────────
parts.append(f'<rect x="{LX - 14}" y="140" width="{LW + 28}" height="560" rx="14" fill="none" stroke="{C["amber"]}" '
             f'stroke-width="1.4" stroke-dasharray="6 5"/>')
text(LX + LW / 2, 164, "CONTEXT SOURCES", 13, 800, C["amber"])
text(LX + LW / 2, 181, "clients/<client_id>/ — a new client is a folder, not a rebuild", 10.5, 400, C["muted"])
box(LX, 196, LW, 120, "reference_pack.md", ["verbatim client Reference Pack", "injected into EVERY AI call as the",
                                             "single source of truth (prompt-cached", "system prefix)"],
    fill=C["amber_s"], stroke=C["amber"])
box(LX, 330, LW, 170, "client.yaml", ["**proof bank with IDs (C1…T5)**", "fact allowlists: numbers, $, %, names",
                                       "forbidden entities · banned language", "CTA terms per funnel stage",
                                       "avatars · creative & lead types", "voice / rhythm / length thresholds"],
    fill=C["amber_s"], stroke=C["amber"])
box(LX, 514, LW, 92, "knowledge/craft_playbook.md", ["client-agnostic craft: hook patterns,", "PPPC structure, open loops, ICE rubric"],
    fill=C["amber_s"], stroke=C["amber"])
box(LX, 620, LW, 66, "prompts/1-4_*.md", ["4 purpose-built prompts, editable as files"], fill=C["amber_s"], stroke=C["amber"])

# context bus
arrow([(LX + LW + 14, 420), (BUS_L, 420)], C["amber"], 2, "5 4", head=False)
arrow([(BUS_L, 230), (BUS_L, 1330)], C["amber"], 2.4, "5 4", head=False)
text(BUS_L + 6, 222, "context bus ↓", 11, 700, C["amber"], anchor="start")

# ── RIGHT: learning memory ───────────────────────────────────────────────────
parts.append(f'<rect x="{RX - 14}" y="140" width="{RW + 28}" height="330" rx="14" fill="none" stroke="{C["violet"]}" '
             f'stroke-width="1.4" stroke-dasharray="7 5"/>')
text(RX + RW / 2, 164, "LEARNING MEMORY (SQLite)", 13, 800, C["violet"])
text(RX + RW / 2, 181, "the system starts warm on every run", 10.5, 400, C["muted"])
mem_items = [("① Idea memory", "every concept ever generated → never repeated"),
             ("② Approver signal", "approve/reject stats by avatar, type, angle + notes"),
             ("③ Exemplars", "top-scoring delivered scripts"),
             ("④ Watch-outs", "checklist items past drafts failed most")]
for i, (t, s) in enumerate(mem_items):
    y = 196 + i * 66
    box(RX, y, RW, 56, t, [s], fill=C["violet_s"], stroke=C["violet"], title_size=13, line_size=11)

arrow([(RX - 14, 330), (BUS_R, 330)], C["violet"], 2, "7 5", head=False)
arrow([(BUS_R, 230), (BUS_R, 1010)], C["violet"], 2.4, "7 5", head=False)
text(BUS_R - 6, 222, "↓ learning bus", 11, 700, C["violet"], anchor="end")

# ── MAIN FLOW ────────────────────────────────────────────────────────────────
y_t1 = 140
box(MX + 90, y_t1, MW - 180, 62, "⚡ TRIGGER 1 — start a run", ["dashboard button · POST /api/runs · CLI · cron"],
    fill=C["blue"], stroke=C["blue"], title_color="#fff")
parts[-1] = parts[-1].replace(f'fill="#3d4452"', 'fill="#dfe7f3"')
for k in range(2, 4):
    parts[-k] = parts[-k].replace(f'fill="#3d4452"', 'fill="#dfe7f3"')

y1 = 232
box(MX, y1, MW, 104, "STAGE 1 · IDEATION", ["prompts/1_ideation.md · role: senior creative strategist",
                                            "batch of 12 concepts, 11 structured fields each",
                                            "JSON-schema output: proof IDs / avatars / types are enums"],
    tag="AI CALL #1 — GENERATION STAGE 1", tag_color=C["blue"], stroke=C["blue"], sw=2.2)
arrow([(MC, y_t1 + 62), (MC, y1)])

yg = 366
box(MX, yg, MW, 104, "Idea guards", ["validate every field vs client.yaml · compliance scan of the hook",
                                     "procedural hook on cold traffic → drop · UGC needs a real testimonial",
                                     "near-duplicate of memory or batch (similarity ≥ 0.62) → drop · 1 top-up"],
    tag="CODE", tag_color=C["muted"], fill=C["grey_s"])
arrow([(MC, y1 + 104), (MC, yg)])

y2 = 500
box(MX, y2, MW, 104, "STAGE 2 · ICE SCORING", ["prompts/2_ice_scoring.md · role: independent analyst (not the author)",
                                               "Impact / Confidence / Ease 1–10, written reasoning for each",
                                               "+ 3-second verdict + risk flags · unscored ideas re-asked"],
    tag="AI CALL — SEPARATE PROMPT", tag_color=C["blue"], stroke=C["blue"], sw=2.2)
arrow([(MC, yg + 104), (MC, y2)])

yd = 634
parts.append(f'<path d="M {MX + 60} {yd + 10} a 240 10 0 0 0 {MW - 120} 0 v 64 a 240 10 0 0 1 -{MW - 120} 0 z" '
             f'fill="{C["blue_s"]}" stroke="{C["blue"]}" stroke-width="1.6"/>')
parts.append(f'<ellipse cx="{MC}" cy="{yd + 10}" rx="{(MW - 120) / 2}" ry="10" fill="#f3f6fb" stroke="{C["blue"]}" stroke-width="1.6"/>')
text(MC, yd + 40, "SQLite · ideas table", 14, 700)
text(MC, yd + 58, "11 fields + ICE + reasoning · status = pending · keyed by client_id", 11.5, 400, "#3d4452")
arrow([(MC, y2 + 104), (MC, yd)])

yh = 744
box(MX - 20, yh, MW + 40, 96, "👤 HUMAN APPROVAL GATE — Next.js dashboard",
    ["approval queue sorted by ICE · proof text + score reasoning + memory similarity shown",
     "Approve  /  Reject  (+ optional note)  — the ONLY manual step"],
    tag="THE ONE MANUAL STEP", tag_color=C["amber"], fill=C["gate_s"], stroke=C["amber"], sw=2.6)
arrow([(MC, yd + 84), (MC, yh)])

yt2 = 872
box(MX + 90, yt2, MW - 180, 62, "⚡ TRIGGER 2 — Approve clicked", ["POST /api/ideas/{id}/decision"],
    fill=C["blue"], stroke=C["blue"], title_color="#fff")
for k in range(1, 4):
    parts[-k] = parts[-k].replace(f'fill="#3d4452"', 'fill="#dfe7f3"')
arrow([(MC, yh + 96), (MC, yt2)], label="Approve", lx=MC + 10, ly=yh + 118)

yo = 962
box(MX, yo, MW, 86, "Atomic handoff (one DB transaction)",
    ["status → approved + script row created (UNIQUE per idea): double-clicks",
     "can never spawn two jobs · queued on worker pool · resumed after restart"],
    tag="CODE", tag_color=C["muted"], fill=C["grey_s"])
arrow([(MC, yt2 + 62), (MC, yo)])

y5 = 1078
box(MX, y5, MW, 140, "STAGE 5 · SCRIPT GENERATION",
    ["prompts/3_scripting.md · role: direct-response scriptwriter",
     "in: full idea record + full text of cited proof + client context",
     "    + exemplars ③ + watch-outs ④ (+ failure report on revision)",
     "out: notes · hook plan (3 interrupt types) · Hook 1/2/3 · Pain › Promise › Proof › CTA",
     "**+ open loop + claim ledger: every factual claim → proof ID**"],
    tag="AI CALL #2 — GENERATION STAGE 2 (SEPARATE PROMPT)", tag_color=C["blue"], stroke=C["blue"], sw=2.2)
arrow([(MC, yo + 86), (MC, y5)])

# quality gate container
yq = 1250
parts.append(f'<rect x="{MX - 40}" y="{yq}" width="{MW + 80}" height="404" rx="14" fill="#fffafa" stroke="{C["red"]}" stroke-width="2"/>')
text(MC, yq + 24, "STAGE 6 · QUALITY GATE — hybrid; the code decides pass/fail, not the model", 13.5, 800, C["red"])
arrow([(MC, y5 + 140), (MC, yq)])
ya = yq + 40
box(MX - 16, ya, MW + 32, 128, "Layer A · deterministic checks",
    ["#8 every number, $ and % vs. allowlist (copy AND notes) · forbidden entities · invented names",
     "     testimonial quotes must be verbatim · claim ledger must cite real IDs",
     "#7 banned language (negation-aware) · no “!” or ALL-CAPS · sentence rhythm",
     "#6 60–180 s for EVERY hook variant · #5 CTA terms per funnel stage",
     "#1 first sentence ≤ 20 words, 3 distinct hooks + interrupt types · #4 proof · #10 sections"],
    tag="CODE — CANNOT BE TALKED OUT OF A VERDICT", tag_color=C["red"], fill=C["red_s"], stroke=C["red"], line_size=11)
yb = ya + 150
box(MX - 16, yb, MW + 32, 104, "Layer B · AI reviewer",
    ["prompts/4_quality_review.md · scores each of the 10 items 1–5 vs. written anchors",
     "+ evidence quote · 5 voice sub-scores · independent claim audit (ID or UNSUPPORTED)",
     "· rules on context-dependent flags, e.g. “…won’t insult you by calling it passive”"],
    tag="AI CALL — SEPARATE REVIEWER PROMPT", tag_color=C["red"], fill=C["red_s"], stroke=C["red"], line_size=11)
arrow([(MC, ya + 128), (MC, yb)], label="hard findings + flags passed in", lx=MC + 10, ly=ya + 143, lsize=10.5)
yc = yb + 104 + 52
diamond(MC, yc, 440, 80, "All 10 items pass?", "no hard finding AND AI ≥ 4 (+voice ≥ 3, 0 unsupported)", C["red"])
arrow([(MC, yb + 104), (MC, yc - 37)])

# branches
ydl = 1745
box(MC + 70, ydl, 420, 118, "✅ STAGE 7 · DELIVERY",
    ["output/<client>/delivered/NNN_title.docx + .md", "p.1 notes (top) · Hook 1/2/3 · main body",
     "p.2 QA scorecard + claim ledger", "download from dashboard · status = delivered"],
    fill=C["green_s"], stroke=C["green"], sw=2.4)
arrow([(MC + 220, yc), (MC + 280, yc), (MC + 280, ydl)], C["green"], 2.4, label="YES", lx=MC + 290, ly=yc - 8)

rv_x, rv_y = MX - 150, yc
diamond(rv_x, rv_y + 100, 220, 70, "Revisions left?", "MAX_REVISIONS = 1", C["amber"])
arrow([(MC - 220, yc), (rv_x, yc), (rv_x, rv_y + 65)], C["red"], 2.4, label="NO", lx=rv_x + 10, ly=yc - 8)
arrow([(rv_x - 110, rv_y + 100), (rv_x - 130, rv_y + 100), (rv_x - 130, y5 + 112), (MX, y5 + 112)], C["amber"], 2,
      label="yes → rewrite with failure report", lx=rv_x - 122, ly=y5 + 104, lsize=10.5)
box(rv_x - 150, ydl + 50, 330, 96, "⛔ HELD — never delivered",
    ["output/<client>/held/NNN_HELD.md failure report", "visible in dashboard · “Retry job” button"],
    fill=C["red_s"], stroke=C["red"], sw=2.4)
arrow([(rv_x, rv_y + 135), (rv_x, ydl + 50)], C["red"], 2.4, label="no", lx=rv_x + 10, ly=rv_y + 160)

# ── injections from the context bus ──────────────────────────────────────────
for y, lbl in [(y1 + 52, "pack + playbook"), (yg + 52, "yaml: enums, rules"), (y2 + 52, "pack + playbook"),
               (y5 + 36, "pack + yaml CTAs"), (ya + 64, "yaml: allowlists"), (yb + 52, "pack + checklist")]:
    tgt = MX - 16 if y >= ya else MX
    arrow([(BUS_L, y), (tgt, y)], C["amber"], 1.8, "5 4", label=lbl, lx=BUS_L + 6, ly=y - 6, lsize=10)

# ── learning bus: reads ──────────────────────────────────────────────────────
for y, lbl in [(y1 + 70, "① ②"), (yg + 70, "①"), (y2 + 70, "②"), (y5 + 100, "③ ④")]:
    arrow([(BUS_R, y), (MX + MW, y)], C["violet"], 1.8, "7 5", label=lbl, lx=BUS_R - 6, ly=y - 6, lanchor="end", lsize=10)

# ── learning loop: writes ────────────────────────────────────────────────────
fx = RX + RW / 2
arrow([(MX + MW + 20, yh + 48), (fx - 40, yh + 48), (fx - 40, 470)], C["violet"], 2, "7 5",
      label="decisions + notes → ②", lx=MX + MW + 30, ly=yh + 40, lsize=10.5)
arrow([(MC + 490, ydl + 59), (fx + 40, ydl + 59), (fx + 40, 470)], C["violet"], 2, "7 5",
      label="delivered → ③ exemplar", lx=MC + 500, ly=ydl + 51, lsize=10.5)
arrow([(MX + MW + 40, yc - 20), (fx, yc - 20), (fx, 470)], C["violet"], 2, "7 5",
      label="every review's failures → ④", lx=MX + MW + 50, ly=yc - 28, lsize=10.5)
arrow([(MX + MW, yd + 40), (fx - 80, yd + 40), (fx - 80, 470)], C["violet"], 2, "7 5",
      label="all ideas → ①", lx=MX + MW + 80, ly=yd + 32, lsize=10.5)

# footer row
fy, fw = 1918, 506
box(40, fy, fw, 100, "Scaling to more clients", ["new folder in clients/ (pack + yaml) → appears in the dashboard",
                                                 "every DB row keyed by client_id · prompts are templates, no client text",
                                                 "models per stage in .env · SQLite → Postgres is a driver swap"],
    fill="#fff", stroke=C["grey"], title_size=13, line_size=11)
box(40 + fw + 21, fy, fw, 100, "Reliability", ["SDK retries 429 / 5xx with backoff · invalid JSON re-asked with the error",
                                               "refusal / truncation → typed error · every step → event log → live UI",
                                               "crash recovery resumes script jobs · failed jobs retryable from the UI"],
    fill="#fff", stroke=C["grey"], title_size=13, line_size=11)
box(40 + 2 * (fw + 21), fy, fw, 100, "Gate red-team (built in) + tests", ["pushes the pack's 3 losing scripts through the real gate on demand",
                                                                         "→ all 3 held; report shows which layer caught what",
                                                                         "39 automated tests (gate, pipeline, API contract) run offline"],
    fill="#fff", stroke=C["grey"], title_size=13, line_size=11)

defs = "".join(
    f'<marker id="a-{col[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{col}"/></marker>'
    for col in {C["line"], C["amber"], C["violet"], C["red"], C["green"], C["blue"]})
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="Helvetica, Arial, sans-serif"><defs>{defs}</defs>'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>' + "".join(parts) + "</svg>")
(OUT / "architecture.svg").write_text(svg, encoding="utf-8")

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
        pg.set_content(f"<html><body style='margin:0'>{svg}</body></html>")
        pg.screenshot(path=str(OUT / "architecture.png"), full_page=True)
        pg.pdf(path=str(OUT / "architecture.pdf"), width=f"{W}px", height=f"{H}px", print_background=True)
        b.close()
    print("wrote architecture.svg / .png / .pdf")
except Exception as e:  # pragma: no cover
    print(f"wrote architecture.svg (PNG export skipped: {e})")
