// Legend document and editing steps of the legend editor (Phase 4).
// Pure functions, so npm test checks them without a browser.

export type ItemKind = "symbol" | "line" | "note";
export type LineStyle = "solid" | "dashed" | "dotted" | "dashdot";

export interface LegendItem {
  id: string;
  kind: ItemKind;
  family_key: string | null;
  symbol_key: string | null;
  text: string;
  x: number; // symbol centre, relative to the block origin (mm)
  y: number;
  scale: number;
  text_size: number;
  length_mm: number | null; // parametric symbols: real length and width
  width_mm: number | null;
  line_style: LineStyle;
  line_length: number;
}

export interface LegendBlock {
  id: string;
  category_id: string | null;
  title: string;
  x: number;
  y: number;
  columns: number;
  spacing: number;
  heading_size: number;
  collapsed: boolean;
  items: LegendItem[];
}

export interface LegendText {
  id: string;
  text: string;
  x: number;
  y: number;
  size: number;
}

export interface LegendStyle {
  font: string;
  title_size: number;
  heading_size: number;
  text_size: number;
  row: number;
  text_offset: number;
  column_width: number;
  page_columns: number;
  page_height: number;
  margin: number;
  grid: number;
  plan_scale: number;
}

export interface LegendDoc {
  version: number;
  style: LegendStyle;
  title: { text: string; x: number; y: number; size: number };
  blocks: LegendBlock[];
  texts: LegendText[];
}

export type Selection =
  | { type: "item"; block: string; item: string }
  | { type: "block"; block: string }
  | { type: "text"; id: string }
  | { type: "title" }
  | null;

// -- undo / redo ---------------------------------------------------------------

export interface History<T> {
  past: T[];
  present: T;
  future: T[];
}

const LIMIT = 100;

export function historyOf<T>(present: T): History<T> {
  return { past: [], present, future: [] };
}

/** A finished change: the old state goes to the undo list. */
export function push<T>(h: History<T>, next: T): History<T> {
  if (next === h.present) return h;
  return { past: [...h.past, h.present].slice(-LIMIT), present: next, future: [] };
}

/** Live change while dragging: no undo step yet. */
export function replace<T>(h: History<T>, next: T): History<T> {
  return { ...h, present: next };
}

/** End of a drag: one undo step back to the state before the drag. */
export function commit<T>(h: History<T>, before: T): History<T> {
  if (before === h.present) return h;
  return { past: [...h.past, before].slice(-LIMIT), present: h.present, future: [] };
}

export function undo<T>(h: History<T>): History<T> {
  if (!h.past.length) return h;
  return { past: h.past.slice(0, -1), present: h.past[h.past.length - 1], future: [h.present, ...h.future] };
}

export function redo<T>(h: History<T>): History<T> {
  if (!h.future.length) return h;
  return { past: [...h.past, h.present], present: h.future[0], future: h.future.slice(1) };
}

// -- geometry helpers ------------------------------------------------------------

export function snap(value: number, grid: number, enabled = true): number {
  if (!enabled || !grid || grid <= 0) return Math.round(value * 1000) / 1000;
  return Math.round(Math.round(value / grid) * grid * 1000) / 1000;
}

/** Paper size in mm: legend columns side by side, height from the content. */
export function paperSize(doc: LegendDoc): { width: number; height: number } {
  const s = doc.style;
  let right = s.margin * 2 + s.column_width * s.page_columns;
  let bottom = s.page_height;
  for (const b of doc.blocks) {
    const rows = Math.ceil(b.items.length / Math.max(1, b.columns));
    bottom = Math.max(bottom, b.y + b.heading_size * 1.8 + rows * b.spacing + s.margin);
    for (const it of b.items) {
      right = Math.max(right, b.x + it.x + s.column_width / Math.max(1, b.columns));
      bottom = Math.max(bottom, b.y + it.y + s.margin);
    }
    right = Math.max(right, b.x + s.column_width + s.margin);
  }
  for (const t of doc.texts) {
    right = Math.max(right, t.x + t.text.length * t.size * 0.6 + s.margin);
    bottom = Math.max(bottom, t.y + s.margin);
  }
  return { width: Math.ceil(right), height: Math.ceil(bottom) };
}

// -- editing steps (each returns a new document) ----------------------------------

function mapBlock(doc: LegendDoc, id: string, fn: (b: LegendBlock) => LegendBlock): LegendDoc {
  return { ...doc, blocks: doc.blocks.map((b) => (b.id === id ? fn(b) : b)) };
}

export function updateItem(doc: LegendDoc, blockId: string, itemId: string, patch: Partial<LegendItem>): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({
    ...b,
    items: b.items.map((it) => (it.id === itemId ? { ...it, ...patch } : it)),
  }));
}

export function removeItem(doc: LegendDoc, blockId: string, itemId: string): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({ ...b, items: b.items.filter((it) => it.id !== itemId) }));
}

export function updateBlock(doc: LegendDoc, blockId: string, patch: Partial<LegendBlock>): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({ ...b, ...patch }));
}

export function removeBlock(doc: LegendDoc, blockId: string): LegendDoc {
  return { ...doc, blocks: doc.blocks.filter((b) => b.id !== blockId) };
}

export function moveBlockInOrder(doc: LegendDoc, blockId: string, delta: number): LegendDoc {
  const blocks = [...doc.blocks];
  const i = blocks.findIndex((b) => b.id === blockId);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= blocks.length) return doc;
  [blocks[i], blocks[j]] = [blocks[j], blocks[i]];
  return { ...doc, blocks };
}

