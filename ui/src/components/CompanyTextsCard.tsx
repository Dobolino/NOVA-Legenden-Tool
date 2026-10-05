import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { CompanyText } from "../api";

/** All company legend texts: which symbol, which text, who saved it. Editable, exportable for Excel. */
export default function CompanyTextsCard({ notify }: { notify: (text: string, error?: boolean) => void }) {
  const [items, setItems] = useState<CompanyText[] | null>(null);
  const [file, setFile] = useState("");
  const [query, setQuery] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

  async function load() {
    try {
      const r = await api.descriptions();
      setItems(r.items);
      setFile(r.file);
      setDrafts({});
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter((t) => !q || `${t.text} ${t.title} ${t.family_key}`.toLowerCase().includes(q));
  }, [items, query]);

  async function commit(t: CompanyText) {
    const text = drafts[t.family_key];
    if (text === undefined || text.trim() === t.text) return;
    try {
      await api.setDescription(t.family_key, text.trim() || null);
      notify(text.trim() ? "Firmentext gespeichert" : "Firmentext entfernt. Die Legende nimmt wieder den Namen aus der Schablone.");
      await load();
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function remove(t: CompanyText) {
    if (!window.confirm(`Firmentext «${t.text}» entfernen? Neue Legenden nehmen dann wieder «${t.title || t.family_key}».`)) return;
    try {
      await api.setDescription(t.family_key, null);
      await load();
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function exportCsv() {
    try {
      const blob = await api.legendExportFile(api.descriptionsExportUrl);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "edeco ag-Firmentexte.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function importCsv(f: File) {
    setBusy(true);
    try {
      const r = await api.importDescriptions(f);
      notify(`${r.rows} Zeilen gelesen: ${r.changed} Texte geändert, ${r.removed} entfernt.`);
      await load();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>Firmentexte</h3>
      <p className="desc">
        Ein Firmentext ersetzt in jeder neuen Legende den Namen aus der Schablone. Er gilt für die ganze Symbolfamilie, egal ob das Programm
        den Apparat über den Katalogcode oder den Namen erkennt. Die Datei liegt im Firmenordner, den du oben einträgst, zusammen mit den Kategorien und Zuordnungen.
      </p>
      {file && <p className="hint" style={{ wordBreak: "break-all" }}>Datei: {file}</p>}
      <div className="row" style={{ gap: 8, margin: "8px 0" }}>
        <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Suchen" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Firmentexte suchen" />
        <button className="btn small" onClick={exportCsv} disabled={!items?.length}>Für Excel exportieren (CSV)</button>
        <button className="btn small" onClick={() => importRef.current?.click()} disabled={busy}>Aus CSV übernehmen</button>
        <input ref={importRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) importCsv(f);
        }} />
      </div>
      {items && !items.length && <p className="hint">Noch keine Firmentexte. Im Legenden-Editor einen Eintrag anklicken, Text ändern, «Als Firmentext speichern».</p>}
      {!!shown.length && (
        <div className="table-scroll" style={{ maxHeight: 420 }}>
          <table className="list-table ct-table">
            <thead>
              <tr><th></th><th>Name aus der Schablone</th><th>Firmentext</th><th>Geändert</th><th></th></tr>
            </thead>
            <tbody>
              {shown.map((t) => (
                <tr key={t.family_key}>
                  <td>{t.svg ? <span className="ct-icon" aria-hidden dangerouslySetInnerHTML={{ __html: t.svg }} /> : null}</td>
                  <td title={t.family_key}>{t.title || <span className="hint">nicht in der Bibliothek ({t.family_key})</span>}</td>
                  <td>
                    <input className="input" aria-label={`Firmentext ${t.title || t.family_key}`} value={drafts[t.family_key] ?? t.text}
                      onChange={(e) => setDrafts((d) => ({ ...d, [t.family_key]: e.target.value }))}
                      onBlur={() => commit(t)} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
                  </td>
                  <td className="hint">{t.updated_by ?? ""}{t.updated_at ? ` · ${t.updated_at.slice(0, 10)}` : ""}</td>
                  <td><button className="btn small" title="Firmentext entfernen" aria-label="Firmentext entfernen" onClick={() => remove(t)}>🗑</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="hint">Excel: exportieren, Spalte «Firmentext» ändern, als CSV speichern und mit «Aus CSV übernehmen» einlesen. Ein leerer Text entfernt den Firmentext.</p>
    </div>
  );
}
