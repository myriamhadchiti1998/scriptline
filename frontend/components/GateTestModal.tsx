import type { GateTest } from "@/lib/types";

export function GateTestModal({ result, onClose }: { result: GateTest; onClose: () => void }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h2 style={{ flex: 1 }}>Quality-gate red-team</h2>
          <span className={`pill ${result.all_held ? "ok" : "bad"}`}>
            {result.results.filter((r) => r.held).length}/{result.results.length} known-bad scripts held
          </span>
          <button className="btn small" onClick={onClose}>Close</button>
        </div>
        <p style={{ color: "var(--muted)", margin: "4px 0 0", fontSize: 13 }}>
          The Reference Pack’s three losing scripts (§09) were pushed through the real gate — deterministic code checks plus
          the AI reviewer. Items in <b>code caught</b> failed on code alone, before any model opinion.
        </p>
        {result.results.map((r) => (
          <div className="rt" key={r.script}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <b style={{ flex: 1 }}>{r.script}</b>
              <span className={`pill ${r.held ? "ok" : "bad"}`}>{r.held ? "HELD ✓" : "LEAKED ✕"}</span>
            </div>
            <q>{r.text}</q>
            <div style={{ fontSize: 12.5 }}>
              Failed items <span className="mono">{r.failed_items.join(", ")}</span> · code caught{" "}
              <span className="mono">{r.caught_by_code_items.join(", ") || "none"}</span>
            </div>
            <ul>{r.top_reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
        ))}
      </div>
    </div>
  );
}
