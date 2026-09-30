import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Category, FamilyItem, ProjectDetail, SymbolRender } from "../api";
import {
  addBlock,
  addItem,
  blockForCategory,
  commit,
  drawingSize,
  fitScale,
  History,
  historyOf,
  LegendBlock,
  LegendDoc,
  LegendItem,
  LineStyle,
  missingRows,
  moveBlockInOrder,
  moveItemToBlock,
  newId,
  paperSize,
  push,
  redo,
  removeBlock,
  removeItem,
  replace,
  Selection,
  snap,
  staleItems,
  symbolRequestKey,
  undo,
  updateBlock,
  updateItem,
} from "../legend";

interface Props {
  projectId: string;
  data: ProjectDetail;
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
}

type SaveState = "idle" | "saving" | "saved" | "error";

const DASH: Record<LineStyle, string> = { solid: "", dashed: "2 1.2", dotted: "0.2 1", dashdot: "2 0.8 0.2 0.8" };
const LINE_LABEL: Record<LineStyle, string> = {
  solid: "durchgezogen",
  dashed: "gestrichelt",
  dotted: "punktiert",
  dashdot: "Strich-Punkt",
};
const INK = "#111";

interface Drag {
  kind: "item" | "block" | "text" | "title";
  block?: string;
  id?: string;
  start: { x: number; y: number };
  orig: { x: number; y: number };
  before: LegendDoc;
  moved: boolean;
}

