import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { DragEvent as ReactDragEvent, PointerEvent as ReactPointerEvent } from "react";
import { api, Category, FamilyItem, GeneralInfo, LegendInfo, LegendLayout, LegendPrim, ProjectDetail, SymbolRender } from "../api";
import { exportDiagnostic } from "../diagnostics";
import {
  addBlock,
  addItem,
  beginSave,
  blockForCategory,
  commit,
  coveredRows,
  describe,
  duplicateItems,
  hideCovered,
  History,
  historyOf,
  inLegend,
  insertItem,
  isCurrentSave,
  LegendBlock,
  LegendDoc,
  LegendItem,
  LineStyle,
  missingRows,
  moveBlockInOrder,
  moveItemInOrder,
  moveItemTo,
  moveItemToBlock,
  push,
  redo,
  removeBlock,
  removeItem,
  replace,
  rotateItem,
  SectionStyle,
  Selection,
  staleItems,
  symbolRequestKey,
  undo,
  updateBlock,
  updateItem,
  updateSectionStyle,
} from "../legend";
import { Icon, TrashIcon } from "./Icons";
import { SaveSession } from "../saveSession";
import { useNavigation } from "../Navigation";
import Menu from "./Menu";

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
const GRID_KEY = "nl.legend.grid";

/** What is being dragged: an entry of the legend or a new symbol from the left lists. */
type DragPayload =
  | { type: "move"; block: string; item: string }
  | { type: "add"; family_key: string | null; symbol_key: string; text: string; categories: string[] };
/** Where it lands: in front of `before` in `block` (null: at the end). */
type DropTarget = { block: string; before: string | null };

