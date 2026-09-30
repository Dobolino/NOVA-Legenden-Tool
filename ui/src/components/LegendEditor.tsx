import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Category, FamilyItem, GeneralInfo, LegendInfo, LegendLayout, LegendPrim, ProjectDetail, SymbolRender } from "../api";
import {
  addBlock,
  addItem,
  beginSave,
  blockForCategory,
  commit,
  describe,
  History,
  historyOf,
  isCurrentSave,
  LegendBlock,
  LegendDoc,
  LegendItem,
  LineStyle,
  missingRows,
  moveBlockInOrder,
  moveItemInOrder,
  moveItemToBlock,
  push,
  redo,
  removeBlock,
  removeItem,
  replace,
  SectionStyle,
  Selection,
  staleItems,
  symbolRequestKey,
  undo,
  updateBlock,
  updateItem,
  updateSectionStyle,
} from "../legend";
import { TrashIcon } from "./Icons";

interface Props {
  projectId: string;
  data: ProjectDetail;
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
}

type SaveState = "idle" | "saving" | "saved" | "error";

const DASH: Record<LineStyle, string> = { solid: "", dashed: "2 1.2", dotted: "0.2 1", dashdot: "2 0.8 0.2 0.8" };
const LINE_LABEL: Record<LineStyle, string> = { solid: "durchgezogen", dashed: "gestrichelt", dotted: "punktiert", dashdot: "Strich-Punkt" };
const FREE_TEXT_HINT = "Freier Text ist ein Zusatztext in der Legende, kein Apparat. Er sitzt im Raster wie ein Eintrag und nutzt die gemeinsame Schriftgrösse.";

