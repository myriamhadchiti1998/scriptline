"use client";

import { useState } from "react";
import type { Idea, ProofBank } from "@/lib/types";
import { StatusPill } from "./StatusPill";

function Bar({ k, v }: { k: string; v: number }) {
  return (
    <div className="bar" title={`${k} ${v}/10`}>
      <span>{k}</span>
      <i><em style={{ width: `${v * 10}%` }} /></i>
      <span>{v}</span>
    </div>
  );
}

export function IdeaCard({
  idea, proofBank, avatars, onDecide, onOpenScript,
}: {
  idea: Idea;
  proofBank: ProofBank;
  avatars: Record<string, string>;
  onDecide: (id: number, decision: "approved" | "rejected", note?: string) => Promise<void>;
  onOpenScript: () => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const r = idea.ice_reasoning;

  const decide = async (d: "approved" | "rejected") => {
    setBusy(true);
    try { await onDecide(idea.id, d, note || undefined); } finally { setBusy(false); }
  };

  return (
    <article className="panel idea" id={`idea-${idea.id}`}>
      <div className="ice">
        <div className="total">{idea.ice_total.toFixed(1)}</div>
        <div className="lbl">ICE</div>
        <div className="bars">
          <Bar k="I" v={idea.ice_impact} />
          <Bar k="C" v={idea.ice_confidence} />
          <Bar k="E" v={idea.ice_ease} />
        </div>
      </div>
      <div className="body">
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <div className="hook" style={{ flex: 1 }}>{idea.concept_hook}</div>
          <span className="mono" style={{ color: "var(--muted)" }}>#{idea.id}</span>
        </div>
        <div className="chips">
          <span className={`pill ${idea.funnel_stage === "cold" ? "accent" : "violet"}`}>{idea.funnel_stage}</span>
          <span className="pill">{idea.creative_type}</span>
          <span className="pill">{idea.lead_type}</span>
          <span className="pill">{idea.hook_family}</span>
          {r.risk_flags?.length ? <span className="pill warn">⚠ {r.risk_flags.length} risk flag(s)</span> : null}
        </div>
        <dl className="meta">
          <dt>Angle</dt><dd>{idea.angle}</dd>
          <dt>Avatar · pain</dt><dd><b>{avatars[idea.target_avatar] ?? idea.target_avatar}</b> — {idea.pain_addressed}</dd>
          <dt>Proof</dt>
          <dd>
            {idea.proof_point_ids.map((p) => (
              <div className="proof" key={p}><code>{p}</code><span>{proofBank[p]?.text ?? "unknown"}</span></div>
            ))}
          </dd>
        </dl>
        <div className="verdict"><b>Scorer verdict:</b> {r.verdict}</div>
        <details className="why">
          <summary>Why these scores</summary>
          <div className="why-grid">
            <span>Impact <b>{idea.ice_impact}</b></span><span>{r.impact}</span>
            <span>Confidence <b>{idea.ice_confidence}</b></span><span>{r.confidence}</span>
            <span>Ease <b>{idea.ice_ease}</b></span><span>{r.ease}</span>
            {r.risk_flags?.length ? (<><span>Risk flags</span><span style={{ color: "var(--warn)" }}>{r.risk_flags.join(" · ")}</span></>) : null}
            {idea.strategist_note ? (<><span>Strategist</span><span>{idea.strategist_note}</span></>) : null}
          </div>
        </details>

        <div className="actions">
          {idea.status === "pending" ? (
            <>
              <input placeholder="Optional note (fed back into the learning loop)" value={note}
                     onChange={(e) => setNote(e.target.value)} />
              <button className="btn ok" disabled={busy} onClick={() => decide("approved")}>✓ Approve → write script</button>
              <button className="btn ghost-bad" disabled={busy} onClick={() => decide("rejected")}>Reject</button>
            </>
          ) : idea.status === "approved" ? (
            <>
              <span className="pill ok">Approved</span>
              {idea.script && (
                <button className="btn small" onClick={onOpenScript}>
                  Script #{idea.script.id}: <StatusPill status={idea.script.status} />
                </button>
              )}
            </>
          ) : (
            <>
              <span className="pill bad">Rejected</span>
              {idea.decision_note && <span style={{ color: "var(--muted)", fontSize: 12.5 }}>“{idea.decision_note}”</span>}
              <button className="btn small" disabled={busy} onClick={() => decide("approved")}>Approve instead</button>
            </>
          )}
          <span className="memory" title="Idea memory: most similar concept generated before this one">
            {idea.nearest_prior_id
              ? `memory: closest prior #${idea.nearest_prior_id} (${Math.round((idea.nearest_prior_similarity ?? 0) * 100)}% similar)`
              : "memory: no prior concept"}
          </span>
        </div>
      </div>
    </article>
  );
}