export default function LegendEditor({ projectId, data, categories, notify }: Props) {
  const [hist, setHist] = useState<History<LegendDoc> | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [templateTexts, setTemplateTexts] = useState<string[]>([]);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [savedInfo, setSavedInfo] = useState("");
  const [sel, setSel] = useState<Selection>(null);
  const [zoom, setZoom] = useState(4);
  const [snapOn, setSnapOn] = useState(true);
  const [symbols, setSymbols] = useState<Record<string, SymbolRender>>({});
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<FamilyItem[]>([]);
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<Drag | null>(null);
  const lastSaved = useRef<LegendDoc | null>(null);
  const fieldBefore = useRef<LegendDoc | null>(null);

  const doc = hist?.present ?? null;
  const colorByCat = useMemo(
    () => Object.fromEntries(data.category_colors.map((c) => [c.id, c.color])),
    [data.category_colors],
  );

  // -- load and save ---------------------------------------------------------------

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    api
      .legend(projectId)
      .then((r) => {
        if (!alive) return;
        setTemplateTexts(r.template_texts);
        if (r.legend) {
          lastSaved.current = r.legend.doc;
          setHist(historyOf(r.legend.doc));
          setSavedInfo(`${formatStamp(r.legend.updated_at)} von ${r.legend.updated_by}`);
        } else setHist(null);
        setLoaded(true);
      })
      .catch((e) => notify((e as Error).message, true));
    return () => {
      alive = false;
    };
  }, [projectId, notify]);

  useEffect(() => {
    if (!doc || doc === lastSaved.current) return;
    setSaveState("saving");
    const handle = window.setTimeout(async () => {
      try {
        const r = await api.saveLegend(projectId, doc);
        lastSaved.current = doc;
        setSaveState("saved");
        setSavedInfo(`${formatStamp(r.legend.updated_at)} von ${r.legend.updated_by}`);
      } catch (e) {
        setSaveState("error");
        notify(`Legende nicht gespeichert: ${(e as Error).message}`, true);
      }
    }, 700);
    return () => window.clearTimeout(handle);
  }, [doc, projectId, notify]);

  // -- symbol drawings in true size --------------------------------------------------

  useEffect(() => {
    if (!doc) return;
    const need = new Map<string, LegendItem>();
    for (const b of doc.blocks)
      for (const it of b.items)
        if (it.kind === "symbol" && it.symbol_key && !symbols[symbolRequestKey(it)]) need.set(symbolRequestKey(it), it);
    if (!need.size) return;
    const list = [...need.values()];
    api
      .legendSymbols(list.map((it) => ({ symbol_key: it.symbol_key!, family_key: it.family_key, length_mm: it.length_mm, width_mm: it.width_mm })))
      .then((r) => {
        setSymbols((prev) => {
          const next = { ...prev };
          list.forEach((it, i) => (next[symbolRequestKey(it)] = r.items[i]));
          return next;
        });
      })
      .catch(() => undefined);
  }, [doc, symbols]);

  // -- library search for adding symbols ------------------------------------------------

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

  // -- editing helpers ----------------------------------------------------------------

  const change = useCallback((next: LegendDoc) => setHist((h) => (h ? push(h, next) : historyOf(next))), []);

  /** Text fields: live change while typing, one undo step per field visit. */
  function field(apply: (d: LegendDoc, value: string) => LegendDoc) {
    return {
      onFocus: () => (fieldBefore.current = doc),
      onChange: (e: { target: { value: string } }) =>
        setHist((h) => (h ? replace(h, apply(h.present, e.target.value)) : h)),
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
      const r = await api.proposeLegend(projectId);
      change(r.doc);
      setSel(null);
      notify("Vorschlag erstellt");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function arrange() {
    if (!doc) return;
    setBusy(true);
    try {
      const r = await api.layoutLegend(doc);
      change(r.doc);
      notify("Automatisch angeordnet");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  function removeSelected() {
    if (!doc || !sel) return;
    if (sel.type === "item") change(removeItem(doc, sel.block, sel.item));
    else if (sel.type === "text") change({ ...doc, texts: doc.texts.filter((t) => t.id !== sel.id) });
    else if (sel.type === "block") {
      const b = doc.blocks.find((x) => x.id === sel.block);
      if (b && b.items.length && !window.confirm(`Abschnitt «${b.title}» mit ${b.items.length} Einträgen entfernen?`)) return;
      change(removeBlock(doc, sel.block));
    } else return;
    setSel(null);
  }

  function nudge(dx: number, dy: number) {
    if (!doc || !sel) return;
    if (sel.type === "item") {
      const it = doc.blocks.find((b) => b.id === sel.block)?.items.find((i) => i.id === sel.item);
      if (it) change(updateItem(doc, sel.block, sel.item, { x: round(it.x + dx), y: round(it.y + dy) }));
    } else if (sel.type === "block") {
      const b = doc.blocks.find((x) => x.id === sel.block);
      if (b) change(updateBlock(doc, sel.block, { x: round(b.x + dx), y: round(b.y + dy) }));
    } else if (sel.type === "text") {
      change({ ...doc, texts: doc.texts.map((t) => (t.id === sel.id ? { ...t, x: round(t.x + dx), y: round(t.y + dy) } : t)) });
    } else if (sel.type === "title") change({ ...doc, title: { ...doc.title, x: round(doc.title.x + dx), y: round(doc.title.y + dy) } });
  }

  // keyboard: undo, redo, delete, arrows
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
      } else if ((e.key === "Delete" || e.key === "Backspace") && sel) {
        e.preventDefault();
        removeSelected();
      } else if (e.key.startsWith("Arrow") && sel && doc) {
        e.preventDefault();
        const step = (doc.style.grid || 0.5) * (e.shiftKey ? 10 : 1);
        const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
        if (d) nudge(d[0], d[1]);
      } else if (e.key === "Escape") setSel(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // -- pointer dragging on the paper --------------------------------------------------

  function toMm(e: { clientX: number; clientY: number }) {
    const svg = svgRef.current!;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const m = svg.getScreenCTM();
    const p = m ? pt.matrixTransform(m.inverse()) : pt;
    return { x: p.x, y: p.y };
  }

  function startDrag(e: React.PointerEvent, d: Omit<Drag, "start" | "before" | "moved">, selection: Selection) {
    if (!doc || e.button !== 0) return;
    e.stopPropagation();
    setSel(selection);
    drag.current = { ...d, start: toMm(e), before: doc, moved: false };
    svgRef.current?.setPointerCapture(e.pointerId);
  }

  function onMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d || !doc) return;
    const p = toMm(e);
    const g = doc.style.grid;
    const x = snap(d.orig.x + p.x - d.start.x, g, snapOn);
    const y = snap(d.orig.y + p.y - d.start.y, g, snapOn);
    if (!d.moved && Math.abs(p.x - d.start.x) < 0.3 && Math.abs(p.y - d.start.y) < 0.3) return;
    d.moved = true;
    setHist((h) => {
      if (!h) return h;
      const cur = h.present;
      if (d.kind === "item") return replace(h, updateItem(cur, d.block!, d.id!, { x, y }));
      if (d.kind === "block") return replace(h, updateBlock(cur, d.block!, { x, y }));
      if (d.kind === "text") return replace(h, { ...cur, texts: cur.texts.map((t) => (t.id === d.id ? { ...t, x, y } : t)) });
      return replace(h, { ...cur, title: { ...cur.title, x, y } });
    });
  }

  function endDrag() {
    const d = drag.current;
    drag.current = null;
    if (d?.moved) setHist((h) => (h ? commit(h, d.before) : h));
  }

  // -- render --------------------------------------------------------------------------

  if (!loaded) return <div className="hint">lädt …</div>;

  if (!doc) {
    return (
      <div className="empty" style={{ padding: 32 }}>
        <p>Für dieses Projekt gibt es noch keine Legende.</p>
        <button className="btn primary" disabled={busy} onClick={proposal}>
          Vorschlag aus dem Projekt erstellen
        </button>
        <p className="hint" style={{ marginTop: 12 }}>
          Der Vorschlag enthält alle Apparate der aktuellen Importe, gegliedert nach Kategorien, mit den Firmentexten
          oder dem Namen aus der Bibliothek.
        </p>
      </div>
    );
  }

  const style = doc.style;
  const paper = paperSize(doc);
  const stale = staleItems(doc, data.rows);
  const missing = missingRows(doc, data.rows);
  const selBlock = sel && "block" in sel ? doc.blocks.find((b) => b.id === sel.block) : undefined;
  const selItem = sel?.type === "item" ? selBlock?.items.find((i) => i.id === sel.item) : undefined;
  const catTitle = Object.fromEntries(categories.map((c) => [c.id, c.title]));
  const targetBlock = selBlock?.id ?? doc.blocks[0]?.id ?? null;

  /** Scale that fits a new symbol into the row of its block (renders it first if needed). */
  async function fitFor(symbolKey: string, familyKey: string | null, blockSpacing: number): Promise<number> {
    const key = symbolRequestKey({ symbol_key: symbolKey, length_mm: null, width_mm: null });
    let r = symbols[key];
    if (!r) {
      try {
        r = (await api.legendSymbols([{ symbol_key: symbolKey, family_key: familyKey, length_mm: null, width_mm: null }])).items[0];
        setSymbols((prev) => ({ ...prev, [key]: r }));
      } catch {
        return 1;
      }
    }
    if (!r?.box) return 1;
    const f = r.engine ? 50 / style.plan_scale : 1;
    const size = drawingSize(r.box);
    return fitScale(size.w * f, size.h * f, blockSpacing, style.text_offset);
  }

  async function addFromRow(r: (typeof data.rows)[number]) {
    let d = doc!;
    let blockId = blockForCategory(d, r.categories, null);
    if (!blockId || !d.blocks.find((b) => b.id === blockId && b.category_id && r.categories.includes(b.category_id))) {
      const cat = r.categories.find((c) => catTitle[c]);
      if (cat && !d.blocks.some((b) => b.category_id === cat)) {
        const nb = addBlock(d, catTitle[cat], cat);
        d = nb.doc;
        blockId = nb.id;
      } else blockId = blockId ?? targetBlock;
    }
    if (!blockId) {
      const nb = addBlock(d, "Legende");
      d = nb.doc;
      blockId = nb.id;
    }
    const spacing = d.blocks.find((b) => b.id === blockId)?.spacing ?? style.row;
    const scale = await fitFor(r.symbol_key, r.family_key, spacing);
    const r2 = addItem(d, blockId, { kind: "symbol", family_key: r.family_key, symbol_key: r.symbol_key, text: r.title, scale });
    change(r2.doc);
    setSel({ type: "item", block: blockId, item: r2.id });
  }

  async function addFromLibrary(f: FamilyItem) {
    let d = doc!;
    let blockId = blockForCategory(d, f.categories, targetBlock);
    if (!blockId) {
      const nb = addBlock(d, "Legende");
      d = nb.doc;
      blockId = nb.id;
    }
    const familyKey = f.id.split("#")[0];
    const spacing = d.blocks.find((b) => b.id === blockId)?.spacing ?? style.row;
    const scale = await fitFor(f.representative.key, familyKey, spacing);
    const r = addItem(d, blockId, {
      kind: "symbol",
      family_key: familyKey,
      symbol_key: f.representative.key,
      text: f.title,
      scale,
    });
    change(r.doc);
    setSel({ type: "item", block: blockId, item: r.id });
    setSearch("");
  }

  function addKind(kind: "line" | "note") {
    let d = doc!;
    let blockId = targetBlock;
    if (!blockId) {
      const nb = addBlock(d, "Legende");
      d = nb.doc;
      blockId = nb.id;
    }
    const r = addItem(d, blockId, kind === "line" ? { kind, text: "UP-Wandleitung" } : { kind, text: "Hinweis" });
    change(r.doc);
    setSel({ type: "item", block: blockId, item: r.id });
  }

  return (
    <div className="legend-editor">
      <div className="legend-toolbar">
        <button className="btn small" disabled={busy} onClick={proposal} title="Legende aus den aktuellen Projektzahlen neu vorschlagen">
          Neuer Vorschlag
        </button>
        <button className="btn small" disabled={busy} onClick={arrange} title="Abschnitte und Einträge nach Spalten und Zeilenabstand ordnen">
          Automatisch anordnen
        </button>
        <span className="sep" />
        <button className="btn small" disabled={!hist?.past.length} onClick={() => setHist((h) => (h ? undo(h) : h))} title="Rückgängig (Strg+Z)">
          ↶ Rückgängig
        </button>
        <button className="btn small" disabled={!hist?.future.length} onClick={() => setHist((h) => (h ? redo(h) : h))} title="Wiederholen (Strg+Y)">
          ↷ Wiederholen
        </button>
        <span className="sep" />
        <button
          className="btn small"
          onClick={() => {
            const id = newId();
            change({ ...doc, texts: [...doc.texts, { id, text: "Text", x: style.margin, y: paper.height - style.margin, size: style.text_size }] });
            setSel({ type: "text", id });
          }}
        >
          + Freier Text
        </button>
        <span className="sep" />
        <label className="toggle">
          <input type="checkbox" checked={snapOn} onChange={(e) => setSnapOn(e.target.checked)} />
          Einrasten
        </label>
        <label className="filter-label">
          Raster
          <select
            className="select"
            value={style.grid}
            onChange={(e) => change({ ...doc, style: { ...style, grid: Number(e.target.value) } })}
          >
            {[0.25, 0.5, 1, 2.5, 4.55, 5].map((g) => (
              <option key={g} value={g}>
                {String(g).replace(".", ",")} mm
              </option>
            ))}
          </select>
        </label>
        <span className="sep" />
        <button className="btn small" onClick={() => setZoom((z) => Math.max(1, round(z / 1.25)))} aria-label="Verkleinern">
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
          <div className="section" style={{ marginTop: 0 }}>Abschnitte</div>
          {doc.blocks.map((b, i) => (
            <div key={b.id} className="outline-block">
              <div className={`outline-row ${sel?.type === "block" && sel.block === b.id ? "active" : ""}`}>
                <button
                  className="fold-btn"
                  aria-label={b.collapsed ? "Aufklappen" : "Einklappen"}
                  onClick={() => change(updateBlock(doc, b.id, { collapsed: !b.collapsed }))}
                >
                  {b.collapsed ? "▸" : "▾"}
                </button>
                <button className="outline-title" onClick={() => setSel({ type: "block", block: b.id })} title={b.title}>
                  {b.title || "(ohne Überschrift)"} <span className="hint">{b.items.length}</span>
                </button>
                <button className="btn small" disabled={i === 0} onClick={() => change(moveBlockInOrder(doc, b.id, -1))} aria-label="Abschnitt nach oben">
                  ↑
                </button>
                <button
                  className="btn small"
                  disabled={i === doc.blocks.length - 1}
                  onClick={() => change(moveBlockInOrder(doc, b.id, 1))}
                  aria-label="Abschnitt nach unten"
                >
                  ↓
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
                    {it.kind === "line" ? "― " : it.kind === "note" ? "◐ " : ""}
                    {it.text || "(ohne Text)"}
                    {stale.has(it.id) && <span className="badge weg">nicht im Projekt</span>}
                  </button>
                ))}
            </div>
          ))}
          <div className="row" style={{ marginTop: 8 }}>
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
            <button className="btn small" onClick={() => addKind("line")} title="Linienmuster, z. B. für Leitungen und Trassen">
              + Linie
            </button>
            <button className="btn small" onClick={() => addKind("note")}>
              + Hinweis
            </button>
          </div>

          <div className="section">Im Projekt, nicht in der Legende ({missing.length})</div>
          {missing.length === 0 ? (
            <p className="hint">Alle Apparate der aktuellen Importe sind in der Legende.</p>
          ) : (
            <>
              {missing.slice(0, 40).map((r) => (
                <button key={r.family_key} className="outline-item add" onClick={() => addFromRow(r)} title={`${r.title} hinzufügen`}>
                  + {r.title} <span className="hint">{r.total}×</span>
                </button>
              ))}
              <button
                className="btn small"
                style={{ marginTop: 6 }}
                onClick={async () => {
                  const list = missing.filter((r) => r.symbol_key);
                  let renders: SymbolRender[] = [];
                  try {
                    renders = (await api.legendSymbols(list.map((r) => ({ symbol_key: r.symbol_key, family_key: r.family_key, length_mm: null, width_mm: null })))).items;
                  } catch {
                    renders = [];
                  }
                  let d = doc;
                  for (const [n, r] of list.entries()) {
                    let blockId = blockForCategory(d, r.categories, null);
                    if (!blockId) {
                      const cat = r.categories.find((c) => catTitle[c]);
                      const nb = addBlock(d, cat ? catTitle[cat] : "Ohne Kategorie", cat ?? null);
                      d = nb.doc;
                      blockId = nb.id;
                    }
                    const rr = renders[n];
                    const spacing = d.blocks.find((b) => b.id === blockId)?.spacing ?? style.row;
                    const size = rr?.box ? drawingSize(rr.box) : null;
                    const f = rr?.engine ? 50 / style.plan_scale : 1;
                    const scale = size ? fitScale(size.w * f, size.h * f, spacing, style.text_offset) : 1;
                    d = addItem(d, blockId, { kind: "symbol", family_key: r.family_key, symbol_key: r.symbol_key, text: r.title, scale }).doc;
                  }
                  change(d);
                }}
              >
                Alle hinzufügen
              </button>
            </>
          )}

          <div className="section">Aus der Bibliothek hinzufügen</div>
          <input className="input" style={{ width: "100%" }} placeholder="Name oder Katalogcode" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Bibliothek durchsuchen" />
          {results.map((f) => (
            <button key={f.id} className="outline-item add" onClick={() => addFromLibrary(f)} title={f.title}>
              + {f.title} <span className="hint">{f.representative.item}</span>
            </button>
          ))}
        </aside>

        <div className="legend-canvas" onPointerDown={() => setSel(null)}>
          <svg
            ref={svgRef}
            className="legend-paper"
            viewBox={`0 0 ${paper.width} ${paper.height}`}
            width={paper.width * zoom}
            height={paper.height * zoom}
            onPointerMove={onMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onPointerDown={(e) => {
              e.stopPropagation();
              setSel(null);
            }}
            style={{ color: INK, fontFamily: `${style.font}, sans-serif` }}
          >
            <defs>
              <pattern id="lg-grid" width={5} height={5} patternUnits="userSpaceOnUse">
                <path d="M5 0 L0 0 0 5" fill="none" stroke="#e6e8eb" strokeWidth={0.1} />
              </pattern>
            </defs>
            <rect width={paper.width} height={paper.height} fill="#fff" />
            {snapOn && <rect width={paper.width} height={paper.height} fill="url(#lg-grid)" />}
            {Array.from({ length: style.page_columns - 1 }, (_, k) => (
              <line
                key={k}
                x1={style.margin + style.column_width * (k + 1)}
                x2={style.margin + style.column_width * (k + 1)}
                y1={0}
                y2={paper.height}
                stroke="#cfd4da"
                strokeWidth={0.15}
                strokeDasharray="1 1"
              />
            ))}
            {doc.title.text && (
              <text
                x={doc.title.x}
                y={doc.title.y + doc.title.size}
                fontSize={doc.title.size}
                fontWeight={700}
                fill={INK}
                className={`lg-hit ${sel?.type === "title" ? "lg-selected-text" : ""}`}
                onPointerDown={(e) => startDrag(e, { kind: "title", orig: { x: doc.title.x, y: doc.title.y } }, { type: "title" })}
              >
                {doc.title.text}
              </text>
            )}
            {doc.blocks.map((b) => (
              <BlockView
                key={b.id}
                block={b}
                style={style}
                color={(b.category_id && colorByCat[b.category_id]) || "#b9c0c9"}
                symbols={symbols}
                sel={sel}
                stale={stale}
                onBlockDown={(e) => startDrag(e, { kind: "block", block: b.id, orig: { x: b.x, y: b.y } }, { type: "block", block: b.id })}
                onItemDown={(e, it) =>
                  startDrag(e, { kind: "item", block: b.id, id: it.id, orig: { x: it.x, y: it.y } }, { type: "item", block: b.id, item: it.id })
                }
              />
            ))}
            {doc.texts.map((t) => (
              <text
                key={t.id}
                x={t.x}
                y={t.y}
                fontSize={t.size}
                fill={INK}
                className={`lg-hit ${sel?.type === "text" && sel.id === t.id ? "lg-selected-text" : ""}`}
                onPointerDown={(e) => startDrag(e, { kind: "text", id: t.id, orig: { x: t.x, y: t.y } }, { type: "text", id: t.id })}
              >
                {t.text}
              </text>
            ))}
          </svg>
        </div>

        <aside className="legend-props">
          {selItem && selBlock ? (
            <ItemProps
              item={selItem}
              block={selBlock}
              doc={doc}
              render={selItem.kind === "symbol" ? symbols[symbolRequestKey(selItem)] : undefined}
              stale={stale.has(selItem.id)}
              templateTexts={templateTexts}
              field={field}
              change={change}
              notify={notify}
              onMoveTo={(to) => {
                change(moveItemToBlock(doc, selBlock.id, selItem.id, to));
                setSel({ type: "item", block: to, item: selItem.id });
              }}
              onRemove={removeSelected}
            />
          ) : sel?.type === "block" && selBlock ? (
            <BlockProps block={selBlock} templateTexts={templateTexts} field={field} change={change} doc={doc} onRemove={removeSelected} catTitle={catTitle} />
          ) : sel?.type === "text" ? (
            <TextProps doc={doc} id={sel.id} field={field} onRemove={removeSelected} />
          ) : sel?.type === "title" ? (
            <>
              <h4>Legendentitel</h4>
              <label className="field">
                <span>Text</span>
                <input className="input" value={doc.title.text} {...field((d, v) => ({ ...d, title: { ...d.title, text: v } }))} />
              </label>
              <label className="field">
                <span>Schriftgrösse (mm)</span>
                <NumberInput value={doc.title.size} step={0.5} onCommit={(v) => change({ ...doc, title: { ...doc.title, size: v } })} />
              </label>
            </>
          ) : (
            <DocProps doc={doc} change={change} />
          )}
        </aside>
      </div>
    </div>
  );
}

