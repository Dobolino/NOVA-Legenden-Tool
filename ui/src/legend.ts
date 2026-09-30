// Legend document (version 2) and editing steps of the legend editor.
// No free coordinates: the backend places everything on a fixed grid.
// Pure functions, so npm test checks them without a browser.

export type ItemKind = "symbol" | "line" | "note" | "text";
export type LineStyle = "solid" | "dashed" | "dotted" | "dashdot";

export interface LegendItem {
  id: string;
  kind: ItemKind;
  family_key: string | null;
  symbol_key: string | null;
  text: string;
  length_mm: number | null; // parametric luminaires: real length and width
  width_mm: number | null;
  line_style: LineStyle;
  line_length: number;
}

export interface SectionStyle {
  header: string;
  header_text: string;
  background: string;
  border_on: boolean;
  border: string;
  symbol: string;
  text: string;
  padding: number;
}

export interface LegendBlock {
  id: string;
  category_id: string | null;
  title: string;
  layer: string;
  collapsed: boolean;
  style: SectionStyle;
  items: LegendItem[];
}

export interface LegendStyle {
  font: string;
  text_size: number;
  symbol_scale: number;
  grid: string;
  row: number;
  text_offset: number;
  columns: number;
  width: number;
  margin: number;
  plan_scale: number;
}

export interface LegendDoc {
  version: number;
  style: LegendStyle;
  title: { text: string };
  blocks: LegendBlock[];
}

export type Selection = { type: "item"; block: string; item: string } | { type: "block"; block: string } | { type: "legend" } | null;

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

/** Live change while typing: no undo step yet. */
export function replace<T>(h: History<T>, next: T): History<T> {
  return { ...h, present: next };
}

/** End of typing in a field: one undo step back to the state before. */
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

// -- saving: a slow answer must not win over a newer save ----------------------------

export interface SaveGate {
  generation: number;
}

/** Start a save; returns its generation. */
export function beginSave(gate: SaveGate): number {
  gate.generation += 1;
  return gate.generation;
}

/** True if the answer of this save is still the newest one. */
export function isCurrentSave(gate: SaveGate, generation: number): boolean {
  return gate.generation === generation;
}

// -- editing steps (each returns a new document) ----------------------------------

function mapBlock(doc: LegendDoc, id: string, fn: (b: LegendBlock) => LegendBlock): LegendDoc {
  return { ...doc, blocks: doc.blocks.map((b) => (b.id === id ? fn(b) : b)) };
}

export function updateItem(doc: LegendDoc, blockId: string, itemId: string, patch: Partial<LegendItem>): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({ ...b, items: b.items.map((it) => (it.id === itemId ? { ...it, ...patch } : it)) }));
}

export function removeItem(doc: LegendDoc, blockId: string, itemId: string): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({ ...b, items: b.items.filter((it) => it.id !== itemId) }));
}

export function updateBlock(doc: LegendDoc, blockId: string, patch: Partial<LegendBlock>): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({ ...b, ...patch }));
}

