import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { CategoryColor, LegendListItem } from "../api";
import { useNavigation } from "../Navigation";
import { useDialogFocus } from "../useDialogFocus";

interface Props {
  projectId: string;
  categories: CategoryColor[];
  active: number | null;
  onSelect: (legendId: number) => void;
  notify: (text: string, error?: boolean) => void;
}

/** The named legends of a project: switch, add, rename and delete. */
export default function LegendTabs({ projectId, categories, active, onSelect, notify }: Props) {
  const { navigate } = useNavigation();
  const [items, setItems] = useState<LegendListItem[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let alive = true;
    api.legends(projectId)
      .then((r) => {
        if (!alive) return;
        setItems(r.items);
        // 0: the project has no legend yet; the editor creates the first one when it saves
        if (!r.items.some((l) => l.id === active)) onSelect(r.items.length ? r.items[0].id : 0);
      })
      .catch((e) => alive && notify((e as Error).message, true));
    return () => {
      alive = false;
    };
    // the list is reloaded when the project changes; the selection only checks it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, notify]);

  const current = items.find((l) => l.id === active) ?? null;

  async function rename() {
    if (!current) return;
    const name = window.prompt("Neuer Name der Legende", current.name)?.trim();
    if (!name || name === current.name) return;
    try {
      setItems((await api.renameLegend(projectId, current.id, name)).items);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function remove() {
    if (!current || items.length < 2) return;
    if (!window.confirm(`Legende «${current.name}» löschen? Das lässt sich nicht rückgängig machen.`)) return;
    // pending edits of the legend go out first, then it is deleted
    await navigate(async () => {
      try {
        const r = await api.deleteLegend(projectId, current.id);
        setItems(r.items);
        onSelect(r.items[0]?.id ?? 0);
        notify(`Legende «${current.name}» gelöscht`);
      } catch (e) {
        notify((e as Error).message, true);
      }
    });
  }

  return (
    <div className="legend-tabs" role="tablist" aria-label="Legenden des Projekts">
      {items.map((l) => (
        <button
          key={l.id}
          role="tab"
          aria-selected={l.id === active}
          className={`legend-tab${l.id === active ? " active" : ""}`}
          title={`${l.entries} Einträge · zuletzt ${l.updated_at ? l.updated_at.slice(0, 16).replace("T", " ") : "nie"}`}
          onClick={() => l.id !== active && navigate(() => onSelect(l.id))}
        >
          {l.name}
        </button>
      ))}
      <button className="btn small" onClick={() => setCreating(true)}>+ Neue Legende</button>
      {current && (
        <span className="legend-tabs-end">
          <button className="btn small" onClick={rename}>Umbenennen</button>
          <button className="btn small" disabled={items.length < 2} onClick={remove}
            title={items.length < 2 ? "Die letzte Legende eines Projekts bleibt bestehen." : "Diese Legende löschen"}>
            Löschen
          </button>
        </span>
      )}
      {creating && (
        <NewLegendDialog
          projectId={projectId}
          categories={categories}
          current={current}
          notify={notify}
          onClose={() => setCreating(false)}
          onDone={(list, id) => {
            setItems(list);
            setCreating(false);
            navigate(() => onSelect(id));
          }}
        />
      )}
    </div>
  );
}

type Source = "proposal" | "categories" | "empty" | "copy";

function NewLegendDialog({ projectId, categories, current, notify, onClose, onDone }: {
  projectId: string;
  categories: CategoryColor[];
  current: LegendListItem | null;
  notify: (text: string, error?: boolean) => void;
  onClose: () => void;
  onDone: (items: LegendListItem[], id: number) => void;
}) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<Source>("categories");
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useDialogFocus(dialogRef, onClose, busy);

  function toggle(id: string) {
    setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
    // a single chosen category names the legend, as long as no name was typed
    if (!name.trim() && !chosen.length) setName(categories.find((c) => c.id === id)?.title ?? "");
  }

  const valid = name.trim() && (source !== "categories" || chosen.length > 0);

  async function submit() {
    if (!valid) return;
    setBusy(true);
    try {
      const r = await api.newLegend(projectId, {
        name: name.trim(),
        source: source === "categories" ? "proposal" : source,
        categories: source === "categories" ? chosen : undefined,
        copy_of: source === "copy" ? current?.id ?? null : null,
      });
      notify(`Legende «${r.legend.name}» angelegt`);
      onDone(r.items, r.legend.id!);
    } catch (e) {
      notify((e as Error).message, true);
      setBusy(false);
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="new-legend-title" tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h3 id="new-legend-title">Neue Legende</h3>
        <p className="desc">Zum Beispiel eine eigene Legende für die Brandmelder. Jede Legende wird im Projekt gespeichert.</p>
        <div className="form-grid">
          <label htmlFor="new-legend-name">Name</label>
          <input id="new-legend-name" className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)}
            placeholder="z. B. Brandmelder" onKeyDown={(e) => e.key === "Enter" && submit()} />
        </div>
        <label className="toggle choice">
          <input type="radio" checked={source === "categories"} onChange={() => setSource("categories")} />
          Vorschlag aus gewählten Kategorien
        </label>
        {source === "categories" && (
          <div className="legend-cat-pick">
            {categories.map((c) => (
              <label key={c.id} className="toggle">
                <input type="checkbox" checked={chosen.includes(c.id)} onChange={() => toggle(c.id)} />
                <span className="swatch" style={{ background: c.color }} /> {c.title}
              </label>
            ))}
            {!categories.length && <p className="desc">Das Projekt hat noch keine Kategorien mit Apparaten.</p>}
          </div>
        )}
        <label className="toggle choice">
          <input type="radio" checked={source === "proposal"} onChange={() => setSource("proposal")} />
          Vorschlag aus allen Kategorien
        </label>
        <label className="toggle choice">
          <input type="radio" checked={source === "copy"} disabled={!current} onChange={() => setSource("copy")} />
          Kopie von «{current?.name ?? "…"}»
        </label>
        <label className="toggle choice">
          <input type="radio" checked={source === "empty"} onChange={() => setSource("empty")} />
          Leer
        </label>
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn" onClick={onClose}>Abbrechen</button>
          <button className="btn primary" disabled={busy || !valid} onClick={submit}>Anlegen</button>
        </div>
      </div>
    </div>
  );
}