// -- canvas parts ---------------------------------------------------------------------

function BlockView({
  block,
  style,
  color,
  symbols,
  sel,
  stale,
  onBlockDown,
  onItemDown,
}: {
  block: LegendBlock;
  style: LegendDoc["style"];
  color: string;
  symbols: Record<string, SymbolRender>;
  sel: Selection;
  stale: Set<string>;
  onBlockDown: (e: React.PointerEvent) => void;
  onItemDown: (e: React.PointerEvent, it: LegendItem) => void;
}) {
  const head = block.heading_size * 1.8;
  const colw = style.column_width / Math.max(1, block.columns);
  const blockSelected = sel?.type === "block" && sel.block === block.id;
  return (
    <g transform={`translate(${block.x} ${block.y})`} style={{ ["--sym-layer" as string]: color, ["--sym-bg" as string]: "#fff" }}>
      <rect
        x={-1}
        y={-0.5}
        width={style.column_width - 2}
        height={head}
        fill={blockSelected ? "rgba(11,107,203,0.08)" : "transparent"}
        stroke={blockSelected ? "#0b6bcb" : "none"}
        strokeWidth={0.2}
        strokeDasharray="1 0.6"
        className="lg-hit lg-move"
        onPointerDown={onBlockDown}
      >
        <title>Abschnitt verschieben</title>
      </rect>
      {block.title && (
        <text x={0} y={block.heading_size} fontSize={block.heading_size} fontWeight={700} fill="#111" pointerEvents="none">
          {block.title}
        </text>
      )}
      {block.items.map((it) => {
        const selected = sel?.type === "item" && sel.item === it.id;
        const r = it.kind === "symbol" ? symbols[symbolRequestKey(it)] : undefined;
        let w = 5;
        let h = 5;
        let pic: React.ReactNode = null;
        if (it.kind === "symbol") {
          if (r?.svg && r.box) {
            const s = it.scale * (r.engine ? 50 / style.plan_scale : 1);
            w = r.box[2] * s;
            h = r.box[3] * s;
            pic = (
              <svg
                x={it.x - w / 2}
                y={it.y - h / 2}
                width={w}
                height={h}
                viewBox={r.box.join(" ")}
                overflow="visible"
                dangerouslySetInnerHTML={{ __html: innerSvg(r.svg) }}
              />
            );
          } else {
            pic = (
              <g>
                <rect x={it.x - 2.5} y={it.y - 2.5} width={5} height={5} fill="none" stroke="#999" strokeWidth={0.15} strokeDasharray="0.6 0.4" />
                <text x={it.x} y={it.y + 0.6} fontSize={1.3} textAnchor="middle" fill="#777">
                  {r ? "keine Vorschau" : "…"}
                </text>
              </g>
            );
          }
        } else if (it.kind === "line") {
          w = it.line_length;
          h = 2;
          pic = (
            <line
              x1={it.x - w / 2}
              x2={it.x + w / 2}
              y1={it.y}
              y2={it.y}
              stroke={color}
              strokeWidth={0.35}
              strokeDasharray={DASH[it.line_style] || undefined}
              strokeLinecap="round"
            />
          );
        } else {
          pic = (
            <g>
              <circle cx={it.x} cy={it.y} r={1.8} fill="none" stroke="#111" strokeWidth={0.18} />
              <path d={`M${it.x} ${it.y - 1.8} A1.8 1.8 0 0 1 ${it.x} ${it.y + 1.8} Z`} fill="#111" />
            </g>
          );
        }
        const tx = it.x + Math.max(style.text_offset, w / 2 + 2);
        const textW = Math.min(colw - (tx - it.x), it.text.length * it.text_size * 0.55);
        return (
          <g key={it.id} className="lg-hit lg-move" onPointerDown={(e) => onItemDown(e, it)}>
            <rect
              x={it.x - Math.max(w, 5) / 2 - 0.6}
              y={it.y - Math.max(h, it.text_size * 1.6) / 2 - 0.4}
              width={tx - it.x + Math.max(w, 5) / 2 + Math.max(textW, 4) + 1}
              height={Math.max(h, it.text_size * 1.6) + 0.8}
              fill={selected ? "rgba(11,107,203,0.08)" : "transparent"}
              stroke={selected ? "#0b6bcb" : stale.has(it.id) ? "#c92a2a" : "none"}
              strokeWidth={0.2}
              strokeDasharray={stale.has(it.id) ? "0.8 0.5" : undefined}
            />
            {pic}
            <text x={tx} y={it.y + it.text_size * 0.36} fontSize={it.text_size} fill="#111">
              {it.text}
            </text>
            {stale.has(it.id) && <title>Kommt in den aktuellen Importen nicht vor</title>}
          </g>
        );
      })}
    </g>
  );
}

