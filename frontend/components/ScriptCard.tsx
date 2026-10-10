"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Script, ScriptVersion } from "@/lib/types";
import { StatusPill } from "./StatusPill";

const LIVE = ["queued", "writing", "reviewing", "revising"];

function Steps({ s }: { s: Script }) {
  const st = s.status;
  const v = s.current_version || 1;
  const reviewed = ["revising", "delivered", "held"].includes(st);
  const items: { label: string; cls: string }[] = [
    { label: "Approved", cls: "done" },
    { label: `Scripted v${v}`, cls: st === "writing" || st === "queued" || st === "revising" ? "now" : "done" },
    { label: "Quality gate", cls: st === "reviewing" ? "now" : reviewed ? (st === "held" ? "fail" : "done") : "" },
  ];
  if (v > 1 || st === "revising") items.splice(2, 0, { label: "v1 failed → auto-revision", cls: "fail" });
  items.push({
    label: st === "held" ? "Held — not delivered" : st === "failed" ? "Job error" : "Delivered",
    cls: st === "delivered" ? "done" : st === "held" || st === "failed" ? "fail" : "",
  });
  return (
    <div className="steps">
      {items.map((i) => <span key={i.label} className={`step ${i.cls}`}>{i.cls === "done" ? "✓ " : i.cls === "fail" ? "✕ " : ""}{i.label}</span>)}
    </div>
  );
}

function hookLabel(c: ScriptVersion["content"], n: number, base: string) {
  const plan = c.hook_plan?.find((h) => h.hook === `hook_${n}`);
  return `Hook ${n} — ${base}${plan ? ` · ${plan.interrupt_type.replace(/-/g, " ")} · door: ${plan.door}` : ""}`;
}

function VersionView({ v, open }: { v: ScriptVersion; open: boolean }) {
  const r = v.review;
  const c = v.content;
  return (
    <>
      {r && (
        <div className="score-grid">
          {r.items.map((it) => (
            <div key={it.id} className={`cell ${it.passed ? "p" : "f"}`} title={`${it.id}. ${it.name}\n${it.passed ? it.evidence : it.fail_reasons.join("\n")}`}>
              #{it.id}<small>{it.passed ? "pass" : "FAIL"} · {it.ai_score}/5</small>
            </div>
          ))}
        </div>
      )}
      {open && r && (
        <div className="qa">
          <div style={{ fontSize: 12.5, color: "var(--muted)", margin: "2px 0 6px" }}>
            Pass rule: {r.pass_rule} · length {r.metrics.seconds_range[0]}–{r.metrics.seconds_range[1]}s ·
            avg sentence {r.metrics.avg_sentence_words} words · voice{" "}
            {["plainspoken", "unhurried_rhythm", "operational_specificity", "anti_hype", "avatar_language"]
              .map((k) => `${k.replace(/_/g, " ")} ${r.voice[k]}/5`).join(" · ")}
          </div>
          {r.items.map((it) => (
            <div className="qa-row" key={it.id}>
              <span className="mono">{it.id}</span>
              <div>
                <div className="nm">{it.name}</div>
                {it.passed ? <div className="ev">“{it.evidence}” — {it.reasoning}</div>
                  : it.fail_reasons.map((x, n) => <div className="rs" key={n}>✕ {x}</div>)}
                {it.code_checks.filter((f) => f.level === "flag" || !it.passed).map((f, n) => (
                  <div className="cc" key={n}><span className={f.level}>{f.level}</span>{f.message}</div>
                ))}
              </div>
              <span className={`pill ${it.passed ? "ok" : "bad"}`}>{it.passed ? "PASS" : "FAIL"} {it.ai_score}/5</span>
            </div>
          ))}
          {r.top_fix && <div className="banner info" style={{ marginTop: 8 }}><b>Reviewer’s top fix:</b> {r.top_fix}</div>}
        </div>
      )}
      {open && (
        <div className="script-text">
          {c.production_notes.length > 0 && (
            <div className="notes"><b>Production notes (videographer)</b><ul>{c.production_notes.map((n, i) => <li key={i}>{n}</li>)}</ul></div>
          )}
          {[[hookLabel(c, 1, "pattern interrupt"), c.hook_1], [hookLabel(c, 2, "alternate angle"), c.hook_2],
            [hookLabel(c, 3, "third option"), c.hook_3],
            ["Pain", c.body.pain], ["Promise", c.body.promise], ["Proof", c.body.proof], ["CTA", c.body.cta]].map(([k, t]) => (
            <div key={k}><div className="lab">{k}</div>{t.split("\n").filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}</div>
          ))}
          <div className="lab">Claim ledger</div>
          {c.claims.map((cl, i) => <p key={i} style={{ fontSize: 12.5 }}><code className="mono">{cl.proof_id}</code> {cl.claim}</p>)}
        </div>
      )}
    </>
  );
}

export function ScriptCard({ script, onRetry, focus }: { script: Script; onRetry: (id: number) => void; focus: boolean }) {
  const [open, setOpen] = useState(focus);
  const [full, setFull] = useState<Script | null>(null);
  const [vIdx, setVIdx] = useState<number | null>(null);

  useEffect(() => { if (focus) setOpen(true); }, [focus]);
  useEffect(() => {
    if (open && script.version_count > 1 && !LIVE.includes(script.status)) {
      api.get<Script>(`/api/scripts/${script.id}`).then(setFull).catch(() => undefined);
    }
  }, [open, script.id, script.version_count, script.status]);

  const versions = full?.versions ?? (script.latest ? [script.latest] : []);
  const shown = vIdx !== null && versions[vIdx] ? versions[vIdx] : script.latest;
  const idea = script.idea;

  return (
    <article className="panel script" id={`script-${script.id}`}>
      <div className="head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="t">{shown?.content.title ?? `Script for idea #${idea.id}`}</div>
          <div className="sub">
            Script #{script.id} · idea #{idea.id} “{idea.concept_hook}” · {idea.funnel_stage} · {idea.target_avatar}
          </div>
        </div>
        <StatusPill status={script.status} />
      </div>
      <Steps s={script} />
      {script.error && <div className="banner bad" style={{ margin: "0 16px 12px" }}>{script.error}</div>}
      {shown ? <VersionView v={shown} open={open} /> : (
        <div style={{ padding: "0 16px 14px", color: "var(--muted)" }}>Waiting for the first draft…</div>
      )}
      <div className="footer-row">
        {script.status === "delivered" && script.docx_available && (
          <>
            <a className="btn primary small" href={api.downloadUrl(script.id, "docx")}>⬇ Download .docx</a>
            <a className="btn small" href={api.downloadUrl(script.id, "md")}>.md</a>
          </>
        )}
        {script.status === "held" && <a className="btn small" href={api.downloadUrl(script.id, "md")}>⬇ Hold report</a>}
        {(script.status === "held" || script.status === "failed") && (
          <button className="btn small" onClick={() => onRetry(script.id)}>↻ Retry job</button>
        )}
        {shown && <button className="btn small" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} script & QA detail</button>}
        {versions.length > 1 && (
          <div className="vtabs">
            {versions.map((v, i) => (
              <button key={v.version} className={`btn small ${shown?.version === v.version ? "primary" : ""}`} onClick={() => setVIdx(i)}>
                v{v.version} {v.passed ? "✓" : "✕"}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