function tint(color: string, share: number): string {
  if (!/^#[0-9a-f]{6}$/i.test(color)) return color;
  return `#${[1, 3, 5]
    .map((i) => parseInt(color.slice(i, i + 2), 16))
    .map((c) => Math.round(c + (255 - c) * share).toString(16).padStart(2, "0"))
    .join("")}`;
}

export default function LegendEditor({ projectId, data, categories, notify }: Props) {
  const [hist, setHist] = useState<History<LegendDoc> | null>(null);
  const [info, setInfo] = useState<LegendInfo | null>(null);
  const [placed, setPlaced] = useState<LegendLayout | null>(null);
  const [general, setGeneral] = useState<(GeneralInfo & { svg: string; prims: LegendPrim[] }) | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [savedInfo, setSavedInfo] = useState("");
  const [sel, setSel] = useState<Selection | { type: "general" }>(null);
  const [zoom, setZoom] = useState(4);
  const [symbols, setSymbols] = useState<Record<string, SymbolRender>>({});
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<FamilyItem[]>([]);
  const [exportBlock, setExportBlock] = useState("");
  const [exportGeneral, setExportGeneral] = useState(true);
  const lastSaved = useRef<LegendDoc | null>(null);
  const saveGate = useRef({ generation: 0 });
  const saveAbort = useRef<AbortController | null>(null);
  const layoutGate = useRef({ generation: 0 });
  const fieldBefore = useRef<LegendDoc | null>(null);

  const doc = hist?.present ?? null;
  const colorByCat = useMemo(() => Object.fromEntries(data.category_colors.map((c) => [c.id, c.color])), [data.category_colors]);
  const layerByCat = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c.layer ?? ""])), [categories]);
  const catTitle = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c.title])), [categories]);
  const descriptions = info?.descriptions ?? {};

  // -- load, general part, save ------------------------------------------------------------

  useEffect(() => {
    let alive = true;
    setInfo(null);
    api
      .legend(projectId)
      .then((r) => {
        if (!alive) return;
        setInfo(r);
        if (r.legend) {
          lastSaved.current = r.legend.doc;
          setHist(historyOf(r.legend.doc));
          setSavedInfo(`${formatStamp(r.legend.updated_at)} von ${r.legend.updated_by}`);
        } else setHist(null);
      })
      .catch((e) => notify((e as Error).message, true));
    api
      .legendGeneral(projectId)
      .then((g) => alive && setGeneral(g))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [projectId, notify]);

  useEffect(() => {
    if (!doc || doc === lastSaved.current) return;
    setSaveState("saving");
    const handle = window.setTimeout(async () => {
      saveAbort.current?.abort();
      const ctrl = new AbortController();
      saveAbort.current = ctrl;
      const generation = beginSave(saveGate.current);
      try {
        const r = await api.saveLegend(projectId, doc, ctrl.signal);
        if (!isCurrentSave(saveGate.current, generation)) return; // a newer save is on its way
        lastSaved.current = doc;
        setSaveState("saved");
        setSavedInfo(`${formatStamp(r.legend.updated_at)} von ${r.legend.updated_by}`);
      } catch (e) {
        if ((e as Error).name === "AbortError" || !isCurrentSave(saveGate.current, generation)) return;
        setSaveState("error");
        notify(`Legende nicht gespeichert: ${(e as Error).message}`, true);
      }
    }, 700);
    return () => window.clearTimeout(handle);
  }, [doc, projectId, notify]);

  // layout from the backend (same code as the DXF export)
  useEffect(() => {
    if (!doc) return;
    const ctrl = new AbortController();
    const handle = window.setTimeout(() => {
      const generation = beginSave(layoutGate.current);
      api
        .layoutLegend(projectId, doc, ctrl.signal)
        .then((r) => isCurrentSave(layoutGate.current, generation) && setPlaced(r))
        .catch(() => undefined);
    }, 120);
    return () => {
      window.clearTimeout(handle);
      ctrl.abort();
    };
  }, [doc, projectId]);

  // symbol drawings for the placed symbols (and those of a general part from a template project)
  useEffect(() => {
    const prims = [...(placed?.prims ?? []), ...(general?.prims ?? [])].filter((p) => p.t === "symbol");
    const need = new Map<string, LegendPrim>();
    for (const p of prims) {
      const key = symbolRequestKey({ symbol_key: p.key, length_mm: p.length_mm, width_mm: p.width_mm });
      if (!symbols[key]) need.set(key, p);
    }
    if (!need.size) return;
    const list = [...need.entries()];
    api
      .legendSymbols(list.map(([, p]) => ({ symbol_key: p.key, family_key: p.family_key, length_mm: p.length_mm, width_mm: p.width_mm })))
      .then((r) =>
        setSymbols((prev) => {
          const next = { ...prev };
          list.forEach(([key], i) => (next[key] = r.items[i]));
          return next;
        }),
      )
      .catch(() => undefined);
  }, [placed, general, symbols]);

  useEffect(() => {
    if (search.trim().length < 2) {
      setResults([]);
      return;
    }
    const h = window.setTimeout(() => {
      api
        .families({ q: search, category: "", dataset: "", mounting: "", all_variants: false })
        .then((r) => setResults(r.items.slice(0, 10)))
        .catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(h);
  }, [search]);

  // -- editing helpers ---------------------------------------------------------------------

  const change = useCallback((next: LegendDoc) => setHist((h) => (h ? push(h, next) : historyOf(next))), []);

  /** Text fields: live change while typing, one undo step per field visit. */
  function field(apply: (d: LegendDoc, value: string) => LegendDoc) {
    return {
      onFocus: () => (fieldBefore.current = doc),
      onChange: (e: { target: { value: string } }) => setHist((h) => (h ? replace(h, apply(h.present, e.target.value)) : h)),
      onBlur: () =>
        setHist((h) => {
          const before = fieldBefore.current;
          fieldBefore.current = null;
          return h && before ? commit(h, before) : h;
        }),
    };
  }

  async function proposal() {
    if (doc && !window.confirm("Neuen Vorschlag aus dem Projekt erstellen? Die jetzige Legende wird ersetzt (Rückgängig bleibt möglich).")) return;
    setBusy(true);
    try {
      const r = await api.proposeLegend(projectId, doc?.style ?? info?.style);
      change(r.doc);
      setSel(null);
      notify("Vorschlag erstellt");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  function ensureBlock(d: LegendDoc, categoriesOfEntry: string[], fallback: string | null): { doc: LegendDoc; id: string } {
    const found = blockForCategory(d, categoriesOfEntry, null);
    if (found) return { doc: d, id: found };
    const cat = categoriesOfEntry.find((c) => catTitle[c]);
    if (cat) return addBlock(d, catTitle[cat], cat, colorByCat[cat], layerByCat[cat] ?? "");
    if (fallback && d.blocks.some((b) => b.id === fallback)) return { doc: d, id: fallback };
    if (d.blocks[0]) return { doc: d, id: d.blocks[0].id };
    return addBlock(d, "Legende");
  }

  function selectedBlockId(): string | null {
    return sel && "block" in sel ? sel.block : null;
  }

  function addRows(rows: typeof data.rows) {
    if (!doc) return;
    let d = doc;
    let last: { block: string; item: string } | null = null;
    for (const r of rows) {
      const target = ensureBlock(d, r.categories, selectedBlockId());
      const res = addItem(target.doc, target.id, { kind: "symbol", family_key: r.family_key, symbol_key: r.symbol_key, text: describe(r.family_key, r.title, descriptions) });
      d = res.doc;
      last = { block: target.id, item: res.id };
    }
    change(d);
    if (last && rows.length === 1) setSel({ type: "item", block: last.block, item: last.item });
  }

  function addFromLibrary(f: FamilyItem) {
    if (!doc) return;
    const familyKey = f.id.split("#")[0];
    const target = ensureBlock(doc, f.categories, selectedBlockId());
    const res = addItem(target.doc, target.id, { kind: "symbol", family_key: familyKey, symbol_key: f.representative.key, text: describe(familyKey, f.title, descriptions) });
    change(res.doc);
    setSel({ type: "item", block: target.id, item: res.id });
    setSearch("");
  }

  function addKind(kind: "line" | "note" | "text") {
    if (!doc) return;
    let d = doc;
    let blockId = selectedBlockId();
    if (!blockId || !d.blocks.some((b) => b.id === blockId)) {
      if (kind === "text") {
        const nb = addBlock(d, "Zusatztext");
        d = nb.doc;
        blockId = nb.id;
      } else {
        const t = ensureBlock(d, [], null);
        d = t.doc;
        blockId = t.id;
      }
    }
    const text = kind === "line" ? "UP-Wandleitung" : kind === "note" ? "Hinweis" : "Zusatztext";
    const res = addItem(d, blockId, { kind, text });
    change(res.doc);
    setSel({ type: "item", block: blockId, item: res.id });
  }

  function removeSelected() {
    if (!doc || !sel) return;
    if (sel.type === "item") change(removeItem(doc, sel.block, sel.item));
    else if (sel.type === "block") {
      const b = doc.blocks.find((x) => x.id === sel.block);
      if (b && b.items.length && !window.confirm(`Abschnitt «${b.title}» mit ${b.items.length} Einträgen entfernen?`)) return;
      change(removeBlock(doc, sel.block));
    } else return;
    setSel(null);
  }

  function moveSelected(delta: number) {
    if (!doc || !sel) return;
    if (sel.type === "item") {
      const r = moveItemInOrder(doc, sel.block, sel.item, delta);
      change(r.doc);
      setSel({ type: "item", block: r.block, item: sel.item });
    } else if (sel.type === "block") change(moveBlockInOrder(doc, sel.block, delta));
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        setHist((h) => (h ? undo(h) : h));
      } else if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        setHist((h) => (h ? redo(h) : h));
      } else if (e.key === "Delete" && sel && sel.type !== "general") {
        e.preventDefault();
        removeSelected();
      } else if ((e.key === "ArrowUp" || e.key === "ArrowDown") && sel && sel.type !== "general") {
        e.preventDefault();
        moveSelected(e.key === "ArrowUp" ? -1 : 1);
      } else if (e.key === "Escape") setSel(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // -- render ------------------------------------------------------------------------------

  if (!info) return <div className="hint">lädt …</div>;

  const generalBox = general?.kind ? (
    <p className="info-line">
      Allgemeinteil: {general.kind === "dxf" ? "DXF/DWG" : "Vorlagen-Projekt"} vom Server, gesperrt.
    </p>
  ) : general?.error ? (
    <p className="info-line company">Allgemeinteil: {general.error}</p>
  ) : null;

  if (!doc) {
    return (
      <div className="empty" style={{ padding: 32 }}>
        {generalBox}
        <p>Für dieses Projekt gibt es noch keine Legende.</p>
        <button className="btn primary" disabled={busy} onClick={proposal}>
          Vorschlag aus dem Projekt erstellen
        </button>
        <p className="hint" style={{ marginTop: 12 }}>
          Der Vorschlag enthält alle Apparate der aktuellen Importe, gegliedert nach Kategorien, mit den Firmentexten oder dem Namen aus der Bibliothek.
          Schriftgrösse {String(info.style.text_size).replace(".", ",")} mm und Symbolmassstab {String(info.style.symbol_scale).replace(".", ",")} kommen aus
          dem Firmen-Standard bzw. der Vorlage.
        </p>
      </div>
    );
  }

  const style = doc.style;
  const stale = staleItems(doc, data.rows);
  const missing = missingRows(doc, data.rows);
  const selBlock = sel && "block" in sel ? doc.blocks.find((b) => b.id === sel.block) : undefined;
  const selItem = sel?.type === "item" ? selBlock?.items.find((i) => i.id === sel.item) : undefined;
  const W = placed?.width ?? 200;
  const H = placed?.height ?? 100;
  const setStyle = (patch: Partial<LegendDoc["style"]>) => change({ ...doc, style: { ...style, ...patch } });

  return (
    <div className="legend-editor">
      {generalBox}
      <div className="legend-toolbar">
        <button className="btn small" disabled={busy} onClick={proposal} title="Legende aus den aktuellen Projektzahlen neu vorschlagen">
          Neuer Vorschlag
        </button>
        <span className="sep" />
        <button className="btn small" disabled={!hist?.past.length} onClick={() => setHist((h) => (h ? undo(h) : h))} title="Rückgängig (Strg+Z)">
          ↶ Rückgängig
        </button>
        <button className="btn small" disabled={!hist?.future.length} onClick={() => setHist((h) => (h ? redo(h) : h))} title="Wiederholen (Strg+Y)">
          ↷ Wiederholen
        </button>
        <span className="sep" />
        <button className="btn small" onClick={() => addKind("text")} title={FREE_TEXT_HINT}>
          + Freier Text
        </button>
        <button className="btn small" onClick={() => addKind("line")} title="Linienmuster, z. B. für Leitungen und Trassen">
          + Linie
        </button>
        <button className="btn small" onClick={() => addKind("note")}>
          + Hinweis
        </button>
        <button
          className="btn small"
          onClick={() => {
            const r = addBlock(doc, "Neuer Abschnitt");
            change(r.doc);
            setSel({ type: "block", block: r.id });
          }}
        >
          + Abschnitt
        </button>
        <span className="sep" />
        <label className="filter-label">
          Raster
          <select className="select" value={style.grid} onChange={(e) => setStyle({ grid: e.target.value })} aria-label="Rastermass">
            {info.grids.map((g) => (
              <option key={g.id} value={g.id}>
                {g.id === "standard" ? "★ " : ""}
                {g.label} · Zeile {String(g.row).replace(".", ",")} mm · Text {String(g.text_offset).replace(".", ",")} mm
              </option>
            ))}
          </select>
        </label>
        <label className="filter-label">
          Spalten
          <select className="select" value={style.columns} onChange={(e) => setStyle({ columns: Number(e.target.value) })}>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
        <span className="sep" />
        <button className="btn small" onClick={() => setZoom((z) => Math.max(1.5, round(z / 1.25)))} aria-label="Verkleinern">
          −
        </button>
        <span className="hint" style={{ minWidth: 44, textAlign: "center" }}>
          {Math.round((zoom / 4) * 100)} %
        </span>
        <button className="btn small" onClick={() => setZoom((z) => Math.min(12, round(z * 1.25)))} aria-label="Vergrössern">
          +
        </button>
        <span style={{ flex: 1 }} />
        <span className={saveState === "error" ? "dirty" : saveState === "saving" ? "hint" : "saved"} role="status">
          {saveState === "saving" ? "Speichert …" : saveState === "error" ? "Nicht gespeichert" : savedInfo ? `Gespeichert ${savedInfo}` : ""}
        </span>
      </div>

      <div className="legend-body">
        <aside className="legend-outline">
          <div className="section" style={{ marginTop: 0 }}>
            Abschnitte
          </div>
          {general?.kind && (
            <button className={`outline-item ${sel?.type === "general" ? "active" : ""}`} style={{ paddingLeft: 6 }} onClick={() => setSel({ type: "general" })}>
              🔒 Allgemeinteil (gesperrt)
            </button>
          )}
          {doc.blocks.map((b) => (
            <div key={b.id} className="outline-block">
              <div className={`outline-row ${sel?.type === "block" && sel.block === b.id ? "active" : ""}`}>
                <button className="fold-btn" aria-label={b.collapsed ? "Aufklappen" : "Einklappen"} onClick={() => change(updateBlock(doc, b.id, { collapsed: !b.collapsed }))}>
                  {b.collapsed ? "▸" : "▾"}
                </button>
                <span className="swatch" style={{ background: b.style.header, width: 12, height: 12 }} />
                <button className="outline-title" onClick={() => setSel({ type: "block", block: b.id })} title={b.title}>
                  {b.title || "(ohne Überschrift)"} <span className="hint">{b.items.length}</span>
                </button>
              </div>
              {!b.collapsed &&
                b.items.map((it) => (
                  <button
                    key={it.id}
                    className={`outline-item ${sel?.type === "item" && sel.item === it.id ? "active" : ""}`}
                    onClick={() => setSel({ type: "item", block: b.id, item: it.id })}
                    title={it.text}
                  >
                    {it.kind === "line" ? "― " : it.kind === "note" ? "◐ " : it.kind === "text" ? "¶ " : ""}
                    {it.text || "(ohne Text)"}
                    {stale.has(it.id) && <span className="badge weg">nicht im Projekt</span>}
                  </button>
                ))}
            </div>
          ))}

          <div className="section">Im Projekt, nicht in der Legende ({missing.length})</div>
          {missing.length === 0 ? (
            <p className="hint">Alle Apparate der aktuellen Importe sind in der Legende.</p>
          ) : (
            <>
              {missing.slice(0, 40).map((r) => (
                <button key={r.family_key} className="outline-item add" onClick={() => addRows([r])} title={`${describe(r.family_key, r.title, descriptions)} hinzufügen`}>
                  + {describe(r.family_key, r.title, descriptions)} <span className="hint">{r.total}×</span>
                </button>
              ))}
              <button className="btn small" style={{ marginTop: 6 }} onClick={() => addRows(missing)}>
                Alle hinzufügen
              </button>
            </>
          )}

          <div className="section">Aus der Bibliothek hinzufügen</div>
          <input className="input" style={{ width: "100%" }} placeholder="Name oder Katalogcode" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Bibliothek durchsuchen" />
          {results.map((f) => (
            <button key={f.id} className="outline-item add" onClick={() => addFromLibrary(f)} title={f.title}>
              + {describe(f.id.split("#")[0], f.title, descriptions)} <span className="hint">{f.representative.item}</span>
            </button>
          ))}
        </aside>

        <div className="legend-canvas" onClick={() => setSel({ type: "legend" })}>
          <svg
            className="legend-paper"
            viewBox={`0 0 ${W} ${H}`}
            width={W * zoom}
            height={H * zoom}
            style={{ fontFamily: `${style.font}, Arial, sans-serif` }}
            aria-label={`Legende, ${W} × ${H} mm`}
          >
            <defs>
              <pattern id="lg-grid" width={style.row} height={style.row} patternUnits="userSpaceOnUse" x={style.margin} y={style.margin}>
                <path d={`M${style.row} 0 L0 0 0 ${style.row}`} fill="none" stroke="#dde1e6" strokeWidth={0.08} />
              </pattern>
            </defs>
            <rect width={W} height={H} fill="#fff" />
            <rect x={style.margin} y={style.margin} width={W - 2 * style.margin} height={H - 2 * style.margin} fill="url(#lg-grid)" />
            {(placed?.prims ?? []).map((p, i) => (
              <Prim key={i} p={p} symbols={symbols} general={general} sel={sel} stale={stale} onSelect={setSel} />
            ))}
          </svg>
        </div>

        <aside className="legend-props">
          {sel?.type === "general" ? (
            <GeneralProps general={general} company={info.company} />
          ) : selItem && selBlock ? (
            <ItemProps
              item={selItem}
              block={selBlock}
              doc={doc}
              render={selItem.kind === "symbol" ? symbols[symbolRequestKey(selItem)] : undefined}
              stale={stale.has(selItem.id)}
              templateTexts={info.template_texts}
              field={field}
              change={change}
              notify={notify}
              onDescription={(fam, text) => setInfo((i) => (i ? { ...i, descriptions: { ...i.descriptions, [fam]: text } } : i))}
              onMoveTo={(to) => {
                change(moveItemToBlock(doc, selBlock.id, selItem.id, to));
                setSel({ type: "item", block: to, item: selItem.id });
              }}
              onMove={moveSelected}
              onRemove={removeSelected}
            />
          ) : sel?.type === "block" && selBlock ? (
            <BlockProps block={selBlock} field={field} change={change} doc={doc} onMove={moveSelected} onRemove={removeSelected} catTitle={catTitle} templateTexts={info.template_texts} />
          ) : (
            <DocProps
              doc={doc}
              info={info}
              field={field}
              setStyle={setStyle}
              projectId={projectId}
              notify={notify}
              exportBlock={exportBlock}
              setExportBlock={setExportBlock}
              exportGeneral={exportGeneral}
              setExportGeneral={setExportGeneral}
              hasGeneral={Boolean(general?.kind)}
            />
          )}
        </aside>
      </div>
    </div>
  );
}

// -- sheet primitives -----------------------------------------------------------------------

function Prim({
  p,
  symbols,
  general,
  sel,
  stale,
  onSelect,
  inert,
}: {
  p: LegendPrim;
  symbols: Record<string, SymbolRender>;
  general: (GeneralInfo & { svg: string; prims: LegendPrim[] }) | null;
  sel: Selection | { type: "general" };
  stale: Set<string>;
  onSelect: (s: Selection | { type: "general" }) => void;
  inert?: boolean;
}) {
  switch (p.t) {
    case "rect":
      if (p.role === "general") {
        if (general?.kind === "dxf" && general.svg)
          return <image x={p.x} y={p.y} width={p.w} height={p.h} href={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(general.svg)}`} preserveAspectRatio="xMinYMin meet" />;
        if (general?.kind === "project")
          return (
            <g transform={`translate(${p.x} ${p.y})`}>
              {general.prims.map((q, i) => (
                <Prim key={i} p={q} symbols={symbols} general={null} sel={null} stale={new Set()} onSelect={() => undefined} inert />
              ))}
            </g>
          );
        return <rect x={p.x} y={p.y} width={p.w} height={p.h} fill="#f5f5f5" stroke="#bbb" strokeWidth={0.2} strokeDasharray="1 1" />;
      }
      return <rect x={p.x} y={p.y} width={p.w} height={p.h} fill={p.fill ?? "none"} stroke={p.stroke ?? "none"} strokeWidth={p.stroke ? 0.25 : 0} />;
    case "text":
      return (
        <text x={p.x} y={p.y} fontSize={p.size} fontWeight={p.bold ? 700 : 400} fill={p.color} pointerEvents="none">
          {p.text}
        </text>
      );
    case "line":
      return <line x1={p.x1} y1={p.y1} x2={p.x2} y2={p.y2} stroke={p.color} strokeWidth={0.35} strokeDasharray={DASH[p.style as LineStyle] || undefined} strokeLinecap="round" />;
    case "half":
      return (
        <g>
          <circle cx={p.cx} cy={p.cy} r={p.r} fill="none" stroke={p.color} strokeWidth={0.18} />
          <path d={`M${p.cx} ${p.cy - p.r} A${p.r} ${p.r} 0 0 1 ${p.cx} ${p.cy + p.r} Z`} fill={p.color} />
        </g>
      );
    case "symbol": {
      const r = symbols[symbolRequestKey({ symbol_key: p.key, length_mm: p.length_mm, width_mm: p.width_mm })];
      if (!r?.svg || !r.box)
        return (
          <g>
            <rect x={p.cx - p.w / 2} y={p.cy - p.h / 2} width={p.w} height={p.h} fill="none" stroke="#999" strokeWidth={0.15} strokeDasharray="0.6 0.4" />
            <title>{r ? "Keine Symbolvorschau verfügbar" : "lädt …"}</title>
          </g>
        );
      const w = r.box[2] * p.scale;
      const h = r.box[3] * p.scale;
      return (
        <svg
          x={p.cx - w / 2}
          y={p.cy - h / 2}
          width={w}
          height={h}
          viewBox={r.box.join(" ")}
          overflow="visible"
          style={{ color: p.color, ["--sym-layer" as string]: tint(p.color, 0.45), ["--sym-bg" as string]: p.background }}
          dangerouslySetInnerHTML={{ __html: innerSvg(r.svg) }}
        />
      );
    }
    case "hit": {
      if (inert) return null;
      const selected =
        (p.kind === "item" && sel?.type === "item" && sel.item === p.id) ||
        (p.kind === "block" && sel?.type === "block" && sel.block === p.id) ||
        (p.kind === "general" && sel?.type === "general");
      const isStale = p.kind === "item" && stale.has(p.id);
      return (
        <rect
          x={p.x}
          y={p.y}
          width={p.w}
          height={p.h}
          fill={selected ? "rgba(11,107,203,0.10)" : "transparent"}
          stroke={selected ? "#0b6bcb" : isStale ? "#c92a2a" : "none"}
          strokeWidth={0.3}
          strokeDasharray={isStale && !selected ? "0.8 0.5" : undefined}
          className="lg-hit"
          onClick={(e) => {
            e.stopPropagation();
            onSelect(p.kind === "item" ? { type: "item", block: p.block, item: p.id } : p.kind === "block" ? { type: "block", block: p.block } : { type: "general" });
          }}
        >
          <title>{p.kind === "general" ? "Allgemeinteil (gesperrt)" : isStale ? "Kommt in den aktuellen Importen nicht vor" : "Anklicken zum Bearbeiten"}</title>
        </rect>
      );
    }
    default:
      return null;
  }
}

function innerSvg(svg: string): string {
  const start = svg.indexOf(">") + 1;
  const end = svg.lastIndexOf("</svg>");
  return svg.slice(start, end > start ? end : undefined);
}

// -- property panels ------------------------------------------------------------------------

type FieldFn = (apply: (d: LegendDoc, value: string) => LegendDoc) => {
  onFocus: () => void;
  onChange: (e: { target: { value: string } }) => void;
  onBlur: () => void;
};

/** Number field: one change (one undo step) when leaving the field or pressing Enter. */
function NumberInput({ value, step, placeholder, label, onCommit }: { value: number | null; step: number; placeholder?: string; label?: string; onCommit: (v: number) => void }) {
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => setText(value == null ? "" : String(value)), [value]);
  const done = () => {
    const v = Number(text.replace(",", "."));
    if (text.trim() === "" || !Number.isFinite(v)) {
      setText(value == null ? "" : String(value));
      return;
    }
    if (v !== value) onCommit(v);
  };
  return (
    <input
      className="input"
      inputMode="decimal"
      aria-label={label}
      value={text}
      step={step}
      placeholder={placeholder}
      onChange={(e) => setText(e.target.value)}
      onBlur={done}
      onKeyDown={(e) => e.key === "Enter" && done()}
    />
  );
}

function ItemProps({
  item,
  block,
  doc,
  render,
  stale,
  templateTexts,
  field,
  change,
  notify,
  onDescription,
  onMoveTo,
  onMove,
  onRemove,
}: {
  item: LegendItem;
  block: LegendBlock;
  doc: LegendDoc;
  render?: SymbolRender;
  stale: boolean;
  templateTexts: string[];
  field: FieldFn;
  change: (d: LegendDoc) => void;
  notify: (text: string, error?: boolean) => void;
  onDescription: (familyKey: string, text: string) => void;
  onMoveTo: (blockId: string) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  const [suggest, setSuggest] = useState<{ text: string; source: string }[]>([]);
  const set = (patch: Partial<LegendItem>) => change(updateItem(doc, block.id, item.id, patch));

  useEffect(() => {
    let alive = true;
    if (item.kind !== "symbol") return;
    api
      .legendTexts(item.text, item.family_key ?? "")
      .then((r) => alive && setSuggest(r.items))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item.id]);

  const listId = `lg-texts-${item.id}`;
  const title = { symbol: "Symbol", line: "Linie", note: "Hinweis", text: "Freier Text" }[item.kind];
  return (
    <>
      <h4>{title}</h4>
      {item.kind === "text" && <p className="hint">{FREE_TEXT_HINT}</p>}
      {stale && <p className="warn-text">Dieser Apparat kommt in den aktuellen Importen nicht vor.</p>}
      <label className="field">
        <span>{item.kind === "text" ? "Text" : "Beschreibung"}</span>
        <input className="input" list={listId} value={item.text} {...field((d, v) => updateItem(d, block.id, item.id, { text: v }))} />
        <datalist id={listId}>
          {[...suggest.map((s) => s.text), ...templateTexts].filter((t, i, a) => a.indexOf(t) === i).map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
      </label>
      {suggest.length > 0 && (
        <div className="suggest-list">
          <span className="hint">Vorschläge:</span>
          {suggest.slice(0, 4).map((s) => (
            <button key={s.text} className="chip-btn" onClick={() => set({ text: s.text })} title={s.source}>
              {s.text}
            </button>
          ))}
        </div>
      )}
      {item.kind === "symbol" && item.family_key && (
        <button
          className="btn small"
          onClick={async () => {
            try {
              await api.setDescription(item.family_key!, item.text);
              onDescription(item.family_key!, item.text);
              notify("Als Firmentext gespeichert (gilt beim Hinzufügen und bei neuen Vorschlägen in allen Projekten)");
            } catch (e) {
              notify((e as Error).message, true);
            }
          }}
        >
          Als Firmentext speichern
        </button>
      )}
      {item.kind === "symbol" && render?.engine && (
        <div className="form two">
          <label className="field">
            <span>Länge (mm, real)</span>
            <NumberInput value={item.length_mm} step={50} placeholder={String(render.length_mm ?? "")} onCommit={(v) => set({ length_mm: v > 0 ? v : null })} />
          </label>
          <label className="field">
            <span>Breite (mm, real)</span>
            <NumberInput value={item.width_mm} step={50} placeholder={String(render.width_mm ?? "")} onCommit={(v) => set({ width_mm: v > 0 ? v : null })} />
          </label>
        </div>
      )}
      {item.kind === "line" && (
        <div className="form two">
          <label className="field">
            <span>Linienart</span>
            <select className="select" value={item.line_style} onChange={(e) => set({ line_style: e.target.value as LineStyle })}>
              {(Object.keys(LINE_LABEL) as LineStyle[]).map((k) => (
                <option key={k} value={k}>
                  {LINE_LABEL[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Länge (mm)</span>
            <NumberInput value={item.line_length} step={1} onCommit={(v) => set({ line_length: Math.max(1, v) })} />
          </label>
        </div>
      )}
      <label className="field">
        <span>Abschnitt</span>
        <select className="select" value={block.id} onChange={(e) => onMoveTo(e.target.value)}>
          {doc.blocks.map((b) => (
            <option key={b.id} value={b.id}>
              {b.title || "(ohne Überschrift)"}
            </option>
          ))}
        </select>
      </label>
      <div className="row" style={{ marginTop: 6 }}>
        <button className="btn small" onClick={() => onMove(-1)} title="Einen Platz nach vorne (Pfeil nach oben)">
          ↑ Nach vorne
        </button>
        <button className="btn small" onClick={() => onMove(1)} title="Einen Platz nach hinten (Pfeil nach unten)">
          ↓ Nach hinten
        </button>
        <span style={{ flex: 1 }} />
        <button className="btn icon danger" onClick={onRemove} aria-label={item.kind === "text" ? "Text entfernen" : "Aus der Legende entfernen"} title={item.kind === "text" ? "Text entfernen" : "Aus der Legende entfernen"}>
          <TrashIcon />
        </button>
      </div>
    </>
  );
}

const COLOR_FIELDS: [keyof SectionStyle, string][] = [
  ["header", "Kopfleiste"],
  ["header_text", "Schrift Kopfleiste"],
  ["background", "Hintergrund"],
  ["symbol", "Symbole und Linien"],
  ["text", "Text"],
  ["border", "Umrandung"],
];

function BlockProps({
  block,
  doc,
  field,
  change,
  onMove,
  onRemove,
  catTitle,
  templateTexts,
}: {
  block: LegendBlock;
  doc: LegendDoc;
  field: FieldFn;
  change: (d: LegendDoc) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
  catTitle: Record<string, string>;
  templateTexts: string[];
}) {
  const setStyle = (patch: Partial<SectionStyle>) => change(updateSectionStyle(doc, block.id, patch));
  return (
    <>
      <h4>Abschnitt</h4>
      <p className="hint">
        {block.category_id ? `Kategorie: ${catTitle[block.category_id] ?? block.category_id}. ` : ""}
        {block.layer ? `Ebene im Export: ${block.layer}. ` : ""}Änderungen gelten nur für diese Legende.
      </p>
      <label className="field">
        <span>Überschrift</span>
        <input className="input" list="lg-headings" value={block.title} {...field((d, v) => updateBlock(d, block.id, { title: v }))} />
        <datalist id="lg-headings">
          {templateTexts.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
      </label>
      <div className="color-grid">
        {COLOR_FIELDS.map(([key, label]) => (
          <label key={key} className="color-field">
            <input type="color" value={String(block.style[key])} onChange={(e) => setStyle({ [key]: e.target.value } as Partial<SectionStyle>)} />
            <span>{label}</span>
          </label>
        ))}
      </div>
      <label className="toggle" style={{ color: "var(--fg)", marginTop: 6 }}>
        <input type="checkbox" checked={block.style.border_on} onChange={(e) => setStyle({ border_on: e.target.checked })} />
        Umrandung zeigen
      </label>
      <label className="field" style={{ marginTop: 6 }}>
        <span>Innenabstand (mm)</span>
        <NumberInput value={block.style.padding} step={0.5} onCommit={(v) => setStyle({ padding: Math.max(0, Math.min(10, v)) })} />
      </label>
      <div className="row" style={{ marginTop: 6 }}>
        <button className="btn small" onClick={() => onMove(-1)}>
          ↑ Nach oben
        </button>
        <button className="btn small" onClick={() => onMove(1)}>
          ↓ Nach unten
        </button>
        <span style={{ flex: 1 }} />
        <button className="btn icon danger" onClick={onRemove} aria-label="Abschnitt entfernen" title="Abschnitt entfernen">
          <TrashIcon />
        </button>
      </div>
    </>
  );
}

function GeneralProps({ general, company }: { general: (GeneralInfo & { svg: string }) | null; company: LegendInfo["company"] }) {
  return (
    <>
      <h4>Allgemeinteil (gesperrt)</h4>
      <p className="hint">
        Dieser Teil steht in jeder Legende zuoberst und lässt sich hier nicht ändern. Anpassen heisst: die Datei auf dem Server ersetzen. Das Programm
        liest sie beim Öffnen neu.
      </p>
      <dl className="kv">
        <dt>Quelle</dt>
        <dd style={{ wordBreak: "break-all" }}>{general?.source || "–"}</dd>
        <dt>Grösse</dt>
        <dd>{general ? `${general.w} × ${general.h} mm` : "–"}</dd>
        <dt>Admins</dt>
        <dd>{company.admins.join(", ") || "noch keine"}</dd>
      </dl>
      <p className="hint">Den Pfad ändern nur Admins unter Einstellungen → Legende der Firma.</p>
    </>
  );
}

function DocProps({
  doc,
  info,
  field,
  setStyle,
  projectId,
  notify,
  exportBlock,
  setExportBlock,
  exportGeneral,
  setExportGeneral,
  hasGeneral,
}: {
  doc: LegendDoc;
  info: LegendInfo;
  field: FieldFn;
  setStyle: (patch: Partial<LegendDoc["style"]>) => void;
  projectId: string;
  notify: (text: string, error?: boolean) => void;
  exportBlock: string;
  setExportBlock: (v: string) => void;
  exportGeneral: boolean;
  setExportGeneral: (v: boolean) => void;
  hasGeneral: boolean;
}) {
  const s = doc.style;
  const company = info.company;
  return (
    <>
      <h4>Legende</h4>
      <p className="hint">Klicke auf einen Eintrag oder eine Kopfleiste, um sie zu bearbeiten. Die Reihenfolge änderst du mit ↑ ↓ oder den Pfeiltasten.</p>
      <label className="field">
        <span>Titel</span>
        <input className="input" value={doc.title.text} {...field((d, v) => ({ ...d, title: { text: v } }))} />
      </label>
      <div className="form two">
        <label className="field">
          <span>Schriftgrösse (mm)</span>
          <NumberInput label="Schriftgrösse" value={s.text_size} step={0.25} onCommit={(v) => setStyle({ text_size: Math.max(1, Math.min(10, v)) })} />
        </label>
        <label className="field">
          <span>Symbolmassstab</span>
          <NumberInput label="Symbolmassstab" value={s.symbol_scale} step={0.1} onCommit={(v) => setStyle({ symbol_scale: Math.max(0.2, Math.min(5, v)) })} />
        </label>
        <label className="field">
          <span>Massstab Leuchten 1:</span>
          <NumberInput value={s.plan_scale} step={10} onCommit={(v) => setStyle({ plan_scale: Math.max(1, v) })} />
        </label>
        <label className="field">
          <span>Blattbreite</span>
          <span className="hint" style={{ lineHeight: "34px" }}>
            {s.width} mm inkl. Rand
          </span>
        </label>
      </div>
      <p className="hint">
        Gilt für alle Texte und Symbole dieses Projekts. Firmen-Standard: Schrift {String(company.text_size).replace(".", ",")} mm, Massstab{" "}
        {String(company.symbol_scale).replace(".", ",")}.
      </p>
      <button
        className="btn small"
        disabled={!company.is_admin}
        title={company.is_admin ? "Schriftgrösse und Symbolmassstab als Firmen-Standard für neue Projekte speichern" : "Nur Admins aus den Firmeneinstellungen"}
        onClick={async () => {
          try {
            const r = await api.rememberLegend(projectId, doc);
            info.company.text_size = r.text_size;
            info.company.symbol_scale = r.symbol_scale;
            notify("Für neue Projekte gemerkt. Bestehende Projekte bleiben unverändert.");
          } catch (e) {
            notify((e as Error).message, true);
          }
        }}
      >
        Für neue Projekte merken
      </button>
      {!company.is_admin && <p className="hint">Nur Admins ({company.admins.join(", ")}) dürfen den Firmen-Standard ändern.</p>}

      <div className="section">Export</div>
      <label className="field">
        <span>Was exportieren</span>
        <select className="select" value={exportBlock} onChange={(e) => setExportBlock(e.target.value)}>
          <option value="">Ganze Legende</option>
          {doc.blocks.map((b) => (
            <option key={b.id} value={b.id}>
              Nur «{b.title || "(ohne Überschrift)"}»
            </option>
          ))}
        </select>
      </label>
      <label className="toggle" style={{ color: "var(--fg)" }}>
        <input type="checkbox" checked={exportGeneral} disabled={!hasGeneral} onChange={(e) => setExportGeneral(e.target.checked)} />
        Allgemeinteil einschliessen
      </label>
      <div className="row" style={{ marginTop: 6 }}>
        <a className="btn small" href={api.legendExportUrl(projectId, "dxf", exportBlock, exportGeneral && hasGeneral)} download>
          DXF exportieren
        </a>
        <a
          className="btn small"
          href={info.oda ? api.legendExportUrl(projectId, "dwg", exportBlock, exportGeneral && hasGeneral) : undefined}
          download
          onClick={(e) => {
            if (!info.oda) {
              e.preventDefault();
              notify("Für DWG-Dateien wird der ODA File Converter gebraucht. Er ist nicht installiert. Alternative: DXF exportieren.", true);
            }
          }}
        >
          DWG exportieren
        </a>
      </div>
      <p className="hint">Die Datei entspricht der Vorschau: DXF R2013, Farben als Truecolor, jedes Symbol als Block. N4D wird nicht geschrieben.</p>
    </>
  );
}

function round(v: number): number {
  return Math.round(v * 1000) / 1000;
}

function formatStamp(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso || "");
  return m ? `${m[3]}.${m[2]}. ${m[4]}:${m[5]}` : "";
}