function innerSvg(svg: string): string {
  const start = svg.indexOf(">") + 1;
  const end = svg.lastIndexOf("</svg>");
  return svg.slice(start, end > start ? end : undefined);
}

// -- property panels ------------------------------------------------------------------

type FieldFn = (apply: (d: LegendDoc, value: string) => LegendDoc) => {
  onFocus: () => void;
  onChange: (e: { target: { value: string } }) => void;
  onBlur: () => void;
};

function NumberInput({ value, step, min, placeholder, onCommit }: { value: number | null; step: number; min?: number; placeholder?: string; onCommit: (v: number) => void }) {
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
      value={text}
      step={step}
      min={min}
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
  onMoveTo,
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
  onMoveTo: (blockId: string) => void;
  onRemove: () => void;
}) {
  const [suggest, setSuggest] = useState<{ text: string; source: string }[]>([]);
  const set = (patch: Partial<LegendItem>) => change(updateItem(doc, block.id, item.id, patch));

  useEffect(() => {
    let alive = true;
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
  return (
    <>
      <h4>{item.kind === "symbol" ? "Symbol" : item.kind === "line" ? "Linie" : "Hinweis"}</h4>
      {stale && <p className="warn-text">Dieser Apparat kommt in den aktuellen Importen nicht vor.</p>}
      <label className="field">
        <span>Beschreibung</span>
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
              notify("Als Firmentext gespeichert (gilt für neue Vorschläge in allen Projekten)");
            } catch (e) {
              notify((e as Error).message, true);
            }
          }}
        >
          Als Firmentext speichern
        </button>
      )}
      <div className="form two">
        <label className="field">
          <span>Schriftgrösse (mm)</span>
          <NumberInput value={item.text_size} step={0.25} onCommit={(v) => set({ text_size: v })} />
        </label>
        {item.kind === "symbol" && (
          <label className="field">
            <span>Massstab Symbol</span>
            <NumberInput value={item.scale} step={0.1} onCommit={(v) => set({ scale: Math.max(0.05, v) })} />
          </label>
        )}
        {item.kind === "symbol" && render?.engine && (
          <>
            <label className="field">
              <span>Länge (mm, real)</span>
              <NumberInput value={item.length_mm} step={50} placeholder={String(render.length_mm ?? "")} onCommit={(v) => set({ length_mm: v > 0 ? v : null })} />
            </label>
            <label className="field">
              <span>Breite (mm, real)</span>
              <NumberInput value={item.width_mm} step={50} placeholder={String(render.width_mm ?? "")} onCommit={(v) => set({ width_mm: v > 0 ? v : null })} />
            </label>
          </>
        )}
        {item.kind === "line" && (
          <>
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
          </>
        )}
        <label className="field">
          <span>X (mm)</span>
          <NumberInput value={item.x} step={0.5} onCommit={(v) => set({ x: v })} />
        </label>
        <label className="field">
          <span>Y (mm)</span>
          <NumberInput value={item.y} step={0.5} onCommit={(v) => set({ y: v })} />
        </label>
      </div>
      {item.kind === "symbol" && render?.engine && (
        <p className="hint">
          Parametrische Leuchte: Länge und Breite in Millimetern wie im Plan, gezeichnet im Massstab 1:{doc.style.plan_scale}
          mal «Massstab Symbol». Für die echte Grösse den Massstab auf 1 setzen.
        </p>
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
      <button className="btn small danger" style={{ marginTop: 8 }} onClick={onRemove}>
        Aus der Legende entfernen
      </button>
    </>
  );
}

