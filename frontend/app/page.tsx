"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityLog } from "@/components/ActivityLog";
import { GateTestModal } from "@/components/GateTestModal";
import { IdeaCard } from "@/components/IdeaCard";
import { PipelineStrip } from "@/components/PipelineStrip";
import { ScriptCard } from "@/components/ScriptCard";
import { API, api } from "@/lib/api";
import type { EventRow, GateTest, Health, Idea, ProofBank, Script, Summary } from "@/lib/types";

type Tab = "queue" | "ideas" | "scripts" | "activity";
const POLL_MS = 2500;

export default function Dashboard() {
  const [clients, setClients] = useState<{ id: string; name: string }[]>([]);
  const [client, setClient] = useState<string>("");
  const [health, setHealth] = useState<Health | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [proofBank, setProofBank] = useState<ProofBank>({});
  const [avatars, setAvatars] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<Tab>("queue");
  const [batch, setBatch] = useState(12);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [gate, setGate] = useState<GateTest | null>(null);
  const [gateBusy, setGateBusy] = useState(false);
  const [focusScript, setFocusScript] = useState<number | null>(null);
  const [ideaFilter, setIdeaFilter] = useState<"all" | "approved" | "rejected">("all");

  // bootstrap
  useEffect(() => {
    Promise.all([api.get<Health>("/api/health"), api.get<{ id: string; name: string }[]>("/api/clients")])
      .then(([h, c]) => { setHealth(h); setClients(c); setClient((cur) => cur || c[0]?.id || ""); })
      .catch((e) => setError(`Cannot reach the API at ${API} — is the backend running? (${e.message})`));
  }, []);

  useEffect(() => {
    if (!client) return;
    api.get<ProofBank>(`/api/clients/${client}/proof-bank`).then(setProofBank).catch(() => undefined);
    api.get<Record<string, string>>(`/api/clients/${client}/avatars`).then(setAvatars).catch(() => undefined);
  }, [client]);

  const refresh = useCallback(async () => {
    if (!client) return;
    try {
      const [s, i, sc, ev] = await Promise.all([
        api.get<Summary>(`/api/clients/${client}/summary`),
        api.get<Idea[]>(`/api/clients/${client}/ideas`),
        api.get<Script[]>(`/api/clients/${client}/scripts`),
        api.get<EventRow[]>(`/api/clients/${client}/events?limit=150`),
      ]);
      setSummary(s); setIdeas(i); setScripts(sc); setEvents(ev); setError(null);
    } catch (e) {
      setError(`Lost connection to the API (${(e as Error).message}). Retrying…`);
    }
  }, [client]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  const running = summary?.runs?.[0]?.status === "running";
  const pending = useMemo(() => ideas.filter((i) => i.status === "pending"), [ideas]);
  const decided = useMemo(
    () => ideas.filter((i) => i.status !== "pending" && (ideaFilter === "all" || i.status === ideaFilter)),
    [ideas, ideaFilter]);
  const lastRun = summary?.runs?.[0];

  const startRun = async () => {
    setStarting(true);
    try {
      await api.post(`/api/clients/${client}/runs`, { batch_size: batch });
      setTab("queue");
      await refresh();
    } catch (e) { setError((e as Error).message); } finally { setStarting(false); }
  };

  const decide = async (id: number, decision: "approved" | "rejected", note?: string) => {
    try { await api.post(`/api/ideas/${id}/decision`, { decision, note }); await refresh(); }
    catch (e) { setError((e as Error).message); }
  };

  const retry = async (id: number) => {
    try { await api.post(`/api/scripts/${id}/retry`); await refresh(); }
    catch (e) { setError((e as Error).message); }
  };

  const runGate = async () => {
    setGateBusy(true);
    try { setGate(await api.post<GateTest>(`/api/clients/${client}/gate-test`)); await refresh(); }
    catch (e) { setError((e as Error).message); } finally { setGateBusy(false); }
  };

  const openScript = (scriptId: number) => {
    setFocusScript(scriptId); setTab("scripts");
    setTimeout(() => document.getElementById(`script-${scriptId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
  };

  const L = summary?.learning;
  const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${Math.round(v * 100)}%`);

  return (
    <>
      <header className="topbar">
        <div className="brand"><b>Scriptline</b><span>AI ideation &amp; scripting pipeline</span></div>
        <label className="field">Client
          <select value={client} onChange={(e) => setClient(e.target.value)}>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Batch
          <input type="number" min={1} max={30} value={batch} onChange={(e) => setBatch(Number(e.target.value) || 12)} />
        </label>
        <button className="btn primary" onClick={startRun} disabled={!client || starting || running}>
          {running ? "Generating…" : "▶ Generate & score ideas"}
        </button>
        <button className="btn" onClick={runGate} disabled={!client || gateBusy}>
          {gateBusy ? "Red-teaming…" : "Red-team the gate"}
        </button>
        {health && (
          <span className={`pill ${health.provider === "mock" ? "warn" : "ok"}`} title={JSON.stringify(health.models, null, 1)}>
            <span className="dot" />{health.provider === "mock" ? "MOCK model (offline)" : health.models.scripting}
          </span>
        )}
      </header>

      <main className="wrap">
        {error && <div className="banner bad">{error}</div>}
        {health?.provider === "mock" && (
          <div className="banner warn">Running with the offline mock model — outputs are fixtures for testing the plumbing. Set LLM_PROVIDER=anthropic for real runs.</div>
        )}
        {lastRun?.status === "failed" && <div className="banner bad">Run #{lastRun.id} failed: {lastRun.error}</div>}

        <PipelineStrip summary={summary} running={running} />

        <div className="grid">
          <section>
            <nav className="tabs">
              <button className={`tab ${tab === "queue" ? "on" : ""}`} onClick={() => setTab("queue")}>Approval queue<span className="k">{pending.length}</span></button>
              <button className={`tab ${tab === "ideas" ? "on" : ""}`} onClick={() => setTab("ideas")}>Decided ideas<span className="k">{ideas.length - pending.length}</span></button>
              <button className={`tab ${tab === "scripts" ? "on" : ""}`} onClick={() => setTab("scripts")}>Scripts<span className="k">{scripts.length}</span></button>
              <button className={`tab ${tab === "activity" ? "on" : ""}`} onClick={() => setTab("activity")}>Activity log</button>
            </nav>

            {tab === "queue" && (
              pending.length ? pending.map((i) => (
                <IdeaCard key={i.id} idea={i} proofBank={proofBank} avatars={avatars} onDecide={decide}
                          onOpenScript={() => i.script && openScript(i.script.id)} />
              )) : (
                <div className="panel empty">
                  <b>{running ? "Generating and scoring concepts…" : "Nothing waiting for approval"}</b>
                  {running ? "Stage 1 ideation, then Stage 2 ICE scoring. This usually takes 1–3 minutes." : "Click “Generate & score ideas” to start a run."}
                </div>
              )
            )}

            {tab === "ideas" && (
              <>
                <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
                  {(["all", "approved", "rejected"] as const).map((f) => (
                    <button key={f} className={`btn small ${ideaFilter === f ? "primary" : ""}`} onClick={() => setIdeaFilter(f)}>{f}</button>
                  ))}
                </div>
                {decided.length ? decided.map((i) => (
                  <IdeaCard key={i.id} idea={i} proofBank={proofBank} avatars={avatars} onDecide={decide}
                            onOpenScript={() => i.script && openScript(i.script.id)} />
                )) : <div className="panel empty"><b>No decisions yet</b>Approved and rejected ideas appear here.</div>}
              </>
            )}

            {tab === "scripts" && (
              scripts.length ? scripts.map((s) => (
                <ScriptCard key={s.id} script={s} onRetry={retry} focus={focusScript === s.id} />
              )) : <div className="panel empty"><b>No scripts yet</b>Approve an idea — scripting starts automatically.</div>
            )}

            {tab === "activity" && <div className="panel"><ActivityLog events={events} /></div>}
          </section>

          <aside className="side">
            <div className="panel">
              <h3>Learning loop</h3>
              <div className="kv"><span>Ideas in memory (never repeated)</span><b>{L?.ideas_in_memory ?? "–"}</b></div>
              <div className="kv"><span>Human decisions learned from</span><b>{L?.human_decisions ?? "–"}</b></div>
              <div className="kv"><span>Approval rate</span><b>{pct(L?.approval_rate)}</b></div>
              <div className="kv"><span>Delivered exemplars fed to scripting</span><b>{L?.exemplars_available ?? "–"}</b></div>
              <div className="kv"><span>First-draft pass rate</span><b>{pct(L?.first_pass_rate)}</b></div>
            </div>
            <div className="panel">
              <h3>Last run</h3>
              {lastRun ? (
                <>
                  <div className="kv"><span>Run #{lastRun.id} · {lastRun.trigger}</span><b>{lastRun.status}</b></div>
                  <div className="kv"><span>Generated → kept</span><b>{lastRun.generated} → {lastRun.kept}</b></div>
                  <div className="kv"><span>Duplicates dropped (memory)</span><b>{lastRun.duplicates_dropped}</b></div>
                  <div className="kv"><span>Invalid dropped (guards)</span><b>{lastRun.invalid_dropped}</b></div>
                </>
              ) : <div style={{ color: "var(--muted)" }}>No runs yet.</div>}
            </div>
            <div className="panel">
              <h3>Live activity</h3>
              <ActivityLog events={events.slice(0, 14)} compact />
            </div>
          </aside>
        </div>
      </main>

      {gate && <GateTestModal result={gate} onClose={() => setGate(null)} />}
    </>
  );
}