/** Move an entry to another block, keeping its place on paper. */
export function moveItemToBlock(doc: LegendDoc, fromId: string, itemId: string, toId: string): LegendDoc {
  const from = doc.blocks.find((b) => b.id === fromId);
  const to = doc.blocks.find((b) => b.id === toId);
  const item = from?.items.find((it) => it.id === itemId);
  if (!from || !to || !item || fromId === toId) return doc;
  const moved = { ...item, x: item.x + from.x - to.x, y: item.y + from.y - to.y };
  return {
    ...doc,
    blocks: doc.blocks.map((b) =>
      b.id === fromId
        ? { ...b, items: b.items.filter((it) => it.id !== itemId) }
        : b.id === toId
          ? { ...b, items: [...b.items, moved] }
          : b,
    ),
  };
}

/** Next free row below the last entry of a block. */
export function nextSlot(block: LegendBlock, style: LegendStyle): { x: number; y: number } {
  if (!block.items.length) return { x: style.text_offset * 0.35, y: block.heading_size * 1.8 + block.spacing / 2 };
  const last = block.items.reduce((a, b) => (b.y > a.y || (b.y === a.y && b.x > a.x) ? b : a));
  const first = block.items.reduce((a, b) => (b.x < a.x ? b : a));
  return { x: first.x, y: Math.round((last.y + block.spacing) * 1000) / 1000 };
}

let counter = 0;
export function newId(): string {
  counter += 1;
  return `n${Date.now().toString(36)}${counter.toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export function makeItem(style: LegendStyle, patch: Partial<LegendItem>): LegendItem {
  return {
    id: newId(),
    kind: "symbol",
    family_key: null,
    symbol_key: null,
    text: "",
    x: 0,
    y: 0,
    scale: 1,
    text_size: style.text_size,
    length_mm: null,
    width_mm: null,
    line_style: "solid",
    line_length: 8,
    ...patch,
  };
}

export function addItem(doc: LegendDoc, blockId: string, patch: Partial<LegendItem>): { doc: LegendDoc; id: string } {
  const block = doc.blocks.find((b) => b.id === blockId);
  if (!block) return { doc, id: "" };
  const item = makeItem(doc.style, { ...nextSlot(block, doc.style), ...patch });
  return { doc: mapBlock(doc, blockId, (b) => ({ ...b, items: [...b.items, item] })), id: item.id };
}

export function addBlock(doc: LegendDoc, title: string, categoryId: string | null = null): { doc: LegendDoc; id: string } {
  const s = doc.style;
  const bottom = doc.blocks.reduce(
    (y, b) => Math.max(y, b.y + b.heading_size * 1.8 + Math.ceil(b.items.length / b.columns) * b.spacing + b.spacing),
    s.margin + doc.title.size * 2.2,
  );
  const block: LegendBlock = {
    id: newId(),
    category_id: categoryId,
    title,
    x: s.margin,
    y: Math.round(bottom * 1000) / 1000,
    columns: 1,
    spacing: s.row,
    heading_size: s.heading_size,
    collapsed: false,
    items: [],
  };
  return { doc: { ...doc, blocks: [...doc.blocks, block] }, id: block.id };
}

// -- comparison with the project ------------------------------------------------

export interface RowLike {
  family_key: string;
  symbol_key?: string;
  title: string;
  total: number;
  categories: string[];
}

/** Apparatus in use in the project that the legend does not show yet. */
export function missingRows<T extends RowLike>(doc: LegendDoc, rows: T[]): T[] {
  const shown = new Set(doc.blocks.flatMap((b) => b.items.map((it) => it.family_key)).filter(Boolean));
  return rows.filter((r) => r.total > 0 && !shown.has(r.family_key));
}

/** Legend entries whose apparatus no longer occurs in the current imports. */
export function staleItems(doc: LegendDoc, rows: RowLike[]): Set<string> {
  const used = new Set(rows.filter((r) => r.total > 0).map((r) => r.family_key));
  const out = new Set<string>();
  for (const b of doc.blocks)
    for (const it of b.items) if (it.kind === "symbol" && it.family_key && !used.has(it.family_key)) out.add(it.id);
  return out;
}

/** Block for a new entry: the one of its category, else the selected or first block. */
export function blockForCategory(doc: LegendDoc, categories: string[], fallback: string | null): string | null {
  for (const c of categories) {
    const b = doc.blocks.find((x) => x.category_id === c);
    if (b) return b.id;
  }
  return fallback ?? doc.blocks[0]?.id ?? null;
}

export function symbolRequestKey(it: Pick<LegendItem, "symbol_key" | "length_mm" | "width_mm">): string {
  return `${it.symbol_key}|${it.length_mm ?? ""}|${it.width_mm ?? ""}`;
}

/** Symbol size without the 12 % padding the rendered SVG adds on every side. */
export function drawingSize(box: [number, number, number, number]): { w: number; h: number } {
  const m = Math.max(box[2], box[3]) / 1.24;
  return { w: Math.max(0, box[2] - 0.24 * m), h: Math.max(0, box[3] - 0.24 * m) };
}

/** Same rule as the backend proposal: shrink large symbols to their row, never enlarge. */
export function fitScale(w: number, h: number, spacing: number, textOffset: number): number {
  if (w <= 0 || h <= 0) return 1;
  const limit = Math.min(1, (spacing * 1.1) / h, ((textOffset - 1.5) * 2) / w);
  return Math.max(0.05, Math.floor(limit * 20 + 1e-9) / 20);
}
