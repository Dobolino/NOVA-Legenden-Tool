import { useState } from "react";
import { api, Plan, ProjectDetail } from "../api";
import { floorNameFor, matchPlan } from "../floors";

interface Row {
  file: File;
  name: string;
  state: "" | "busy" | "ok" | "error";
  message: string;
}

/** Several plan files at once: one row per file with its floor name, then import all. */
export default function ImportDialog({
  projectId,
  files,
  plans,
  onDone,
  onClose,
}: {
  projectId: string;
  files: File[];
  plans: Plan[];
  onDone: (result: ProjectDetail | null, summary: { ok: number; failed: number; text: string }) => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<Row[]>(() => files.map((file) => ({ file, name: floorNameFor(file.name), state: "", message: "" })));
  const [running, setRunning] = useState(false);

  const set = (i: number, patch: Partial<Row>) => setRows((list) => list.map((r, k) => (k === i ? { ...r, ...patch } : r)));

  async function importAll() {
    setRunning(true);
    let last: ProjectDetail | null = null;
    let known: Plan[] = plans;
    let ok = 0;
    let failed = 0;
    const lines: string[] = [];
    for (const [i, row] of rows.entries()) {
      if (row.state === "ok") continue;
      const name = row.name.trim() || floorNameFor(row.file.name);
      const target = matchPlan(name, known);
      set(i, { state: "busy", message: target ? `neue Planversion von ${target.name}` : "neues Geschoss" });
      try {
        last = await api.importPlan(projectId, target ? "" : name, row.file, target?.id);
        known = last.plans;
        const plan = target ? last.plans.find((p) => p.id === target.id) : matchPlan(name, last.plans) ?? last.plans[last.plans.length - 1];
        const count = plan ? last.rows.reduce((n, r) => n + (r.counts[plan.id] ?? 0), 0) : 0;
        set(i, { state: "ok", message: `${plan?.name ?? name}: ${count} Apparate${target ? ", neue Planversion" : ""}` });
        lines.push(`${row.file.name} → ${plan?.name ?? name}`);
        ok += 1;
      } catch (e) {
        set(i, { state: "error", message: (e as Error).message });
        failed += 1;
      }
    }
    setRunning(false);
    onDone(last, { ok, failed, text: lines.join(", ") });
    if (!failed) onClose();
  }

  return (
    <div className="modal-back" onClick={() => !running && onClose()}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Pläne importieren">
        <h3>Pläne importieren</h3>
        <p className="desc">
          Eine Zeile pro Datei. Den Geschossnamen schlägt das Programm aus dem Dateinamen vor. Heisst er wie ein vorhandenes Geschoss, wird die Datei dessen
          neue Planversion; die Liste dieses Geschosses bleibt erhalten.
        </p>
        <table className="list-table">
          <thead>
            <tr>
              <th>Datei</th>
              <th>Geschoss</th>
              <th>Ergebnis</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const target = matchPlan(r.name, plans);
              return (
                <tr key={`${r.file.name}-${i}`}>
                  <td style={{ wordBreak: "break-all" }}>{r.file.name}</td>
                  <td>
                    <input
                      className="input"
                      value={r.name}
                      disabled={running || r.state === "ok"}
                      aria-label={`Geschoss für ${r.file.name}`}
                      onChange={(e) => set(i, { name: e.target.value })}
                    />
                  </td>
                  <td className={r.state === "error" ? "warn-text" : "hint"}>
                    {r.state === "busy" && "importiert … "}
                    {r.state === "ok" && "✓ "}
                    {r.state === "error" && "Fehler: "}
                    {r.message || (target ? `neue Planversion von ${target.name}` : "neues Geschoss")}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
          <button className="btn" disabled={running} onClick={onClose}>
            {rows.some((r) => r.state === "ok") ? "Schliessen" : "Abbrechen"}
          </button>
          <button className="btn primary" disabled={running || rows.every((r) => r.state === "ok")} onClick={importAll}>
            {running ? "importiert …" : `Alle importieren (${rows.filter((r) => r.state !== "ok").length})`}
          </button>
        </div>
      </div>
    </div>
  );
}
