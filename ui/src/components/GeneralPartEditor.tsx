import { useEffect, useState } from "react";
import { api } from "../api";
import type { CompanyGeneral, FamilyItem, GeneralRow, SymbolRender } from "../api";

/** Settings: the rows of the general part. The drawing on the server stays the source;
 *  text changes, hidden rows and linked symbols are kept beside it for the whole company. */
export default function GeneralPartEditor({ notify, reloadKey = 0 }: { notify: (text: string, error?: boolean) => void; reloadKey?: number }) {
  const [data, setData] = useState<CompanyGeneral | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [linking, setLinking] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<FamilyItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [addQuery, setAddQuery] = useState("");
  const [addFound, setAddFound] = useState<FamilyItem[]>([]);
  const [addPick, setAddPick] = useState<FamilyItem | null>(null);
  const [addText, setAddText] = useState("");
  const [icons, setIcons] = useState<Record<string, SymbolRender>>({});

  useEffect(() => {
    api.companyGeneral().then(setData).catch((e) => notify((e as Error).message, true));
  }, [notify, reloadKey]);

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

  useEffect(() => {
    if (!adding || addQuery.trim().length < 2) {
      setAddFound([]);
      return;
    }
    const h = window.setTimeout(() => {
      api.families({ q: addQuery, category: "", dataset: "", mounting: "", all_variants: false })
        .then((r) => setAddFound(r.items.slice(0, 8))).catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(h);
  }, [adding, addQuery]);

  // drawings of the rows added from the library (the drawing rows bring their own)
  useEffect(() => {
    const need = (data?.rows ?? []).filter((r) => r.extra && r.symbol_key && !icons[r.symbol_key]);
    if (!need.length) return;
    api.legendSymbols(need.map((r) => ({ symbol_key: r.symbol_key!, family_key: r.family_key || null, length_mm: null, width_mm: null })))
      .then((res) => setIcons((m) => {
        const next = { ...m };
        need.forEach((r, i) => { if (res.items[i]) next[r.symbol_key!] = res.items[i]; });
        return next;
      }))
      .catch(() => undefined);
  }, [data, icons]);

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

  async function download(cols: number, format: "dxf" | "pdf") {
    const name = `edeco ag-Allgemeinteil-${cols}-spaltig.${format}`;
    try {
      const blob = await api.legendExportFile(`/api/company/general/export/${encodeURIComponent(name)}?cols=${cols}&format=${format}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30000);
      notify(`${name} exportiert`);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function run(action: () => Promise<CompanyGeneral>, ok: string) {
    setBusy(true);
    try {
      setData(await action());
      notify(ok);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  function move(index: number, delta: number) {
    const keys = data!.rows.map((r) => r.key);
    const j = index + delta;
    if (j < 0 || j >= keys.length) return;
    [keys[index], keys[j]] = [keys[j], keys[index]];
    run(() => api.orderGeneral(keys), "Reihenfolge gespeichert");
  }

  async function addRow() {
    if (!addPick) return;
    const last = data!.rows[data!.rows.length - 1];
    await run(() => api.addGeneralRow({ text: addText.trim() || addPick.title, symbol_key: addPick.representative.key,
      family_key: addPick.key, after: last?.key ?? "" }), `Zeile «${addText.trim() || addPick.title}» hinzugefügt`);
    setAdding(false);
    setAddPick(null);
    setAddText("");
    setAddQuery("");
  }

  async function downloadTemplate(format: "dxf" | "dwg") {
    const name = `E_Legende Allgemeinteil Vorlage.${format}`;
    try {
      const blob = await api.legendExportFile(`/api/company/general/template/${encodeURIComponent(name)}?format=${format}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30000);
      notify(`${name} exportiert. In Nova oder AutoCAD bearbeiten und als Servervorlage ablegen.`);
    } catch (e) {
      notify((e as Error).message, true);
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
    <div className="general-editor">
      <h4>Zeilen der Legende Allgemein</h4>
      <p className="desc">
        Die Zeichnung oben bleibt die Quelle. Hier änderst du Texte, blendest Zeilen aus und verknüpfst Zeilen mit Symbolen:
        Verknüpfte Symbole erscheinen in den Projektabschnitten nicht noch einmal. Schriftgrösse, Symbolgrösse, Abstand und
        Spalten übernimmt der Allgemeinteil vom Legendeneditor, damit er wie der Rest der Legende aussieht. Mit ↑ ↓ änderst du
        die Reihenfolge, mit «+ Zeile aus Bibliothek» nimmst du ein Nova-Symbol auf. «Als Vorlage» exportiert die Zeichnung mit
        allen Änderungen und dem Hilfsraster: in Nova bearbeiten, auf dem Server ablegen, «Neu laden».
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
      {data.rows.length > 0 && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap", alignItems: "center", margin: "6px 0" }}>
          <span className="hint">Als Vorlage (bearbeitbar, mit Hilfsraster):</span>
          <button className="btn small" disabled={busy} onClick={() => downloadTemplate("dxf")}
            title="Die Servervorlage mit allen Änderungen: Texte, ausgeblendete Zeilen, Reihenfolge, Zeilen aus der Bibliothek">
            Vorlage DXF
          </button>
          <button className="btn small" disabled={busy || !data.oda} onClick={() => downloadTemplate("dwg")}
            title={data.oda ? "Wie DXF, als DWG" : "DWG braucht den ODA File Converter"}>
            Vorlage DWG
          </button>
          <span className="hint">Exportieren, z. B. für ein Nova-Makro:</span>
          {[2, 3].map((cols) => (
            <span key={cols} className="row" style={{ gap: 4 }}>
              <button className="btn small" disabled={busy} onClick={() => download(cols, "dxf")}>{cols} Spalten DXF</button>
              <button className="btn small" disabled={busy} onClick={() => download(cols, "pdf")}>PDF</button>
            </span>
          ))}
        </div>
      )}
      {!data.rows.length && data.source && !data.error && (
        <p className="hint">Die Zeichnung hat keine klare Textspalte. Sie wird als Ganzes gezeigt und lässt sich hier nicht in Zeilen bearbeiten.</p>
      )}
      {locked && data.rows.length > 0 && <p className="hint">Nur Admins ändern den Allgemeinteil. Du siehst ihn hier zur Kontrolle.</p>}
      {data.rows.length > 0 && (
        <div className="table-scroll" style={{ maxHeight: 520 }}>
          <table className="list-table gp-table">
            <thead>
              <tr><th></th><th></th><th>Text</th><th>Zeigen</th><th>Verknüpfte Symbole</th></tr>
            </thead>
            <tbody>
              {data.rows.map((r, index) => (
                <tr key={r.key} className={r.hidden ? "gp-hidden" : ""}>
                  <td className="gp-move">
                    <button className="btn icon small" disabled={locked || busy || index === 0} aria-label={`${r.original} nach oben`}
                      onClick={() => move(index, -1)}>↑</button>
                    <button className="btn icon small" disabled={locked || busy || index === data.rows.length - 1}
                      aria-label={`${r.original} nach unten`} onClick={() => move(index, 1)}>↓</button>
                  </td>
                  <td className="gp-icon">
                    {r.extra ? (
                      icons[r.symbol_key ?? ""]?.svg
                        ? <span className="gp-sym" aria-hidden dangerouslySetInnerHTML={{ __html: icons[r.symbol_key!].svg }} />
                        : <span className="badge">Symbol</span>
                    ) : r.svg ? (
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
                    {r.extra && (
                      <span className="hint">
                        aus der Bibliothek{" "}
                        {!locked && (
                          <button className="btn small" disabled={busy} onClick={() => run(() => api.removeGeneralRow(r.extra_id!), `Zeile «${r.original}» entfernt`)}>
                            Entfernen
                          </button>
                        )}
                      </span>
                    )}
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
      {data.rows.length > 0 && !locked && (
        adding ? (
          <div className="gp-add">
            <input className="input" autoFocus placeholder="Nova-Symbol suchen, z. B. Abzweigdose AP" value={addQuery}
              aria-label="Symbol für die neue Zeile suchen"
              onChange={(e) => { setAddQuery(e.target.value); setAddPick(null); }}
              onKeyDown={(e) => e.key === "Escape" && setAdding(false)} />
            <div className="gp-links">
              {addFound.map((f) => (
                <button key={f.id} className={`chip-btn ${addPick?.id === f.id ? "active" : ""}`}
                  onClick={() => { setAddPick(f); setAddText((t) => t || f.title); }}>
                  {f.title} <span className="hint">{f.representative.item}</span>
                </button>
              ))}
            </div>
            <input className="input" placeholder="Text der Zeile" value={addText} aria-label="Text der neuen Zeile"
              onChange={(e) => setAddText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addRow()} />
            <div className="row" style={{ gap: 6 }}>
              <button className="btn small primary" disabled={busy || !addPick} onClick={addRow}>Zeile hinzufügen</button>
              <button className="btn small" onClick={() => setAdding(false)}>Abbrechen</button>
              <span className="hint">Die Zeile kommt ans Ende, mit ↑ verschiebst du sie. Das Symbol erscheint dann in keiner Projektkategorie mehr.</span>
            </div>
          </div>
        ) : (
          <button className="btn small" style={{ marginTop: 8 }} onClick={() => setAdding(true)}>+ Zeile aus Bibliothek</button>
        )
      )}
    </div>
  );
}
