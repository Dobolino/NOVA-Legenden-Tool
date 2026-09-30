import { useEffect, useMemo, useRef, useState } from "react";
import { api, Category, DATASET_LABEL, DatasetInfo, FamilyItem, Options } from "../api";
import FamilyDetail from "./FamilyDetail";
import SymbolPic from "./SymbolPic";

interface Props {
  categories: Category[];
  options: Options;
  revision: number;
  datasets: DatasetInfo[];
  notify: (text: string, error?: boolean) => void;
  onCategoriesChanged: () => void;
  onOpenSettings: () => void;
}

const PAGE = 240;

/** Newest dataset (V2) if present, else the first one, else all. */
function defaultDataset(datasets: DatasetInfo[]): string {
  if (!datasets.length) return "";
  return (datasets.find((d) => d.id.includes(".V2.")) ?? datasets[0]).id;
}
const MOUNTINGS = ["UP", "AP", "NUP", "NAP", "EB", "-"];

export default function Library(props: Props) {
  const { categories, options, revision, datasets, notify } = props;
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  // "" means all datasets. The default (V2, else the first) is set only once.
  const [dataset, setDataset] = useState(() => defaultDataset(datasets));
  const datasetInitialized = useRef(datasets.length > 0);
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const [mounting, setMounting] = useState("");
  const [allVariants, setAllVariants] = useState(false);
  const [tile, setTile] = useState(150);
  const [items, setItems] = useState<FamilyItem[]>([]);
  const [total, setTotal] = useState(0);
  const [shown, setShown] = useState(PAGE);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0); // bumps after a display option changed
  const moreRef = useRef<HTMLDivElement>(null);

  // Datasets can arrive after the first render: apply the default once,
  // later an empty value stays "all datasets".
  useEffect(() => {
    if (!datasetInitialized.current && datasets.length) {
      datasetInitialized.current = true;
      setDataset(defaultDataset(datasets));
    }
  }, [datasets]);

  // Category counts for the chosen dataset, so they match the visible tiles
  useEffect(() => {
    let alive = true;
    api
      .categories(dataset)
      .then((res) => alive && setCounts(Object.fromEntries(res.items.map((c) => [c.id, c.family_count ?? 0]))))
      .catch(() => alive && setCounts(null));
    return () => {
      alive = false;
    };
  }, [dataset, categories, revision, options]);

  const countOf = (cat: Category) => (counts ? (counts[cat.id] ?? 0) : (cat.family_count ?? 0));

  useEffect(() => {
    const handle = window.setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.families({ q, category, dataset, mounting, all_variants: allVariants });
        setItems(res.items);
        setTotal(res.total);
        setShown(PAGE);
      } catch (e) {
        notify((e as Error).message, true);
      } finally {
        setLoading(false);
      }
    }, 180);
    return () => window.clearTimeout(handle);
  }, [q, category, dataset, mounting, allVariants, revision, options, refresh, notify]);

  // Load more tiles when the sentinel scrolls into view
  useEffect(() => {
    const el = moreRef.current;
    if (!el) return;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) setShown((s) => s + PAGE);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [items]);

  const visibleCats = useMemo(() => {
    const top = categories.filter((c) => !c.parent);
    const out: { cat: Category; child: boolean }[] = [];
    for (const c of top) {
      out.push({ cat: c, child: false });
      for (const ch of categories.filter((x) => x.parent === c.id)) out.push({ cat: ch, child: true });
    }
    return out.filter(
      ({ cat }) =>
        !cat.hidden &&
        (options.show_empty_categories || (counts ? (counts[cat.id] ?? 0) : (cat.family_count ?? 0)) > 0),
    );
  }, [categories, options.show_empty_categories, counts]);

  const catTitle = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c.title])), [categories]);

  if (!datasets.length) {
    return (
      <div className="page">
        <div className="page-inner">
          <div className="card">
            <h3>Keine Nova-Datensätze gefunden</h3>
            <p className="desc">
              Das Programm hat die Datei «Elektroinstallationen…nzp» nicht automatisch gefunden. Gib den Pfad in
              den Einstellungen an.
            </p>
            <button className="btn primary" onClick={props.onOpenSettings}>
              Zu den Einstellungen
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <aside className="sidebar">
        <div className="side-title">Kategorien</div>
        <button className={`cat-btn ${category === "" ? "active" : ""}`} onClick={() => setCategory("")}>
          Alle Symbole
        </button>
        {visibleCats.map(({ cat, child }) => (
          <button
            key={cat.id}
            className={`cat-btn ${child ? "child" : ""} ${category === cat.id ? "active" : ""}`}
            onClick={() => setCategory(cat.id)}
          >
            {cat.title}
            <span className="count">{countOf(cat)}</span>
          </button>
        ))}
      </aside>
      <section className="content">
        <div className="toolbar">
          <input
            className="search"
            placeholder="Suche nach Name oder Katalogcode, z. B. «Steckdose T13» oder «230-10»"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            autoFocus
          />
          <select className="select" value={dataset} onChange={(e) => setDataset(e.target.value)} title="Datensatz">
            <option value="">Alle Datensätze</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {DATASET_LABEL(d.id)}
              </option>
            ))}
          </select>
          <select className="select" value={mounting} onChange={(e) => setMounting(e.target.value)} title="Montageart">
            <option value="">Alle Montagearten</option>
            {MOUNTINGS.map((m) => (
              <option key={m} value={m}>
                {m === "-" ? "ohne Angabe" : m}
              </option>
            ))}
          </select>
          <label className="toggle" title="Zeigt jede Variante (UP, AP, ohne Text …) als eigene Kachel">
            <input type="checkbox" checked={allVariants} onChange={(e) => setAllVariants(e.target.checked)} />
            Alle Varianten anzeigen
          </label>
          <input
            type="range"
            min={110}
            max={240}
            value={tile}
            onChange={(e) => setTile(Number(e.target.value))}
            title="Kachelgrösse"
          />
          <span className="result-count">{loading ? "lädt …" : `${total} Einträge`}</span>
        </div>
        <div className="grid-wrap">
          {items.length === 0 && !loading && <div className="empty">Keine Symbole für diese Auswahl.</div>}
          <div className="grid" style={{ ["--tile" as string]: `${tile}px` }}>
            {items.slice(0, shown).map((it) => (
              <div
                key={it.id}
                className={`tile ${selected === it.id ? "selected" : ""}`}
                onClick={() => setSelected(it.id)}
                title={it.representative.name}
              >
                <div className="pic">
                  <SymbolPic sym={it.representative} />
                </div>
                <div className="name">{allVariants ? it.representative.name : it.title}</div>
                <div className="meta">
                  <span>{it.representative.item}</span>
                  {allVariants ? (
                    <span className={`badge ${it.representative.mounting === "UP" ? "up" : ""}`}>
                      {it.representative.mounting ?? "–"}
                    </span>
                  ) : (
                    it.mountings.map((m) => (
                      <span key={m} className={`badge ${m === "UP" ? "up" : ""}`}>
                        {m === "-" ? "–" : m}
                      </span>
                    ))
                  )}
                  {it.representative.kind === "Engine" && it.representative.svg && (
                    <span className="badge" title="Nova zeichnet dieses Symbol aus Parametern. Die Vorschau ist vereinfacht.">
                      vereinfacht
                    </span>
                  )}
                  {it.category_source === "manuell" && <span className="badge manual">zugeordnet</span>}
                  {it.conflicts.length > 0 && <span className="badge warn">prüfen</span>}
                </div>
                {!category && (
                  <div className="meta">{it.categories.map((c) => catTitle[c] ?? c).join(", ")}</div>
                )}
              </div>
            ))}
          </div>
          {shown < items.length && (
            <div className="more" ref={moreRef}>
              weitere laden …
            </div>
          )}
        </div>
      </section>
      {selected && (
        <FamilyDetail
          id={selected}
          categories={categories}
          notify={notify}
          onClose={() => setSelected(null)}
          onFillChanged={() => setRefresh((r) => r + 1)}
          onAssigned={(updated) => {
            setItems((list) =>
              list.map((x) =>
                x.id.split("#")[0] === updated.id
                  ? { ...x, categories: updated.categories, category_source: updated.category_source }
                  : x,
              ),
            );
            props.onCategoriesChanged();
          }}
        />
      )}
    </>
  );
}
