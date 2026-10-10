import type { Summary } from "@/lib/types";

export function PipelineStrip({ summary, running }: { summary: Summary | null; running: boolean }) {
  const s = summary?.scripts;
  const i = summary?.ideas;
  const writing = (s?.writing ?? 0) + (s?.queued ?? 0) + (s?.revising ?? 0);
  const reviewing = s?.reviewing ?? 0;
  const last = summary?.runs?.[0];

  const stages = [
    { n: "01", t: "Ideate", s: "AI call #1 · ideation prompt", c: last ? last.kept : "–", active: running,
      sub: last ? `run #${last.id} · ${last.duplicates_dropped} dupes dropped` : "no runs yet" },
    { n: "02", t: "ICE score", s: "separate scorer prompt", c: (i?.pending ?? 0) + (i?.approved ?? 0) + (i?.rejected ?? 0), active: running,
      sub: "ideas scored total" },
    { n: "03", t: "Human gate", s: "approve / reject", c: i?.pending ?? 0, human: true, sub: "awaiting decision" },
    { n: "04", t: "Trigger", s: "approval → job", c: i?.approved ?? 0, sub: "approved → auto-queued" },
    { n: "05", t: "Script", s: "AI call #2 · scripting prompt", c: writing, active: writing > 0, sub: "writing / revising" },
    { n: "06", t: "Quality gate", s: "code checks + AI reviewer", c: reviewing, active: reviewing > 0, sub: `held: ${s?.held ?? 0}` },
    { n: "07", t: "Delivered", s: ".docx + .md", c: s?.delivered ?? 0, sub: s?.failed ? `${s.failed} job error(s)` : "zero manual steps" },
  ];

  return (
    <div className="pipeline">
      {stages.map((st) => (
        <div key={st.n} className={`stage ${st.human ? "human" : ""} ${st.active ? "active" : ""}`}>
          <div className="n">{st.n}{st.human ? " · HUMAN" : ""}</div>
          <div className="t">{st.t}</div>
          <div className="s">{st.s}</div>
          <div className="c">{st.c}</div>
          <div className="s">{st.sub}</div>
        </div>
      ))}
    </div>
  );
}
