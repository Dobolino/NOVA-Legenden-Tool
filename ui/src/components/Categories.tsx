import { useEffect, useState } from "react";
import { api, Category, Options } from "../api";
import { parseSheets } from "../sheets";

interface Props {
  categories: Category[];
  options: Options;
  notify: (text: string, error?: boolean) => void;
  onChanged: () => void;
}

const OPTION_TEXT: { key: keyof Options; title: string; desc: string }[] = [
  {
    key: "merge_labels",
    title: "Beschriftungsvarianten zusammenfassen",
    desc: "«(Ohne Text)», «(Text horizontal)» usw. erscheinen unter dem UP-Vertreter.",
  },
  {
    key: "merge_orientation",
    title: "Ausrichtungen zusammenfassen",
    desc: "«liegend», «stehend», «rechts» gelten als eine Funktion.",
  },
  {
    key: "show_empty_categories",
    title: "Leere Kategorien anzeigen",
    desc: "Kategorien ohne Symbole erscheinen trotzdem in der Liste.",
  },
  {
    key: "legend_by_category",
    title: "Legende nach Kategorien gliedern",
    desc: "Die Legende zeigt Abschnitte mit Überschriften (wirkt ab Phase 4).",
  },
];

export default function Categories({ categories, options, notify, onChanged }: Props) {
  const [rows, setRows] = useState<Category[]>(categories);
  // Raw text of the number range fields while typing (saved on blur)
  const [sheetsDraft, setSheetsDraft] = useState<Record<string, string>>({});
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newParent, setNewParent] = useState("");

  useEffect(() => setRows(categories), [categories]);

  const tops = rows.filter((c) => !c.parent);

  async function run(action: () => Promise<unknown>, ok: string) {
    try {
      await action();
      notify(ok);
      onChanged();
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  function edit(id: string, field: keyof Category, value: unknown) {
    setRows((list) => list.map((c) => (c.id === id ? { ...c, [field]: value } : c)));
  }

  function commit(id: string, field: keyof Category) {
    const row = rows.find((c) => c.id === id);
    const orig = categories.find((c) => c.id === id);
    if (!row || !orig || JSON.stringify(row[field]) === JSON.stringify(orig[field])) return;
    if (field === "title" && !String(row.title).trim()) {
      notify("Titel darf nicht leer sein", true);
      setRows(categories);
      return;
    }
    run(() => api.updateCategory(id, { [field]: row[field] }), "Gespeichert");
  }

  function saveSheets(id: string) {
    const text = sheetsDraft[id];
    if (text === undefined) return;
    setSheetsDraft((d) => {
      const next = { ...d };
      delete next[id];
      return next;
    });
    const sheets = parseSheets(text);
    const orig = categories.find((c) => c.id === id);
    if (!orig || JSON.stringify(sheets) === JSON.stringify(orig.sheets)) return;
    edit(id, "sheets", sheets);
    run(() => api.updateCategory(id, { sheets }), "Gespeichert");
  }

  function drop(targetId: string) {
    if (!dragId || dragId === targetId) return;
    const ids = rows.map((c) => c.id).filter((x) => x !== dragId);
    ids.splice(ids.indexOf(targetId), 0, dragId);
    setDragId(null);
    setOverId(null);
    run(() => api.reorder(ids), "Reihenfolge gespeichert");
  }

  function move(id: string, delta: number) {
    const ids = rows.map((c) => c.id);
    const i = ids.indexOf(id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    run(() => api.reorder(ids), "Reihenfolge gespeichert");
  }

  return (
    <div className="page">
      <div className="page-inner wide">
        <div className="card">
          <h3>Kategorien der Firma</h3>
          <p className="desc">
            Diese Kategorien gelten für alle im Firmenordner. Ziehe eine Zeile am Griff ⠿, um die Reihenfolge zu
            ändern. Änderungen speichern sofort. Nummernkreise ordnen Symbole automatisch zu (z. B. 230, 240 für
            Brandmeldeanlage).
          </p>
          <table className="cat-table">
            <colgroup>
              <col style={{ width: 28 }} />
              <col style={{ width: "24%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: 70 }} />
              <col style={{ width: 80 }} />
              <col style={{ width: "15%" }} />
              <col style={{ width: 60 }} />
              <col style={{ width: 250 }} />
            </colgroup>
            <thead>
              <tr>
                <th />
                <th>Titel</th>
                <th>Unter</th>
                <th>Ebene</th>
                <th>Spalten</th>
                <th>Abstand mm</th>
                <th>Nummernkreise</th>
                <th>Symbole</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.id}
                  className={`${dragId === c.id ? "dragging" : ""} ${overId === c.id ? "drop-target" : ""} ${
                    c.hidden ? "hidden-cat" : ""
                  }`}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setOverId(c.id);
                  }}
                  onDragLeave={() => setOverId(null)}
                  onDrop={() => drop(c.id)}
                >
                  <td>
                    <span
                      className="handle"
                      draggable
                      onDragStart={() => setDragId(c.id)}
                      onDragEnd={() => {
                        setDragId(null);
                        setOverId(null);
                      }}
                      title="Ziehen zum Verschieben"
                    >
                      ⠿
                    </span>
                  </td>
                  <td style={{ paddingLeft: c.parent ? 22 : 6 }}>
                    <input
                      className="input"
                      value={c.title}
                      onChange={(e) => edit(c.id, "title", e.target.value)}
                      onBlur={() => commit(c.id, "title")}
                    />
                  </td>
                  <td>
                    <select
                      className="select"
                      value={c.parent ?? ""}
                      onChange={(e) => {
                        const parent = e.target.value || null;
                        run(() => api.updateCategory(c.id, { parent }), "Gespeichert");
                      }}
                    >
                      <option value="">–</option>
                      {tops
                        .filter((t) => t.id !== c.id)
                        .map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.title}
                          </option>
                        ))}
                    </select>
                  </td>
                  <td>
                    <input
                      className="input"
                      value={c.layer ?? ""}
                      onChange={(e) => edit(c.id, "layer", e.target.value)}
                      onBlur={() => commit(c.id, "layer")}
                    />
                  </td>
                  <td>
                    <input
                      className="input num"
                      type="number"
                      min={1}
                      max={6}
                      value={c.columns}
                      onChange={(e) => edit(c.id, "columns", Number(e.target.value))}
                      onBlur={() => commit(c.id, "columns")}
                    />
                  </td>
                  <td>
                    <input
                      className="input num"
                      type="number"
                      step={0.05}
                      min={1}
                      value={c.spacing}
                      onChange={(e) => edit(c.id, "spacing", Number(e.target.value))}
                      onBlur={() => commit(c.id, "spacing")}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      value={sheetsDraft[c.id] ?? c.sheets.join(", ")}
                      onChange={(e) => setSheetsDraft((d) => ({ ...d, [c.id]: e.target.value }))}
                      onBlur={() => saveSheets(c.id)}
                    />
                  </td>
                  <td className="hint">{c.family_count ?? ""}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="btn small" onClick={() => move(c.id, -1)} title="nach oben">
                      ↑
                    </button>{" "}
                    <button className="btn small" onClick={() => move(c.id, 1)} title="nach unten">
                      ↓
                    </button>{" "}
                    <button
                      className="btn small"
                      onClick={() =>
                        run(
                          () => api.updateCategory(c.id, { hidden: !c.hidden }),
                          c.hidden ? "Eingeblendet" : "Ausgeblendet",
                        )
                      }
                    >
                      {c.hidden ? "Einblenden" : "Ausblenden"}
                    </button>{" "}
                    <button
                      className="btn small danger"
                      onClick={() => {
                        if (window.confirm(`Kategorie «${c.title}» löschen? Das gilt für die ganze Firma.`))
                          run(() => api.deleteCategory(c.id), "Gelöscht");
                      }}
                    >
                      Löschen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ marginTop: 12 }}>
            <input
              className="input"
              placeholder="Neue Kategorie"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
            />
            <select className="select" value={newParent} onChange={(e) => setNewParent(e.target.value)}>
              <option value="">als Hauptkategorie</option>
              {tops.map((t) => (
                <option key={t.id} value={t.id}>
                  unter «{t.title}»
                </option>
              ))}
            </select>
            <button
              className="btn primary"
              disabled={!newTitle.trim()}
              onClick={() =>
                run(async () => {
                  await api.createCategory(newTitle.trim(), newParent || null);
                  setNewTitle("");
                }, "Kategorie angelegt")
              }
            >
              Anlegen
            </button>
            <div style={{ flex: 1 }} />
            <button
              className="btn danger"
              onClick={() => {
                if (
                  window.confirm(
                    "Alle Kategorien und manuellen Zuordnungen auf den Standard zurücksetzen? Das gilt für die ganze Firma.",
                  )
                )
                  run(() => api.resetCategories(), "Standard wiederhergestellt");
              }}
            >
              Standard wiederherstellen
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Regeln für Symbolfamilien</h3>
          <p className="desc">Gelten für die ganze Firma.</p>
          {OPTION_TEXT.map((o) => (
            <label key={o.key} className="toggle" style={{ display: "flex", alignItems: "flex-start", margin: "8px 0" }}>
              <input
                type="checkbox"
                checked={Boolean(options[o.key])}
                onChange={(e) => run(() => api.saveOptions({ [o.key]: e.target.checked }), "Gespeichert")}
              />
              <span>
                <b style={{ color: "var(--fg)" }}>{o.title}</b>
                <br />
                {o.desc}
              </span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
