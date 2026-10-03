import { useEffect, useMemo, useRef, useState } from "react";
import { api, ImportPreview, Plan, PreviewChange, ProjectDetail } from "../api";
import { floorNameFor, matchPlan } from "../floors";

interface Row {
  file: File;
  name: string;
  planId?: number; // fixed target floor ("Neue Planversion importieren")
  include: boolean;
  state: "" | "checking" | "ready" | "importing" | "ok" | "error";
  message: string;
  preview?: ImportPreview;
}

type Filter = "all" | "weg" | "geaendert" | "neu";
const FILTERS: [Filter, string][] = [
  ["all", "Alle"],
  ["weg", "Weg"],
  ["geaendert", "Geändert"],
  ["neu", "Neu"],
];

const hasWarning = (p?: ImportPreview) => Boolean(p?.warnings.some((w) => w.level === "warn"));
const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "±0");

/**
 * Import one or more plan files in two steps:
 * 1. files and floor names, 2. what each file changes on its floor, confirmed before anything is stored.
 */
export default function ImportDialog({
  projectId,
  files,
  plans,
  planId,
  onDone,
  onClose,
}: {
  projectId: string;
  files: File[];
  plans: Plan[];
  planId?: number;
  onDone: (result: ProjectDetail | null, summary: { ok: number; failed: number; text: string }) => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Row[]>(() =>
    files.map((file) => ({
      file,
      name: planId ? plans.find((p) => p.id === planId)?.name ?? floorNameFor(file.name) : floorNameFor(file.name),
      planId,
      include: true,
      state: "",
      message: "",
    })),
  );
  const [step, setStep] = useState<"files" | "review">("files");
  const [selected, setSelected] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const tokens = useRef<string[]>([]);
  const started = useRef(false);

  const set = (i: number, patch: Partial<Row>) => setRows((list) => list.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const targetOf = (r: Row) => (r.planId ? plans.find((p) => p.id === r.planId) : matchPlan(r.name.trim() || floorNameFor(r.file.name), plans));

  async function discardAll() {
    const list = tokens.current;
    tokens.current = [];
    await Promise.all(list.map((t) => api.discardPreview(projectId, t).catch(() => undefined)));
  }

  async function check() {
    setBusy(true);
    setStep("review");
    setConfirmed(false);
    await discardAll();
    const current = rows;
    for (const [i, row] of current.entries()) {
      set(i, { state: "checking", message: "", preview: undefined });
      const target = targetOf(row);
      try {
        const p = await api.previewPlan(projectId, target ? "" : row.name.trim() || floorNameFor(row.file.name), row.file, target?.id);
        tokens.current.push(p.token);
        set(i, { state: "ready", preview: p, include: !(p.existing && p.changes.length === 0) });
      } catch (e) {
        set(i, { state: "error", message: (e as Error).message, include: false });
      }
    }
    setBusy(false);
  }

  // a reimport of one floor opens directly on the review
  useEffect(() => {
    if (planId && !started.current) {
      started.current = true;
      check();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId]);

  async function close() {
    if (busy) return;
    await discardAll();
    onClose();
  }

  async function importChosen() {
    setBusy(true);
    let last: ProjectDetail | null = null;
    let ok = 0;
    let failed = 0;
    const lines: string[] = [];
    for (const [i, row] of rows.entries()) {
      if (!row.include || !row.preview || row.state !== "ready") continue;
      set(i, { state: "importing" });
      try {
        last = await api.commitPlan(projectId, row.preview.token);
        tokens.current = tokens.current.filter((t) => t !== row.preview?.token);
        set(i, { state: "ok", message: "übernommen" });
        lines.push(`${row.file.name} → ${row.preview.plan?.name ?? row.preview.floor}`);
        ok += 1;
      } catch (e) {
        set(i, { state: "error", message: (e as Error).message });
        failed += 1;
      }
    }
    setBusy(false);
    onDone(last, { ok, failed, text: lines.join(", ") });
    if (!failed) {
      await discardAll();
      onClose();
    }
  }

  const chosen = rows.filter((r) => r.include && r.state === "ready");
  const needsConfirm = chosen.some((r) => hasWarning(r.preview));
  const sel = rows[selected];

  return (
    <div className="modal-back" onClick={close}>
      <div className="modal ip-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Pläne importieren">
        <header className="ip-head">
          <h3>Pläne importieren</h3>
          <ol className="ip-steps" aria-label="Schritte">
            <li className={step === "files" ? "on" : "done"}>Dateien</li>
            <li className={step === "review" ? "on" : ""}>Änderungen prüfen</li>
          </ol>
        </header>

        {step === "files" ? (
          <>
            <p className="desc">
              Den Geschossnamen schlägt das Programm aus dem Dateinamen vor. Heisst er wie ein vorhandenes Geschoss, wird die Datei dessen neue Planversion.
              Im nächsten Schritt siehst du, was sich ändert. Gespeichert wird erst danach.
            </p>
            <div className="ip-files">
              {rows.map((r, i) => {
                const target = targetOf(r);
                return (
                  <div key={`${r.file.name}-${i}`} className="ip-file-row">
                    <span className="ip-file-name" title={r.file.name}>
                      {r.file.name}
                    </span>
                    <input className="input" value={r.name} aria-label={`Geschoss für ${r.file.name}`} onChange={(e) => set(i, { name: e.target.value })} />
                    <span className={`ip-tag ${target ? "version" : "new"}`}>{target ? `Neue Version von ${target.name}` : "Neues Geschoss"}</span>
                  </div>
                );
              })}
            </div>
            <footer className="ip-foot">
              <span />
              <div className="row">
                <button className="btn" onClick={close}>
                  Abbrechen
                </button>
                <button className="btn primary" onClick={check}>
                  Änderungen prüfen
                </button>
              </div>
            </footer>
          </>
        ) : (
          <>
            <div className="ip-body">
              <nav className="ip-list" aria-label="Dateien">
                {rows.map((r, i) => (
                  <div key={`${r.file.name}-${i}`} className={`ip-item ${i === selected ? "on" : ""}`} onClick={() => setSelected(i)}>
                    <input
                      type="checkbox"
                      checked={r.include}
                      disabled={r.state !== "ready" || busy}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => set(i, { include: e.target.checked })}
                      aria-label={`${r.file.name} übernehmen`}
                    />
                    <div className="ip-item-main">
                      <div className="ip-item-title">
                        {r.preview?.plan?.name ?? r.preview?.floor ?? r.name}
                        {hasWarning(r.preview) && <span className="ip-dot" title="Hinweise prüfen" />}
                      </div>
                      <div className="ip-item-file">{r.file.name}</div>
                      <ItemStatus row={r} />
                    </div>
                  </div>
                ))}
              </nav>
              <section className="ip-detail">{sel && <Detail row={sel} filter={filter} setFilter={setFilter} />}</section>
            </div>
            <footer className="ip-foot">
              {needsConfirm ? (
                <label className="toggle ip-confirm">
                  <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                  Hinweise geprüft, trotzdem übernehmen
                </label>
              ) : (
                <span className="hint">{busy ? "prüft …" : `${chosen.length} von ${rows.length} ausgewählt`}</span>
              )}
              <div className="row">
                {!planId && (
                  <button className="btn" disabled={busy} onClick={() => setStep("files")}>
                    Zurück
                  </button>
                )}
                <button className="btn" disabled={busy} onClick={close}>
                  Abbrechen
                </button>
                <button className="btn primary" disabled={busy || chosen.length === 0 || (needsConfirm && !confirmed)} onClick={importChosen}>
                  {chosen.length === 1 ? "1 Plan übernehmen" : `${chosen.length} Pläne übernehmen`}
                </button>
              </div>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}

function ItemStatus({ row }: { row: Row }) {
  if (row.state === "checking") return <div className="ip-item-sub hint">prüft …</div>;
  if (row.state === "importing") return <div className="ip-item-sub hint">übernimmt …</div>;
  if (row.state === "ok") return <div className="ip-item-sub ok-text">✓ übernommen</div>;
  if (row.state === "error") return <div className="ip-item-sub warn-text">{row.message}</div>;
  const p = row.preview;
  if (!p) return null;
  if (!p.existing) return <div className="ip-item-sub hint">Neu · {p.total_after} Apparate</div>;
  if (!p.changes.length) return <div className="ip-item-sub hint">Keine Änderung</div>;
  return (
    <div className="ip-item-sub ip-chips">
      {p.summary.neu > 0 && <span className="ip-chip neu">+{p.summary.neu}</span>}
      {p.summary.weg > 0 && <span className="ip-chip weg">−{p.summary.weg}</span>}
      {p.summary.geaendert > 0 && <span className="ip-chip mod">~{p.summary.geaendert}</span>}
    </div>
  );
}

function Detail({ row, filter, setFilter }: { row: Row; filter: Filter; setFilter: (f: Filter) => void }) {
  const p = row.preview;
  const shown = useMemo(() => {
    if (!p) return [];
    // a new floor has nothing to compare: its content, largest count first
    if (!p.existing) return [...p.changes].sort((a, b) => b.after - a.after || a.title.localeCompare(b.title));
    return filter === "all" ? p.changes : p.changes.filter((c) => c.kind === filter);
  }, [p, filter]);
  if (row.state === "checking" || (!p && row.state !== "error")) return <div className="ip-empty">prüft {row.file.name} …</div>;
  if (!p) return <div className="ip-empty warn-text">{row.message}</div>;
  const delta = p.total_after - p.total_before;
  const counts: Record<Filter, number> = { all: p.changes.length, weg: p.summary.weg, geaendert: p.summary.geaendert, neu: p.summary.neu };
  return (
    <>
      <div className="ip-detail-head">
        <div>
          <div className="ip-detail-title">{p.plan?.name ?? p.floor}</div>
          <div className="hint">
            {p.existing ? "Neue Planversion" : "Neues Geschoss"} · {p.file_name} · {p.format.toUpperCase()}
          </div>
        </div>
      </div>

      <div className="ip-stats">
        <Stat label="Apparate" value={p.existing ? `${p.total_before} → ${p.total_after}` : String(p.total_after)} delta={p.existing ? delta : undefined} />
        <Stat label="Arten" value={String(p.kinds_after)} />
        <Stat label="Unverändert" value={p.existing ? String(p.unchanged) : "–"} />
        <Stat label="Unbekannt" value={String(p.unknown_after)} />
      </div>

      {p.warnings.length > 0 && (
        <ul className="ip-notes">
          {p.warnings.map((w, i) => (
            <li key={i} className={w.level}>
              <span className="ip-note-icon" aria-hidden>
                {w.level === "warn" ? "!" : "i"}
              </span>
              {w.text}
            </li>
          ))}
        </ul>
      )}

      {p.changes.length > 0 && !p.existing ? (
        <div className="ip-changes">
          {shown.map((c) => (
            <ChangeRow key={c.key} c={c} plain />
          ))}
        </div>
      ) : p.changes.length > 0 ? (
        <>
          <div className="ip-seg" role="tablist" aria-label="Änderungen filtern">
            {FILTERS.map(([id, label]) => (
              <button key={id} role="tab" aria-selected={filter === id} className={filter === id ? "on" : ""} disabled={!counts[id]} onClick={() => setFilter(id)}>
                {label} <span>{counts[id]}</span>
              </button>
            ))}
          </div>
          <div className="ip-changes">
            {shown.map((c) => (
              <ChangeRow key={c.key} c={c} />
            ))}
          </div>
        </>
      ) : (
        <div className="ip-empty">{p.existing ? "Die Datei ändert nichts an diesem Geschoss." : "Keine Apparate gefunden."}</div>
      )}
    </>
  );
}

function Stat({ label, value, delta }: { label: string; value: string; delta?: number }) {
  return (
    <div className="ip-stat">
      <div className="ip-stat-label">{label}</div>
      <div className="ip-stat-value">
        {value}
        {delta !== undefined && delta !== 0 && <span className={`ip-delta ${delta > 0 ? "up" : "down"}`}>{signed(delta)}</span>}
      </div>
    </div>
  );
}

function ChangeRow({ c, plain }: { c: PreviewChange; plain?: boolean }) {
  return (
    <div className={`ip-change ${c.kind}`}>
      <span className="ip-sym" aria-hidden dangerouslySetInnerHTML={{ __html: c.svg }} />
      <div className="ip-change-main">
        <div className="ip-change-title">{c.title}</div>
        <div className="hint">{c.item}</div>
      </div>
      {plain ? (
        <div className="ip-change-num">
          <span className="ip-counts">{c.after}</span>
        </div>
      ) : (
        <div className="ip-change-num">
          {c.kind === "neu" ? <span className="ip-tag new">neu</span> : c.kind === "weg" ? <span className="ip-tag gone">weg</span> : null}
          <span className="ip-counts">
            {c.before} → {c.after}
          </span>
          <span className={`ip-delta ${c.delta > 0 ? "up" : "down"}`}>{signed(c.delta)}</span>
        </div>
      )}
    </div>
  );
}
