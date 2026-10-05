import { useEffect, useState } from "react";
import { api } from "../api";
import type { CompanyGeneral, FamilyItem, GeneralRow } from "../api";

/** Settings: the rows of the general part. The drawing on the server stays the source;
 *  text changes, hidden rows and linked symbols are kept beside it for the whole company. */
export default function GeneralPartEditor({ notify }: { notify: (text: string, error?: boolean) => void }) {
  const [data, setData] = useState<CompanyGeneral | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [linking, setLinking] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<FamilyItem[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.companyGeneral().then(setData).catch((e) => notify((e as Error).message, true));
  }, [notify]);

  useEffect(() => {
    if (!linking || query.trim().length < 2) {
      setFound([]);
      return;
    }
    const h = window.setTimeout(() => {
      api.families({ q: query, category: "", dataset: "", mounting: "", all_variants: false })
        .then((r) => setFound(r.items.slice(0, 8))).catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(h);
  }, [linking, query]);

  if (!data) return null;
  const locked = !data.company.is_admin;

  async function save(row: GeneralRow, change: { text?: string; hidden?: boolean; links?: string[] }, ok?: string) {
    setBusy(true);
    try {
      setData(await api.saveGeneralRow({ key: row.key, ...change }));
      setDrafts((d) => {
        const next = { ...d };
        delete next[row.key];
        return next;
      });
      if (ok) notify(ok);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function reload() {
    setBusy(true);
    try {
      setData(await api.reloadGeneral());
      notify("Allgemeinteil neu vom Server gelesen");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const stamp = data.file_time ? new Date(data.file_time * 1000).toLocaleString("de-CH") : "";
  return (
    <div className="card">
      <h3>Allgemeinteil bearbeiten</h3>
      <p className="desc">
        Die Zeichnung auf dem Server bleibt die Quelle (Einstellungen → Legende der Firma). Hier änderst du Texte, blendest Zeilen
        aus und verknüpfst Zeilen mit Symbolen: Verknüpfte Symbole erscheinen in den Projektabschnitten nicht noch einmal. Neue
        Symbole und die Reihenfolge änderst du in der DWG, dann «Neu laden». Im Legendeneditor ordnet sich der Allgemeinteil
        selbst in 2 oder 3 Spalten.
      </p>
      <div className="row" style={{ gap: 8, alignItems: "center" }}>
        <span className="hint" style={{ flex: 1, wordBreak: "break-all" }}>
          {data.source || "Keine Servervorlage eingestellt."}{stamp ? ` · Datei vom ${stamp}` : ""}
          {data.error ? ` · ${data.error}` : ""}
        </span>
        <button className="btn small" disabled={busy || !data.source} onClick={reload} title="Die Datei auf dem Server jetzt neu lesen">
          Neu laden
        </button>
      </div>
      {!data.rows.length && data.source && !data.error && (
        <p className="hint">Die Zeichnung hat keine klare Textspalte. Sie wird als Ganzes gezeigt und lässt sich hier nicht in Zeilen bearbeiten.</p>
      )}
      {locked && data.rows.length > 0 && <p className="hint">Nur Admins ändern den Allgemeinteil. Du siehst ihn hier zur Kontrolle.</p>}
      {data.rows.length > 0 && (
        <div className="table-scroll" style={{ maxHeight: 520 }}>
          <table className="list-table gp-table">
            <thead>
              <tr><th></th><th>Text</th><th>Zeigen</th><th>Verknüpfte Symbole</th></tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.key} className={r.hidden ? "gp-hidden" : ""}>
                  <td className="gp-icon">
                    {r.svg ? (
                      <svg viewBox={r.vb} preserveAspectRatio="xMidYMid meet" aria-hidden dangerouslySetInnerHTML={{ __html: r.svg }} />
                    ) : r.heading ? <span className="badge">Überschrift</span> : null}
                  </td>
                  <td>
                    <input className="input" disabled={locked} value={drafts[r.key] ?? (r.text || r.original)} aria-label={`Text ${r.original}`}
                      title={r.text ? `In der Zeichnung: ${r.original}` : undefined}
                      onChange={(e) => setDrafts((d) => ({ ...d, [r.key]: e.target.value }))}
                      onBlur={() => {
                        const v = drafts[r.key];
                        if (v === undefined) return;
                        const text = v.trim() === r.original ? "" : v.trim();
                        if (text !== r.text) save(r, { text }, "Text gespeichert");
                      }}
                      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
                    {(r.text || r.by) && (
                      <span className="hint">{r.text ? `Zeichnung: ${r.original}` : ""}{r.by ? ` · geändert von ${r.by}` : ""}</span>
                    )}
                  </td>
                  <td>
                    <input type="checkbox" checked={!r.hidden} disabled={locked || busy} aria-label={`${r.original} zeigen`}
                      onChange={(e) => save(r, { hidden: !e.target.checked })} />
                  </td>
                  <td>
                    <div className="gp-links">
                      {r.links.map((fk) => (
                        <span key={fk} className="chip">
                          {fk}
                          {!locked && (
                            <button className="chip-x" aria-label={`${fk} lösen`} onClick={() => save(r, { links: r.links.filter((x) => x !== fk) })}>×</button>
                          )}
                        </span>
                      ))}
                      {!r.heading && !locked && (linking === r.key ? (
                        <span className="gp-search">
                          <input className="input" autoFocus placeholder="Symbol suchen" value={query} onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === "Escape" && setLinking(null)} />
                          {found.map((f) => (
                            <button key={f.id} className="chip-btn" onClick={() => {
                              save(r, { links: [...r.links, f.key] }, `${f.title} verknüpft`);
                              setLinking(null);
                              setQuery("");
                            }}>{f.title} <span className="hint">{f.representative.item}</span></button>
                          ))}
                        </span>
                      ) : (
                        <button className="btn small" onClick={() => { setLinking(r.key); setQuery(""); }}
                          title="Symbole, die diese Zeile erklärt: sie erscheinen in den Projektabschnitten nicht noch einmal">
                          + Symbol
                        </button>
                      ))}
                      {r.names.length > 0 && <span className="hint" title="Symbole in der Zeichnung (Nova-Namen)">erkannt: {r.names.join(", ")}</span>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
