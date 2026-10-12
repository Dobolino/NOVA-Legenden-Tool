import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { CompanySymbolItem } from "../api";

/** All company symbols: how a symbol appears in every legend (text, section, size, turn,
 *  combined symbols). They are saved in the legend editor with «Als Firmensymbol speichern». */
export default function CompanySymbolsCard({ notify }: { notify: (text: string, error?: boolean) => void }) {
  const [items, setItems] = useState<CompanySymbolItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.companySymbols().then((r) => setItems(r.items)).catch((e) => notify((e as Error).message, true));
  }, [notify]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (items ?? []).filter((t) => !q || `${t.text} ${t.title} ${t.category_title}`.toLowerCase().includes(q));
  }, [items, query]);

  async function reset(t: CompanySymbolItem) {
    if (!window.confirm(`Firmensymbol «${t.text || t.title}» zurücksetzen? Grösse, Drehung und Kombination gelten dann nicht mehr. Firmentext und Abschnitt bleiben.`)) return;
    setBusy(true);
    try {
      setItems((await api.resetCompanySymbol(t.family_key)).items);
      notify("Firmensymbol zurückgesetzt");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const fmt = (n: number) => String(n).replace(".", ",");
  return (
    <div className="card">
      <h3>Firmensymbole</h3>
      <p className="desc">
        So erscheint ein Symbol in jeder neuen Legende: Text, Abschnitt, Grösse, Drehung, Spiegeln und kombinierte Symbole. Du speicherst
        ein Firmensymbol im Legendeneditor beim Symbol mit «Als Firmensymbol speichern». Die Farbe kommt weiter aus dem Plan.
        Bestehende Legenden ändern sich erst, wenn du einen neuen Vorschlag machst.
      </p>
      {items && items.length > 0 && (
        <input className="input" style={{ margin: "8px 0", maxWidth: 360 }} placeholder="Suchen" value={query}
          onChange={(e) => setQuery(e.target.value)} aria-label="Firmensymbole suchen" />
      )}
      {items && !items.length && <p className="hint">Noch keine Firmensymbole gespeichert.</p>}
      {shown.length > 0 && (
        <div className="table-scroll" style={{ maxHeight: 420 }}>
          <table className="list-table">
            <thead>
              <tr><th>Text</th><th>Abschnitt</th><th>Grösse</th><th>Drehung</th><th>Kombiniert mit</th><th>Gespeichert</th><th></th></tr>
            </thead>
            <tbody>
              {shown.map((t) => (
                <tr key={t.family_key}>
                  <td className="wrap"><b>{t.text || t.title}</b>{t.text && t.text !== t.title && <div className="hint">{t.title}</div>}</td>
                  <td className="wrap">{t.category_title || <span className="hint">automatisch</span>}</td>
                  <td>{fmt(t.symbol_factor)}</td>
                  <td>{t.rotation ? `${t.rotation}°` : "–"}{t.mirror ? " · gespiegelt" : ""}</td>
                  <td className="wrap">{t.parts.length ? t.parts.map((p) => p.title || p.family_key).join(" / ") : "–"}</td>
                  <td className="hint">{t.by}{t.at ? ` · ${new Date(t.at).toLocaleDateString("de-CH")}` : ""}</td>
                  <td><button className="btn small" disabled={busy} onClick={() => reset(t)}>Zurücksetzen</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