function BlockProps({
  block,
  doc,
  templateTexts,
  field,
  change,
  onRemove,
  catTitle,
}: {
  block: LegendBlock;
  doc: LegendDoc;
  templateTexts: string[];
  field: FieldFn;
  change: (d: LegendDoc) => void;
  onRemove: () => void;
  catTitle: Record<string, string>;
}) {
  const set = (patch: Partial<LegendBlock>) => change(updateBlock(doc, block.id, patch));
  return (
    <>
      <h4>Abschnitt</h4>
      <p className="hint">
        {block.category_id ? `Kategorie: ${catTitle[block.category_id] ?? block.category_id}. ` : ""}Änderungen gelten nur für diese Legende.
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
      <div className="form two">
        <label className="field">
          <span>Spalten</span>
          <NumberInput value={block.columns} step={1} onCommit={(v) => set({ columns: Math.min(6, Math.max(1, Math.round(v))) })} />
        </label>
        <label className="field">
          <span>Zeilenabstand (mm)</span>
          <NumberInput value={block.spacing} step={0.05} onCommit={(v) => set({ spacing: Math.max(1, v) })} />
        </label>
        <label className="field">
          <span>Überschrift (mm)</span>
          <NumberInput value={block.heading_size} step={0.25} onCommit={(v) => set({ heading_size: Math.max(0.5, v) })} />
        </label>
        <label className="field">
          <span>X / Y (mm)</span>
          <span className="hint">
            {block.x} / {block.y}
          </span>
        </label>
      </div>
      <p className="hint">Spalten und Zeilenabstand wirken bei «Automatisch anordnen».</p>
      <button className="btn small danger" onClick={onRemove}>
        Abschnitt entfernen
      </button>
    </>
  );
}