export function updateSectionStyle(doc: LegendDoc, blockId: string, patch: Partial<SectionStyle>): LegendDoc {
  return mapBlock(doc, blockId, (b) => ({ ...b, style: { ...b.style, ...patch } }));
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

/** Move an entry one place up or down; at the edge it goes to the neighbouring section. */
export function moveItemInOrder(doc: LegendDoc, blockId: string, itemId: string, delta: number): { doc: LegendDoc; block: string } {
  const bi = doc.blocks.findIndex((b) => b.id === blockId);
  if (bi < 0) return { doc, block: blockId };
  const items = [...doc.blocks[bi].items];
  const i = items.findIndex((it) => it.id === itemId);
  if (i < 0) return { doc, block: blockId };
  const j = i + delta;
  if (j >= 0 && j < items.length) {
    [items[i], items[j]] = [items[j], items[i]];
    return { doc: mapBlock(doc, blockId, (b) => ({ ...b, items })), block: blockId };
  }
  const nb = doc.blocks[bi + (delta < 0 ? -1 : 1)];
  if (!nb) return { doc, block: blockId };
  return { doc: moveItemToBlock(doc, blockId, itemId, nb.id, delta < 0 ? "end" : "start"), block: nb.id };
}

export function moveItemToBlock(doc: LegendDoc, fromId: string, itemId: string, toId: string, where: "start" | "end" = "end"): LegendDoc {
  const item = doc.blocks.find((b) => b.id === fromId)?.items.find((it) => it.id === itemId);
  if (!item || fromId === toId || !doc.blocks.some((b) => b.id === toId)) return doc;
  return {
    ...doc,
    blocks: doc.blocks.map((b) =>
      b.id === fromId
        ? { ...b, items: b.items.filter((it) => it.id !== itemId) }
        : b.id === toId
          ? { ...b, items: where === "start" ? [item, ...b.items] : [...b.items, item] }
          : b,
    ),
  };
}

let counter = 0;
export function newId(): string {
  counter += 1;
  return `n${Date.now().toString(36)}${counter.toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export function makeItem(patch: Partial<LegendItem>): LegendItem {
  return {
    id: newId(),
    kind: "symbol",
    family_key: null,
    symbol_key: null,
    text: "",
    length_mm: null,
    width_mm: null,
    line_style: "solid",
    line_length: 8,
    ...patch,
  };
}

export function addItem(doc: LegendDoc, blockId: string, patch: Partial<LegendItem>): { doc: LegendDoc; id: string } {
  if (!doc.blocks.some((b) => b.id === blockId)) return { doc, id: "" };
  const item = makeItem(patch);
  return { doc: mapBlock(doc, blockId, (b) => ({ ...b, items: [...b.items, item] })), id: item.id };
}

export const NEUTRAL_SECTION: SectionStyle = {
  header: "#6b7280",
  header_text: "#ffffff",
  background: "#f0f1f3",
  border_on: true,
  border: "#6b7280",
  symbol: "#6b7280",
  text: "#000000",
  padding: 1.5,
};

/** Default look of a section from a plan colour (same rule as the backend). */
export function sectionStyle(color?: string | null): SectionStyle {
  if (!color || !/^#[0-9a-f]{6}$/i.test(color) || /^#(ffffff|000000)$/i.test(color)) return { ...NEUTRAL_SECTION };
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
  const lum = 0.299 * r + 0.587 * g + 0.114 * b;
  const mix = (c: number) => Math.round(c + (255 - c) * 0.9);
  const bg = `#${[r, g, b].map((c) => mix(c).toString(16).padStart(2, "0")).join("")}`;
  return { header: color, header_text: lum > 160 ? "#000000" : "#ffffff", background: bg, border_on: true, border: color, symbol: color, text: "#000000", padding: 1.5 };
}

export function addBlock(doc: LegendDoc, title: string, categoryId: string | null = null, color?: string | null, layer = ""): { doc: LegendDoc; id: string } {
  const block: LegendBlock = { id: newId(), category_id: categoryId, title, layer, collapsed: false, style: sectionStyle(color), items: [] };
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

/** Legend entries whose apparatus does not occur in the current imports. */
export function staleItems(doc: LegendDoc, rows: RowLike[]): Set<string> {
  const used = new Set(rows.filter((r) => r.total > 0).map((r) => r.family_key));
  const out = new Set<string>();
  for (const b of doc.blocks) for (const it of b.items) if (it.kind === "symbol" && it.family_key && !used.has(it.family_key)) out.add(it.id);
  return out;
}

/** Block for a new entry: the one of its category, else the fallback or first block. */
export function blockForCategory(doc: LegendDoc, categories: string[], fallback: string | null): string | null {
  for (const c of categories) {
    const b = doc.blocks.find((x) => x.category_id === c);
    if (b) return b.id;
  }
  return fallback ?? doc.blocks[0]?.id ?? null;
}

/** Description of a new entry: the company text first, else the library name. */
export function describe(familyKey: string | null, fallback: string, descriptions: Record<string, string>): string {
  return (familyKey && descriptions[familyKey]) || fallback;
}

export function symbolRequestKey(it: { symbol_key: string | null; length_mm: number | null; width_mm: number | null }): string {
  return `${it.symbol_key}|${it.length_mm ?? ""}|${it.width_mm ?? ""}`;
}
