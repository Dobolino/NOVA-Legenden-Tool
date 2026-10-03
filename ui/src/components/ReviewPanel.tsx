import { Review, ReviewCheck } from "../api";

type Target = ReviewCheck["target"];

const ICON: Record<ReviewCheck["level"], string> = { block: "✕", warn: "!", ok: "✓" };

/** Release check: everything open before the legend is handed on, with a jump to the fix. */
export default function ReviewPanel({
  review,
  loading,
  onRefresh,
  onOpen,
}: {
  review: Review | null;
  loading: boolean;
  onRefresh: () => void;
  onOpen: (target: Target) => void;
}) {
  if (!review) return <div className="hint">{loading ? "prüft …" : "Noch nicht geprüft."}</div>;
  const open = review.checks.filter((c) => c.level !== "ok");
  const done = review.checks.filter((c) => c.level === "ok");
  return (
    <div className="rv">
      <div className={`rv-head ${review.ready ? "ready" : "open"}`}>
        <span className="rv-badge" aria-hidden>
          {review.ready ? "✓" : review.blocks}
        </span>
        <div className="rv-head-text">
          <div className="rv-head-title">
            {review.ready ? "Bereit zur Weitergabe" : review.blocks === 1 ? "1 Punkt muss behoben werden" : `${review.blocks} Punkte müssen behoben werden`}
          </div>
          <div className="hint">
            {review.warns ? `${review.warns} ${review.warns === 1 ? "Punkt" : "Punkte"} zum Prüfen · ` : ""}
            {done.length} erledigt
          </div>
        </div>
        <button className="btn small" disabled={loading} onClick={onRefresh}>
          {loading ? "prüft …" : "Neu prüfen"}
        </button>
      </div>

      {open.length > 0 && (
        <div className="rv-list">
          {open.map((c) => (
            <CheckRow key={c.id} c={c} onOpen={onOpen} />
          ))}
        </div>
      )}

      {done.length > 0 && (
        <details className="rv-done">
          <summary>Erledigt ({done.length})</summary>
          <div className="rv-list">
            {done.map((c) => (
              <CheckRow key={c.id} c={c} onOpen={onOpen} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function CheckRow({ c, onOpen }: { c: ReviewCheck; onOpen: (t: Target) => void }) {
  return (
    <div className={`rv-row ${c.level}`}>
      <span className="rv-icon" aria-label={c.level === "block" ? "muss behoben werden" : c.level === "warn" ? "prüfen" : "erledigt"}>
        {ICON[c.level]}
      </span>
      <div className="rv-main">
        <div className="rv-title">
          {c.title}
          {c.level !== "ok" && c.count > 0 && <span className="rv-count">{c.count}</span>}
        </div>
        <div className="hint">{c.detail}</div>
        {c.items.length > 0 && c.level !== "ok" && (
          <details className="rv-items">
            <summary>{c.count > c.items.length ? `Erste ${c.items.length} von ${c.count} zeigen` : "Einträge zeigen"}</summary>
            <ul>
              {c.items.map((it, i) => (
                <li key={i}>
                  <span>{it.title}</span>
                  <span className="hint">{it.detail}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
      {c.level !== "ok" && (
        <button className="btn small" onClick={() => onOpen(c.target)}>
          Öffnen
        </button>
      )}
    </div>
  );
}
