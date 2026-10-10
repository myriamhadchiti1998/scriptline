import type { ScriptStatus } from "@/lib/types";

const MAP: Record<ScriptStatus, { cls: string; label: string; live?: boolean }> = {
  queued: { cls: "accent", label: "queued", live: true },
  writing: { cls: "accent", label: "writing", live: true },
  reviewing: { cls: "violet", label: "in review", live: true },
  revising: { cls: "warn", label: "revising", live: true },
  delivered: { cls: "ok", label: "delivered" },
  held: { cls: "bad", label: "held" },
  failed: { cls: "bad", label: "job error" },
};

export function StatusPill({ status }: { status: ScriptStatus }) {
  const m = MAP[status];
  return (
    <span className={`pill ${m.cls} ${m.live ? "pulse" : ""}`}>
      <span className="dot" />
      {m.label}
    </span>
  );
}