function TextProps({ doc, id, field, onRemove }: { doc: LegendDoc; id: string; field: FieldFn; onRemove: () => void }) {
  const t = doc.texts.find((x) => x.id === id);
  if (!t) return null;
  const apply = (patch: Partial<typeof t>) => (d: LegendDoc) => ({ ...d, texts: d.texts.map((x) => (x.id === id ? { ...x, ...patch } : x)) });
  return (
    <>
      <h4>Freier Text</h4>
      <label className="field">
        <span>Text</span>
        <input className="input" value={t.text} {...field((d, v) => apply({ text: v })(d))} />
      </label>
      <label className="field">
        <span>Schriftgrösse (mm)</span>
        <input className="input" inputMode="decimal" value={t.size} {...field((d, v) => apply({ size: Math.max(0.5, Number(v.replace(",", ".")) || t.size) })(d))} />
      </label>
      <button className="btn small danger" style={{ marginTop: 8 }} onClick={onRemove}>
        Text entfernen
      </button>
    </>
  );
}

function DocProps({ doc, change }: { doc: LegendDoc; change: (d: LegendDoc) => void }) {
  const s = doc.style;
  const set = (patch: Partial<LegendDoc["style"]>) => change({ ...doc, style: { ...s, ...patch } });
  return (
    <>
      <h4>Legende</h4>
      <p className="hint">Klicke auf ein Symbol, einen Text oder eine Abschnittsüberschrift, um es zu bearbeiten. Ziehen verschiebt.</p>
      <div className="form two">
        <label className="field">
          <span>Legendenspalten</span>
          <NumberInput value={s.page_columns} step={1} onCommit={(v) => set({ page_columns: Math.min(8, Math.max(1, Math.round(v))) })} />
        </label>
        <label className="field">
          <span>Spaltenbreite (mm)</span>
          <NumberInput value={s.column_width} step={1} onCommit={(v) => set({ column_width: Math.max(20, v) })} />
        </label>
        <label className="field">
          <span>Höhe bis Umbruch (mm)</span>
          <NumberInput value={s.page_height} step={5} onCommit={(v) => set({ page_height: Math.max(30, v) })} />
        </label>
        <label className="field">
          <span>Text nach Symbol (mm)</span>
          <NumberInput value={s.text_offset} step={0.25} onCommit={(v) => set({ text_offset: Math.max(2, v) })} />
        </label>
        <label className="field">
          <span>Massstab Leuchten 1:</span>
          <NumberInput value={s.plan_scale} step={10} onCommit={(v) => set({ plan_scale: Math.max(1, v) })} />
        </label>
        <label className="field">
          <span>Schrift</span>
          <input className="input" value={s.font} onChange={(e) => set({ font: e.target.value || "Arial" })} />
        </label>
      </div>
      <div className="section">Tastatur</div>
      <dl className="kv">
        <dt>Strg+Z / Strg+Y</dt>
        <dd>Rückgängig / Wiederholen</dd>
        <dt>Pfeiltasten</dt>
        <dd>um ein Raster verschieben (mit Umschalt: zehn)</dd>
        <dt>Entf</dt>
        <dd>Auswahl entfernen</dd>
      </dl>
      <p className="hint">Den Export als DXF, DWG und N4D bringt Phase 5 und 6.</p>
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
