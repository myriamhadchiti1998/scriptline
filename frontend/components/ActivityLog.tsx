import type { EventRow } from "@/lib/types";

const time = (ts: string) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

export function ActivityLog({ events, compact = false }: { events: EventRow[]; compact?: boolean }) {
  if (!events.length) return <div className="empty">No activity yet.</div>;
  return (
    <div className="log">
      {events.map((e) => (
        <div key={e.id} className={`log-row ${e.level}`}>
          <span className="ts">{compact ? time(e.ts).slice(0, 5) : time(e.ts)}</span>
          <span className="kind">{e.kind}{e.ref_id ? ` ${e.ref_id}` : ""}</span>
          <span className="msg">{e.message}</span>
        </div>
      ))}
    </div>
  );
}