function readGridPref(): boolean {
  try {
    return window.localStorage.getItem(GRID_KEY) === "1";
  } catch {
    return false;
  }
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
  const [showGrid, setShowGrid] = useState(readGridPref);
  const [detached, setDetached] = useState(false);
  const [windowed, setWindowed] = useState(false);
  const [dropAt, setDropAt] = useState<DropTarget | null>(null);
  const [exporting, setExporting] = useState(false);
  const dragPayload = useRef<DragPayload | null>(null);
  const sheetDrag = useRef<{ block: string; item: string; x: number; y: number; active: boolean } | null>(null);
  const justDragged = useRef(false);
  const [saveSession] = useState(() => new SaveSession(projectId, api.saveLegend));
  const { register } = useNavigation();
  const layoutGate = useRef({ generation: 0 });
  const fieldBefore = useRef<LegendDoc | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

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
          saveSession.initialize(r.legend.doc);
          // entries the general part already shows: hidden (one undo step), not deleted
          const hidden = hideCovered(r.legend.doc, r.in_general);
          setHist(hidden === r.legend.doc ? historyOf(r.legend.doc) : push(historyOf(r.legend.doc), hidden));
          if (hidden !== r.legend.doc) {
            const n = hidden.blocks.flatMap((b) => b.items).filter((it) => it.hidden).length - r.legend.doc.blocks.flatMap((b) => b.items).filter((it) => it.hidden).length;
            notify(`${n} Einträge ausgeblendet: Der Allgemeinteil zeigt sie schon. Rückgängig mit Strg+Z.`);
          }
          setSavedInfo(`${formatStamp(r.legend.updated_at)} von ${r.legend.updated_by}`);
        } else {
          saveSession.initialize(null);
          setHist(null);
        }
      })
      .catch((e) => alive && notify((e as Error).message, true));
    api
      .legendGeneral(projectId)
      .then((g) => alive && setGeneral(g))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [projectId, notify, saveSession]);

  // Register the latest rendered edit before navigation events can flush it.
  useLayoutEffect(() => { saveSession.update(doc); }, [doc, saveSession]);

  const saveNow = useCallback(async (): Promise<void> => {
    if (!saveSession.dirty) return;
    setSaveState("saving");
    try {
      await saveSession.flush();
      const r = saveSession.result;
      setSaveState("saved");
      if (r) setSavedInfo(`${formatStamp(r.legend.updated_at)} von ${r.legend.updated_by}`);
    } catch (e) {
      setSaveState("error");
      notify(`Legende nicht gespeichert: ${(e as Error).message}. Bitte erneut versuchen; deine Änderungen bleiben im Editor.`, true);
      throw e;
    }
  }, [notify, saveSession]);

  useEffect(() => register({ flush: saveNow, dirty: () => saveSession.dirty }), [register, saveNow, saveSession]);

  useEffect(() => {
    if (!saveSession.dirty) return;
    setSaveState("saving");
    const handle = window.setTimeout(() => { saveNow().catch(() => undefined); }, 700);
    return () => window.clearTimeout(handle);
  }, [doc, saveNow, saveSession]);

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

  // symbol drawings for the placed symbols (and those of a general part from a template project),
  // plus the small icons of the lists on the left (same drawing, without length)
  const stripFill = Boolean(doc?.style.strip_fill);
  const stripSeen = useRef(stripFill);
  const symbolGen = useRef(0);
  useEffect(() => {
    const switched = stripSeen.current !== stripFill;
    stripSeen.current = stripFill;
    const known = switched ? {} : symbols;
    const prims = [...(placed?.prims ?? []), ...(general?.prims ?? [])].filter((p) => p.t === "symbol");
    const need = new Map<string, LegendPrim>();
    for (const p of prims) {
      const key = symbolRequestKey({ symbol_key: p.key, length_mm: p.length_mm, width_mm: p.width_mm });
      if (!known[key]) need.set(key, p);
    }
    const listed = [
      ...data.rows.filter((r) => r.total > 0 && r.symbol_key).map((r) => ({ key: r.symbol_key, family_key: r.family_key })),
      ...results.map((f) => ({ key: f.representative.key, family_key: f.key })),
    ];
    for (const l of listed) {
      const key = symbolRequestKey({ symbol_key: l.key, length_mm: null, width_mm: null });
      if (!known[key] && !need.has(key)) need.set(key, { t: "symbol", key: l.key, family_key: l.family_key, length_mm: null, width_mm: null });
    }
    if (!need.size) return;
    const list = [...need.entries()];
    const gen = ++symbolGen.current;
    api
      .legendSymbols(list.map(([, p]) => ({ symbol_key: p.key, family_key: p.family_key, length_mm: p.length_mm, width_mm: p.width_mm })), stripFill)
      .then((r) => {
        if (gen !== symbolGen.current || stripSeen.current !== stripFill) return;
        setSymbols((prev) => {
          const next = switched ? {} : { ...prev };
          list.forEach(([key], i) => (next[key] = r.items[i]));
          return next;
        });
      })
      .catch(() => undefined);
  }, [placed, general, symbols, data.rows, results, stripFill]);

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
    const familyKey = f.key;
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

  // -- drag and drop ---------------------------------------------------------------------

  function drop(payload: DragPayload | null, target: DropTarget | null) {
    setDropAt(null);
    if (!doc || !payload || !target) return;
    if (payload.type === "move") {
      if (payload.item === target.before) return;
      change(moveItemTo(doc, payload.block, payload.item, target.block, target.before));
      setSel({ type: "item", block: target.block, item: payload.item });
    } else {
      const res = insertItem(doc, target.block, { kind: "symbol", family_key: payload.family_key, symbol_key: payload.symbol_key, text: payload.text }, target.before);
      change(res.doc);
      setSel({ type: "item", block: target.block, item: res.id });
    }
  }

  /** Drop place under the pointer on the sheet: an entry (upper or lower half) or a section. */
  function sheetTargetAt(x: number, y: number): DropTarget | null {
    if (!doc) return null;
    const el = document.elementFromPoint(x, y) as (Element & { dataset?: DOMStringMap }) | null;
    const hit = el?.closest?.("[data-hit]") as (SVGElement & { dataset: DOMStringMap }) | null;
    if (!hit) return null;
    const { hit: kind, block, id } = hit.dataset;
    if (!block) return null;
    if (kind === "item" && id) {
      const r = hit.getBoundingClientRect();
      if (y < r.top + r.height / 2) return { block, before: id };
      const items = doc.blocks.find((b) => b.id === block)?.items.filter((it) => !it.hidden) ?? [];
      const i = items.findIndex((it) => it.id === id);
      return { block, before: items[i + 1]?.id ?? null };
    }
    return { block, before: null };
  }

  function startSheetDrag(e: ReactPointerEvent, block: string, item: string) {
    if (e.button !== 0) return;
    sheetDrag.current = { block, item, x: e.clientX, y: e.clientY, active: false };
  }

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = sheetDrag.current;
      if (!d) return;
      if (!d.active && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 4) return;
      d.active = true;
      setDropAt(sheetTargetAt(e.clientX, e.clientY));
    };
    const up = (e: PointerEvent) => {
      const d = sheetDrag.current;
      sheetDrag.current = null;
      if (!d?.active) return;
      justDragged.current = true;
      window.setTimeout(() => (justDragged.current = false), 0);
      drop({ type: "move", block: d.block, item: d.item }, sheetTargetAt(e.clientX, e.clientY));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  });

  /** HTML drag (left lists): what to carry. */
  function dragProps(payload: DragPayload) {
    return {
      draggable: true,
      onDragStart: (e: ReactDragEvent) => {
        dragPayload.current = payload;
        e.dataTransfer.effectAllowed = payload.type === "move" ? "move" : "copy";
        e.dataTransfer.setData("text/plain", payload.type === "move" ? "legend-entry" : payload.text);
      },
      onDragEnd: () => {
        dragPayload.current = null;
        setDropAt(null);
      },
    };
  }

  /** HTML drop on a row of the outline. */
  function dropProps(target: DropTarget) {
    return {
      onDragOver: (e: ReactDragEvent) => {
        if (!dragPayload.current) return;
        e.preventDefault();
        e.stopPropagation();
        if (dropAt?.block !== target.block || dropAt?.before !== target.before) setDropAt(target);
      },
      onDrop: (e: ReactDragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        drop(dragPayload.current, target);
        dragPayload.current = null;
      },
    };
  }

  // -- save now and export ----------------------------------------------------------------

  async function exportFile(format: "dxf" | "dwg", block: string, withGeneral: boolean) {
    if (format === "dwg" && !info?.oda) {
      notify("Für DWG-Dateien wird der ODA File Converter gebraucht. Er ist nicht installiert. Alternative: DXF exportieren.", true);
      return;
    }
    setExporting(true);
    try {
      await saveNow();
      const { name } = await api.legendExportName(projectId, format, block);
      const blob = await api.legendExportFile(api.legendExportUrl(projectId, name, format, block, withGeneral));
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
    } finally {
      setExporting(false);
    }
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
      } else if (e.key === "Escape") {
        if (sel) setSel(null);
        else if (windowed) setWindowed(false);
      }
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
  const covered = new Set(info.in_general?.covered ?? []);
  const missing = missingRows(doc, data.rows, covered);
  const inGeneralRows = coveredRows(data.rows, covered);
  const dups = duplicateItems(doc);
  const selBlock = sel && "block" in sel ? doc.blocks.find((b) => b.id === sel.block) : undefined;
  const selItem = sel?.type === "item" ? selBlock?.items.find((i) => i.id === sel.item) : undefined;
  const W = placed?.width ?? 200;
  const H = placed?.height ?? 100;
  const setStyle = (patch: Partial<LegendDoc["style"]>) => change({ ...doc, style: { ...style, ...patch } });

  return (
    <>
    {windowed && (
      <button type="button" className="legend-window-back" aria-label="Fenster schliessen" onClick={() => setWindowed(false)} />
    )}
    <div className={`legend-editor ${windowed ? "windowed" : ""}`}>
      {generalBox}
      <div className="legend-toolbar">
        <div className="tool-group" role="group" aria-label="Verlauf">
        <button className="btn small" disabled={busy} onClick={proposal} title="Legende aus den aktuellen Projektzahlen neu vorschlagen">
          Neuer Vorschlag
        </button>
        <button className="btn small" disabled={!hist?.past.length} onClick={() => setHist((h) => (h ? undo(h) : h))} title="Rückgängig (Strg+Z)">
          ↶ Rückgängig
        </button>
        <button className="btn small" disabled={!hist?.future.length} onClick={() => setHist((h) => (h ? redo(h) : h))} title="Wiederholen (Strg+Y)">
          ↷ Wiederholen
        </button>
        </div>
        <div className="tool-group" role="group" aria-label="Aufbau">
        <Menu label="Einfügen">
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
        </Menu>
        <label className="filter-label">
          Raster
          <select
            className="select"
            value={style.grid}
            onChange={(e) => {
              // row and text step change at once, so the grid lines follow without a reload
              const g = info.grids.find((x) => x.id === e.target.value);
              if (g) setStyle({ grid: g.id, row: g.row, text_offset: g.text_offset });
            }}
            aria-label="Rastermass"
          >
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
        </div>
        <div className="tool-group" role="group" aria-label="Ansicht">
        <button
          className={`btn small ${showGrid ? "is-on" : ""}`}
          aria-pressed={showGrid}
          onClick={() => {
            const next = !showGrid;
            setShowGrid(next);
            try {
              window.localStorage.setItem(GRID_KEY, next ? "1" : "0");
            } catch {
              /* only a convenience */
            }
          }}
          title="Rasterlinien im gewählten Mass einblenden. Sie erscheinen nicht im Export."
        >
          Raster anzeigen
        </button>
        <button className="btn small" onClick={() => setZoom((z) => Math.max(0.5, round(z / 1.25)))} aria-label="Verkleinern">
          −
        </button>
        <span className="hint" style={{ minWidth: 44, textAlign: "center" }}>
          {Math.round((zoom / 4) * 100)} %
        </span>
        <button className="btn small" onClick={() => setZoom((z) => Math.min(12, round(z * 1.25)))} aria-label="Vergrössern">
          +
        </button>
        <button className="btn small" onClick={() => {
          const canvas = canvasRef.current;
          if (!canvas) return;
          const padding = getComputedStyle(canvas);
          const width = canvas.clientWidth - parseFloat(padding.paddingLeft) - parseFloat(padding.paddingRight);
          setZoom(Math.max(0.5, Math.min(12, round(width / W))));
        }} title="Die Ansicht an die verfügbare Breite anpassen. Ändert nur den Zoom.">An Breite anpassen</button>
        <button className={`btn small ${detached ? "is-on" : ""}`} onClick={() => setDetached((v) => !v)}
          title="Die Einstellungen als schwebendes Fenster über der Legende öffnen. Das Blatt bleibt weiss.">
          {detached ? "Einstellungen andocken" : "Einstellungen lösen"}
        </button>
        <button className={`btn small ${windowed ? "is-on" : ""}`} onClick={() => setWindowed((v) => !v)}
          title="Die Legende gross über dem Programm öffnen. Das Blatt bleibt weiss.">
          {windowed ? "Fenster schliessen" : "Als Fenster"}
        </button>
        </div>
        <span style={{ flex: 1 }} />
        <span className={saveState === "error" ? "dirty" : saveState === "saving" ? "hint" : "saved"} role="status">
          {saveState === "saving" ? "Speichert …" : saveState === "error" ? "Nicht gespeichert" : savedInfo ? `Gespeichert ${savedInfo}` : ""}
        </span>
        <div className="tool-group" role="group" aria-label="Export">
        <button className="btn small primary" disabled={busy || exporting} onClick={() => exportFile("dxf", exportBlock, exportGeneral && Boolean(general?.kind))}
          title={exportBlock ? "Den in den Exportoptionen gewählten Abschnitt als DXF herunterladen" : "Die ganze Legende als DXF herunterladen"}>
          <Icon name="download" size={16} /> {exporting ? "Exportiert …" : "DXF herunterladen"}
        </button>
        </div>
      </div>

      <div className={`legend-body ${detached ? "detached" : ""}`}>
        <aside className="legend-outline">
          <div className="section" style={{ marginTop: 0 }}>
            Abschnitte
          </div>
          {general?.kind && (
            <button className={`outline-item ${sel?.type === "general" ? "active" : ""}`} style={{ paddingLeft: 6 }} onClick={() => setSel({ type: "general" })}>
              🔒 Allgemeinteil (gesperrt)
            </button>
          )}
          {doc.title.text.trim() && (
            <button className={`outline-item ${sel?.type === "title" ? "active" : ""}`} style={{ paddingLeft: 6 }} onClick={() => setSel({ type: "title" })} title={doc.title.text}>
              T Titel
            </button>
          )}
          {doc.blocks.map((b) => (
            <div key={b.id} className="outline-block">
              <div
                className={`outline-row ${sel?.type === "block" && sel.block === b.id ? "active" : ""} ${dropAt?.block === b.id && dropAt.before === null ? "drop-end" : ""}`}
                {...dropProps({ block: b.id, before: null })}
              >
                <button className="fold-btn" aria-label={b.collapsed ? "Aufklappen" : "Einklappen"} onClick={() => change(updateBlock(doc, b.id, { collapsed: !b.collapsed }))}>
                  {b.collapsed ? "▸" : "▾"}
                </button>
                <span className="swatch" style={{ background: b.style.header, width: 12, height: 12 }} />
                <button className="outline-title" onClick={() => setSel({ type: "block", block: b.id })} title={b.title}>
                  {b.title || "(ohne Überschrift)"} <span className="hint">{b.items.filter((it) => !it.hidden).length}</span>
                </button>
              </div>
              {!b.collapsed &&
                b.items.map((it) => (
                  <button
                    key={it.id}
                    className={`outline-item ${sel?.type === "item" && sel.item === it.id ? "active" : ""} ${it.hidden ? "hidden-entry" : ""} ${dropAt?.block === b.id && dropAt.before === it.id ? "drop-before" : ""}`}
                    onClick={() => setSel({ type: "item", block: b.id, item: it.id })}
                    title={`${it.text} · ziehen zum Verschieben`}
                    {...dragProps({ type: "move", block: b.id, item: it.id })}
                    {...dropProps({ block: b.id, before: it.id })}
                  >
                    {it.kind === "symbol" && it.symbol_key ? <SymIcon r={symbols[symbolRequestKey({ symbol_key: it.symbol_key, length_mm: null, width_mm: null })]} /> : null}
                    {it.kind === "line" ? "― " : it.kind === "note" ? "◐ " : it.kind === "text" ? "¶ " : ""}
                    {it.text || "(ohne Text)"}
                    {it.hidden && <span className="badge">im Allgemeinteil</span>}
                    {dups.has(it.id) && <span className="badge warn">doppelt</span>}
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
              <p className="hint">Anklicken oder auf einen Abschnitt ziehen.</p>
              {missing.slice(0, 40).map((r) => {
                const text = describe(r.family_key, r.title, descriptions);
                return (
                  <button
                    key={r.family_key}
                    className="outline-item add"
                    onClick={() => addRows([r])}
                    title={`${text} hinzufügen`}
                    {...dragProps({ type: "add", family_key: r.family_key, symbol_key: r.symbol_key, text, categories: r.categories })}
                  >
                    <SymIcon r={symbols[symbolRequestKey({ symbol_key: r.symbol_key, length_mm: null, width_mm: null })]} />
                    {text} <span className="hint">{r.total}×</span>
                  </button>
                );
              })}
              <button className="btn small" style={{ marginTop: 6 }} onClick={() => addRows(missing)}>
                Alle hinzufügen
              </button>
            </>
          )}

          {inGeneralRows.length > 0 && (
            <>
              <div className="section">Im Allgemeinteil ({inGeneralRows.length})</div>
              <p className="hint">Der Allgemeinteil zeigt diese Apparate schon. Sie kommen nicht in den Vorschlag. Ziehen geht trotzdem.</p>
              {inGeneralRows.map((r) => {
                const text = describe(r.family_key, r.title, descriptions);
                return (
                  <div
                    key={r.family_key}
                    className="outline-item hidden-entry"
                    title="im Allgemeinteil"
                    {...dragProps({ type: "add", family_key: r.family_key, symbol_key: r.symbol_key, text, categories: r.categories })}
                  >
                    <SymIcon r={symbols[symbolRequestKey({ symbol_key: r.symbol_key, length_mm: null, width_mm: null })]} />
                    {text} <span className="badge">im Allgemeinteil</span>
                  </div>
                );
              })}
            </>
          )}

          <div className="section">Aus der Bibliothek</div>
          <input className="input" style={{ width: "100%" }} placeholder="Name oder Katalogcode" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Bibliothek durchsuchen" />
          {results.map((f) => {
            const fam = f.key;
            const text = describe(fam, f.title, descriptions);
            const twice = inLegend(doc, fam, f.representative.key);
            return (
              <button
                key={f.id}
                className="outline-item add"
                onClick={() => addFromLibrary(f)}
                title={twice ? `${f.title} · schon in der Legende` : f.title}
                {...dragProps({ type: "add", family_key: fam, symbol_key: f.representative.key, text, categories: f.categories })}
              >
                <SymIcon r={symbols[symbolRequestKey({ symbol_key: f.representative.key, length_mm: null, width_mm: null })]} />
                {text} <span className="hint">{f.representative.item}</span>
                {twice && <span className="badge warn">doppelt</span>}
              </button>
            );
          })}
        </aside>

        <div
          ref={canvasRef}
          className="legend-canvas"
          onClick={() => !justDragged.current && setSel({ type: "legend" })}
          onDragOver={(e) => {
            if (!dragPayload.current) return;
            e.preventDefault();
            const t = sheetTargetAt(e.clientX, e.clientY);
            if (t?.block !== dropAt?.block || t?.before !== dropAt?.before) setDropAt(t);
          }}
          onDragLeave={(e) => {
            if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node)) setDropAt(null);
          }}
          onDrop={(e) => {
            e.preventDefault();
            drop(dragPayload.current, sheetTargetAt(e.clientX, e.clientY));
            dragPayload.current = null;
          }}
        >
          <svg
            className="legend-paper"
            viewBox={`0 0 ${W} ${H}`}
            width={W * zoom}
            height={H * zoom}
            style={{ fontFamily: `${style.font}, Arial, sans-serif` }}
            aria-label={`Legende, ${W} × ${H} mm`}
          >
            <rect width={W} height={H} fill="#fff" />
            {/* section backgrounds, then the grid above the paper, then everything else */}
            {(placed?.prims ?? [])
              .filter((p) => p.t === "rect" && p.role === "background")
              .map((p, i) => (
                <Prim key={`bg${i}`} p={p} symbols={symbols} general={general} sel={sel} stale={stale} dups={dups} onSelect={setSel} />
              ))}
            {showGrid && (placed?.prims ?? []).filter((p) => p.t === "grid").map((g) => <GridLines key={`g${g.block}`} g={g} />)}
            {(placed?.prims ?? [])
              .filter((p) => !(p.t === "rect" && p.role === "background") && p.t !== "grid")
              .map((p, i) => (
                <Prim key={i} p={p} symbols={symbols} general={general} sel={sel} stale={stale} dups={dups} onSelect={setSel} onDragStart={startSheetDrag} />
              ))}
            {dropAt && placed && <DropMarker placed={placed} target={dropAt} doc={doc} />}
          </svg>
        </div>

        <aside className={`legend-props ${detached ? "floating" : ""}`}>
          {sel?.type === "general" ? (
            <GeneralProps general={general} company={info.company} />
          ) : sel?.type === "title" ? (
            <TitleProps doc={doc} field={field} change={change} />
          ) : selItem && selBlock ? (
            <ItemProps
              item={selItem}
              block={selBlock}
              doc={doc}
              render={selItem.kind === "symbol" ? symbols[symbolRequestKey(selItem)] : undefined}
              stale={stale.has(selItem.id)}
              duplicate={dups.has(selItem.id)}
              onRotate={() => change(rotateItem(doc, selBlock.id, selItem.id))}
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
              exporting={exporting}
              onExport={exportFile}
            />
          )}
        </aside>
      </div>
    </div>
    </>
  );
}

// -- sheet primitives -----------------------------------------------------------------------

function Prim({
  p,
  symbols,
  general,
  sel,
  stale,
  dups,
  onSelect,
  onDragStart,
  inert,
}: {
  p: LegendPrim;
  symbols: Record<string, SymbolRender>;
  general: (GeneralInfo & { svg: string; prims: LegendPrim[] }) | null;
  sel: Selection | { type: "general" };
  stale: Set<string>;
  dups?: Set<string>;
  onSelect: (s: Selection | { type: "general" }) => void;
  onDragStart?: (e: ReactPointerEvent, block: string, item: string) => void;
  inert?: boolean;
}) {
  switch (p.t) {
    case "rect":
      if (p.role === "general") {
        if (general?.kind === "dxf" && general.svg)
          return <image x={p.x} y={p.y} width={p.w} height={p.h} href={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(general.svg)}`} preserveAspectRatio="xMinYMin meet" />;
        if (general?.kind === "project")
          return (
            <g transform={`translate(${p.x} ${p.y}) scale(${p.fit ?? 1})`}>
              {general.prims.map((q, i) => (
                <Prim key={i} p={q} symbols={symbols} general={null} sel={null} stale={new Set()} onSelect={() => undefined} inert />
              ))}
            </g>
          );
        return <rect x={p.x} y={p.y} width={p.w} height={p.h} fill="#f5f5f5" stroke="#bbb" strokeWidth={0.2} strokeDasharray="1 1" />;
      }
      return <rect x={p.x} y={p.y} width={p.w} height={p.h} fill={p.fill ?? "none"} stroke={p.stroke ?? "none"} strokeWidth={p.stroke ? 0.25 : 0} pointerEvents="none" />;
    case "text":
      return (
        <text x={p.x} y={p.y} fontSize={p.size} fontWeight={p.bold ? 700 : 400} fill={p.color} pointerEvents="none">
          {p.text}
        </text>
      );
    case "line":
      return <line x1={p.x1} y1={p.y1} x2={p.x2} y2={p.y2} stroke={p.color} strokeWidth={0.35} strokeDasharray={DASH[p.style as LineStyle] || undefined} strokeLinecap="round" pointerEvents="none" />;
    case "half":
      return (
        <g pointerEvents="none">
          <circle cx={p.cx} cy={p.cy} r={p.r} fill="none" stroke={p.color} strokeWidth={0.18} />
          <path d={`M${p.cx} ${p.cy - p.r} A${p.r} ${p.r} 0 0 1 ${p.cx} ${p.cy + p.r} Z`} fill={p.color} />
        </g>
      );
    case "symbol": {
      const r = symbols[symbolRequestKey({ symbol_key: p.key, length_mm: p.length_mm, width_mm: p.width_mm })];
      if (!r?.svg || !r.box)
        return (
          <g pointerEvents="none">
            <rect x={p.x0 ?? p.cx - p.w / 2} y={p.y0 ?? p.cy - p.h / 2} width={p.w} height={p.h} fill="none" stroke="#999" strokeWidth={0.15} strokeDasharray="0.6 0.4" />
            <title>{r ? "Keine Symbolvorschau verfügbar" : "lädt …"}</title>
          </g>
        );
      // The drawing keeps its own colours. Its insertion point (ax, ay; Nova y up) sits on the
      // symbol axis; turned around that point, counter-clockwise like the DXF.
      const ax = p.ax ?? r.box[0] + r.box[2] / 2;
      const ay = p.ay ?? -(r.box[1] + r.box[3] / 2);
      return (
        <g
          transform={`translate(${p.cx} ${p.cy}) rotate(${-(p.rot || 0)}) scale(${p.scale}) translate(${-ax} ${ay})`}
          pointerEvents="none"
          dangerouslySetInnerHTML={{ __html: innerSvg(r.svg) }}
        />
      );
    }
    case "hit": {
      if (inert) return null;
      const selected =
        (p.kind === "item" && sel?.type === "item" && sel.item === p.id) ||
        (p.kind === "block" && sel?.type === "block" && sel.block === p.id) ||
        (p.kind === "general" && sel?.type === "general") ||
        (p.kind === "title" && sel?.type === "title");
      const isStale = p.kind === "item" && stale.has(p.id);
      const isDup = p.kind === "item" && Boolean(dups?.has(p.id));
      if (p.kind === "section")
        return (
          <rect
            x={p.x}
            y={p.y}
            width={p.w}
            height={p.h}
            fill="transparent"
            data-hit="section"
            data-block={p.block}
            onClick={(e) => {
              e.stopPropagation();
              onSelect({ type: "block", block: p.block });
            }}
          />
        );
      return (
        <rect
          x={p.x}
          y={p.y}
          width={p.w}
          height={p.h}
          fill={selected ? "rgba(11,107,203,0.10)" : "transparent"}
          stroke={selected ? "#0b6bcb" : isDup ? "#e8590c" : isStale ? "#c92a2a" : "none"}
          strokeWidth={0.3}
          strokeDasharray={(isStale || isDup) && !selected ? "0.8 0.5" : undefined}
          className="lg-hit"
          data-hit={p.kind}
          data-block={p.block ?? undefined}
          data-id={p.id}
          onPointerDown={p.kind === "item" && onDragStart ? (e) => onDragStart(e, p.block, p.id) : undefined}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(
              p.kind === "item"
                ? { type: "item", block: p.block, item: p.id }
                : p.kind === "block"
                  ? { type: "block", block: p.block }
                  : p.kind === "title"
                    ? { type: "title" }
                    : { type: "general" },
            );
          }}
        >
          <title>
            {p.kind === "general"
              ? "Allgemeinteil (gesperrt)"
              : isDup
                ? "doppelt: Dieses Symbol steht schon weiter oben in der Legende"
                : isStale
                  ? "Kommt in den aktuellen Importen nicht vor"
                  : p.kind === "item"
                    ? "Anklicken zum Bearbeiten, ziehen zum Verschieben"
                    : "Anklicken zum Bearbeiten"}
          </title>
        </rect>
      );
    }
    default:
      return null;
  }
}

/** Grid of one section: the placeholders the entries sit in (rows in the chosen step,
 *  column edges, symbol axis and text line of every column). From the layout, so the
 *  lines match the entries exactly. */
function GridLines({ g }: { g: LegendPrim }) {
  const rows: number[] = [];
  for (let y = g.y; y <= g.y + g.h + 1e-6; y += g.row) rows.push(y);
  const cols = Array.from({ length: g.cols }, (_, c) => g.x + c * g.colw);
  return (
    <g className="lg-grid" stroke="#5b87b5" strokeOpacity={0.45} strokeWidth={0.07} pointerEvents="none" data-step={g.row}>
      {rows.map((y) => (
        <line key={`y${y}`} x1={g.x} y1={y} x2={g.x + g.w} y2={y} />
      ))}
      {[...cols, g.x + g.w].map((x) => (
        <line key={`c${x}`} x1={x} y1={g.y} x2={x} y2={g.y + g.h} />
      ))}
      {cols.map((x) => (
        <g key={`a${x}`} strokeDasharray="0.6 0.6">
          <line x1={x + g.axis} y1={g.y} x2={x + g.axis} y2={g.y + g.h} />
          <line x1={x + g.text} y1={g.y} x2={x + g.text} y2={g.y + g.h} />
        </g>
      ))}
    </g>
  );
}

/** Blue line where a dragged entry will land. */
function DropMarker({ placed, target, doc }: { placed: LegendLayout; target: DropTarget; doc: LegendDoc }) {
  const hits = placed.prims.filter((p) => p.t === "hit");
  let x = 0;
  let y = 0;
  let w = 0;
  const before = target.before ? hits.find((h) => h.kind === "item" && h.id === target.before) : null;
  if (before) {
    [x, y, w] = [before.x, before.y, before.w];
  } else {
    const items = doc.blocks.find((b) => b.id === target.block)?.items.filter((it) => !it.hidden) ?? [];
    const last = items.length ? hits.find((h) => h.kind === "item" && h.id === items[items.length - 1].id) : null;
    const section = hits.find((h) => h.kind === "section" && h.block === target.block);
    if (last) [x, y, w] = [last.x, last.y + last.h, last.w];
    else if (section) [x, y, w] = [section.x, section.y + section.h - 1, section.w];
    else return null;
  }
  return <line x1={x} y1={y} x2={x + w} y2={y} stroke="#0b6bcb" strokeWidth={0.6} pointerEvents="none" />;
}

/** Small symbol icon for the lists on the left: the same drawing as on the sheet. */
function SymIcon({ r }: { r?: SymbolRender }) {
  if (!r?.svg || !r.box) return <span className="sym-icon empty" aria-hidden />;
  return <svg className="sym-icon" viewBox={r.box.join(" ")} aria-hidden dangerouslySetInnerHTML={{ __html: innerSvg(r.svg) }} />;
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
function NumberInput({
  value,
  step,
  placeholder,
  label,
  min,
  max,
  onCommit,
}: {
  value: number | null;
  step: number;
  placeholder?: string;
  label?: string;
  min?: number;
  max?: number;
  onCommit: (v: number) => void;
}) {
  const [text, setText] = useState(value == null ? "" : String(value));
  useEffect(() => setText(value == null ? "" : String(value)), [value]);
  const done = () => {
    const raw = Number(text.replace(",", "."));
    if (text.trim() === "" || !Number.isFinite(raw)) {
      setText(value == null ? "" : String(value));
      return;
    }
    const v = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, raw));
    setText(String(v)); // show the value that applies, e.g. 210 after typing 250
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
  duplicate,
  onRotate,
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
  duplicate: boolean;
  onRotate: () => void;
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
      {duplicate && <p className="warn-text">doppelt: Dieses Symbol steht schon weiter oben in der Legende.</p>}
      {item.hidden && (
        <div className="info-line company">
          Ausgeblendet: Der Allgemeinteil zeigt diesen Apparat schon. Der Eintrag ist nicht gelöscht.{" "}
          <button className="btn small" onClick={() => set({ hidden: false, keep: true })}>
            Wieder zeigen
          </button>
        </div>
      )}
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
      <div className="form two">
        <label className="field">
          <span>Textgrösse (Faktor)</span>
          <NumberInput label="Textgrösse Faktor" value={item.text_scale ?? 1} step={0.1} onCommit={(v) => set({ text_scale: Math.max(0.5, Math.min(3, v)) })} />
        </label>
        {item.kind === "symbol" && (
          <label className="field">
            <span>Symbolgrösse (Faktor)</span>
            <NumberInput label="Symbolgrösse Faktor" value={item.symbol_factor ?? 1} step={0.1} onCommit={(v) => set({ symbol_factor: Math.max(0.3, Math.min(4, v)) })} />
          </label>
        )}
        {item.kind === "symbol" && (
          <div className="field">
            <span>Drehung {item.rotation || 0}°</span>
            <button className="btn small" onClick={onRotate} title="Symbol um 90 Grad um seinen Mittelpunkt drehen. Der Text bleibt waagrecht.">
              ↻ 90° drehen
            </button>
          </div>
        )}
      </div>
      <p className="hint">
        Faktor 1 = gemeinsame Schriftgrösse bzw. gemeinsamer Symbolmassstab. 1,2 macht nur diesen Eintrag grösser, die Zeile wächst um ganze Rasterzeilen.
      </p>
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
  ["text", "Text"],
  ["symbol", "Linien und Hinweise"],
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
      <p className="hint">Symbole behalten die Farben aus der Nova-Zeichnung.</p>
      <div className="color-grid">
        <label className="color-field">
          <input type="checkbox" checked={block.style.background_on} onChange={(e) => setStyle({ background_on: e.target.checked })} aria-label="Hintergrundfarbe an" />
          <input type="color" value={block.style.background} onChange={(e) => setStyle({ background: e.target.value })} aria-label="Hintergrundfarbe" />
          <span>Hintergrundfarbe</span>
        </label>
        <label className="color-field">
          <input type="checkbox" checked={block.style.border_on} onChange={(e) => setStyle({ border_on: e.target.checked })} aria-label="Umrandung an" />
          <input type="color" value={block.style.border} onChange={(e) => setStyle({ border: e.target.value })} aria-label="Farbe Umrandung" />
          <span>Umrandung</span>
        </label>
      </div>
      <label className="field" style={{ marginTop: 6 }}>
        <span>Textgrösse Überschrift (Faktor)</span>
        <NumberInput value={block.title_scale ?? 1} step={0.1} onCommit={(v) => change(updateBlock(doc, block.id, { title_scale: Math.max(0.5, Math.min(3, v)) }))} />
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

function TitleProps({ doc, field, change }: { doc: LegendDoc; field: FieldFn; change: (d: LegendDoc) => void }) {
  const t = doc.title;
  const set = (patch: Partial<LegendDoc["title"]>) => change({ ...doc, title: { ...t, ...patch } });
  const mm = t.size_mm > 0 ? t.size_mm : Math.round(doc.style.text_size * (t.scale ?? 1) * 100) / 100;
  return (
    <>
      <h4>Titel</h4>
      <label className="field">
        <span>Text</span>
        <input className="input" value={t.text} {...field((d, v) => ({ ...d, title: { ...d.title, text: v } }))} />
      </label>
      <label className="field">
        <span>Textgrösse (mm)</span>
        <NumberInput label="Textgrösse Titel" value={mm} step={0.25} onCommit={(v) => {
          const size = Math.max(1, Math.min(20, v));
          const base = doc.style.text_size || 1;
          set({ size_mm: size, scale: Math.max(0.5, Math.min(3, Math.round((size / base) * 100) / 100)) });
        }} />
      </label>
      <label className="field">
        <span>Schriftart</span>
        <select className="select" aria-label="Schriftart Titel" value={t.font || "Arial"} onChange={(e) => set({ font: e.target.value })}>
          <option value="Arial">Arial</option>
          <option value="Calibri">Calibri</option>
          <option value="Verdana">Verdana</option>
        </select>
      </label>
      <p className="hint">Titelgrösse, Farbe und Schriftart gelten nur für den Titel, nicht für die Einträge.</p>
      <div className="color-grid">
        <label className="color-field">
          <input type="color" value={t.color || "#000000"} onChange={(e) => set({ color: e.target.value })} aria-label="Farbe Titel" />
          <span>Schrift</span>
        </label>
        <label className="color-field">
          <input type="checkbox" checked={Boolean(t.border_on)} onChange={(e) => set({ border_on: e.target.checked })} aria-label="Umrandung Titel an" />
          <input type="color" value={t.border || "#000000"} onChange={(e) => set({ border: e.target.value })} aria-label="Farbe Umrandung Titel" />
          <span>Umrandung</span>
        </label>
      </div>
    </>
  );
}

function GeneralProps({ general, company }: { general: (GeneralInfo & { svg: string }) | null; company: LegendInfo["company"] }) {
  return (
    <>
      <h4>Allgemeinteil (gesperrt)</h4>
      <p className="hint">Steht in jeder Legende zuoberst.</p>
      <p className="hint">Verknüpft ist eine DXF- oder DWG-Datei auf dem Server.</p>
      <p className="hint">Die Datei wird nur an die Blattbreite angepasst.</p>
      <p className="hint">Kachelgrösse, Schrift und Abstand gelten für die erzeugten Einträge, nicht für diese Zeichnung.</p>
      <p className="hint">Einträge darin lassen sich nicht ziehen. N4D wird für diese Verknüpfung nicht gelesen.</p>
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
  exporting,
  onExport,
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
  exporting: boolean;
  onExport: (format: "dxf" | "dwg", block: string, withGeneral: boolean) => void;
}) {
  const s = doc.style;
  const company = info.company;
  return (
    <>
      <h4>Legende</h4>
      <p className="hint">Klicke auf einen Eintrag oder eine Kopfleiste, um sie zu bearbeiten. Einträge ziehst du mit der Maus an einen anderen Platz, ↑ ↓ geht auch.</p>
      <label className="field">
        <span>Titel</span>
        <input className="input" value={doc.title.text} {...field((d, v) => ({ ...d, title: { ...d.title, text: v } }))} />
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
          <span>Abstand zwischen Abschnitten (mm)</span>
          <NumberInput label="Abstand zwischen Abschnitten" value={s.section_gap ?? 0} step={0.5} onCommit={(v) => setStyle({ section_gap: Math.max(0, Math.min(50, v)) })} />
        </label>
        <label className="field">
          <span>Abstand zwischen den Kacheln (mm)</span>
          <NumberInput label="Abstand zwischen den Kacheln" value={s.entry_gap ?? 0} step={0.5} onCommit={(v) => setStyle({ entry_gap: Math.max(0, Math.min(20, v)) })} />
        </label>
        <label className="field">
          <span>Textzeilen</span>
          <select className="select" aria-label="Textzeilen" value={String(s.text_lines ?? 0)} onChange={(e) => setStyle({ text_lines: Number(e.target.value) })}>
            <option value="0">Automatisch</option>
            <option value="1">1 Zeile, gleiche Höhe</option>
            <option value="2">2 Zeilen, gleiche Höhe</option>
            <option value="3">3 Zeilen, gleiche Höhe</option>
          </select>
        </label>
        <label className="field">
          <span>Blattbreite (mm)</span>
          <NumberInput label="Blattbreite" value={s.width} step={5} min={80} max={210} onCommit={(v) => setStyle({ width: v })} />
        </label>
      </div>
      <label className="toggle" style={{ color: "var(--fg)" }}>
        <input type="checkbox" checked={Boolean(s.strip_fill)} onChange={(e) => setStyle({ strip_fill: e.target.checked })} />
        Symbol-Hintergründe/Schraffuren entfernen
      </label>
      <p className="hint">
        Jede Symbolkachel ist {String(Math.round(s.text_size * 3.6 * s.symbol_scale * 10) / 10).replace(".", ",")} mm gross.
        Die Kante folgt der Schriftgrösse und dem Symbolmassstab. Langfeldleuchten behalten ihr Seitenverhältnis und füllen dieselbe Kachel.
        Der Abstand gilt zwischen den Kacheln. Bei «Automatisch» bleibt der Text auf einer Zeile.
      </p>
      <p className="hint">
        Blattbreite inkl. 5 mm Rand: Standard 200 mm, höchstens 210 mm. Gilt für alle Texte und Symbole dieses Projekts. Firmen-Standard: Schrift {String(company.text_size).replace(".", ",")} mm, Massstab{" "}
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

      <div className="color-grid">
        <label className="color-field">
          <input type="checkbox" checked={Boolean(s.frame_on)} onChange={(e) => setStyle({ frame_on: e.target.checked })} aria-label="Umrandung der Legende an" />
          <input type="color" value={s.frame || "#000000"} onChange={(e) => setStyle({ frame: e.target.value })} aria-label="Farbe Umrandung der Legende" />
          <span>Umrandung der ganzen Legende</span>
        </label>
      </div>
      <p className="hint">Titel anklicken: Textgrösse, Farbe und Umrandung des Titels.</p>

      <div className="section">Export</div>
      <label className="field">
        <span>Was exportieren</span>
        <select className="select" value={exportBlock} onChange={(e) => setExportBlock(e.target.value)}>
          <option value="">Ganze Legende</option>
          {doc.blocks.map((b) => (
            <option key={b.id} value={b.id}>
              Nur {b.title || "(ohne Überschrift)"}
            </option>
          ))}
        </select>
      </label>
      <label className="toggle" style={{ color: "var(--fg)" }}>
        <input
          type="checkbox"
          checked={exportGeneral && hasGeneral}
          onChange={(e) => {
            if (!hasGeneral) {
              notify("Es ist keine Servervorlage für den Allgemeinteil eingestellt. Der Export läuft ohne ihn.", true);
              return;
            }
            setExportGeneral(e.target.checked);
          }}
        />
        Allgemeinteil einschliessen
      </label>
      <p className="hint">
        Verknüpft ist eine DXF- oder DWG-Datei.
        <br />Schriftgrösse, Kachel und Abstand ändern nur die erzeugte Legende darunter.
        <br />Die Zeichnung bleibt gesperrt. Einträge darin lassen sich nicht ziehen.
        <br />N4D wird für diese Verknüpfung nicht gelesen.
      </p>
      <div className="row" style={{ marginTop: 6 }}>
        <button className="btn small" disabled={exporting} onClick={() => onExport("dxf", exportBlock, exportGeneral && hasGeneral)}>
          DXF exportieren
        </button>
        <button className="btn small" disabled={exporting} onClick={() => onExport("dwg", exportBlock, exportGeneral && hasGeneral)}>
          DWG exportieren
        </button>
      </div>
      <p className="hint">Der Export speichert zuerst die Legende. Dateiname: edeco ag-{"<Bezeichnung>"}-{"<Abschnitt>"}.dxf bzw. …-Legende.dxf.</p>
      <p className="hint">Die Datei entspricht der Vorschau: DXF R2013, Farben als Truecolor, jedes Symbol als Block. N4D wird nicht geschrieben. Das Blatt bleibt weiss, unabhängig vom Hell- oder Dunkelmodus.</p>
      {!info.oda && (
        <p className="hint">
          DWG braucht den ODA File Converter. DXF funktioniert ohne.{" "}
          <a href="https://www.opendesign.com/guestfiles/oda_file_converter" target="_blank" rel="noreferrer">ODA File Converter herunterladen</a>
        </p>
      )}
      <p className="hint">© 2026 edeco ag. Alle Rechte vorbehalten.</p>
      <button className="btn small" type="button" onClick={() => exportDiagnostic(projectId, notify)}>Prüfbericht exportieren</button>
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
