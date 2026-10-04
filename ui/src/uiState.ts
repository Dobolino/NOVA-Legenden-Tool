// Small pure helpers of the UI: session state, labels and the category draft.
// No React here, so npm test can check them with node:test.
import { parseSheets } from "./sheets.ts";

// -- session state -------------------------------------------------------------

interface KeyStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function sessionStore(): KeyStore | null {
  try {
    return typeof sessionStorage === "undefined" ? null : sessionStorage;
  } catch {
    return null;
  }
}

/** Plans section open? A project without plans always shows it. */
export function plansOpen(projectId: string, planCount: number, store: KeyStore | null = sessionStore()): boolean {
  if (planCount === 0) return true;
  try {
    const value = store?.getItem(`plans-open:${projectId}`);
    return value === null || value === undefined ? true : value === "1";
  } catch {
    return true;
  }
}

export function rememberPlansOpen(projectId: string, open: boolean, store: KeyStore | null = sessionStore()): void {
  try {
    store?.setItem(`plans-open:${projectId}`, open ? "1" : "0");
  } catch {
    /* private window: the section just opens again next time */
  }
}

// -- import versions -----------------------------------------------------------

export interface VersionLike {
  id: number;
  file_name: string | null;
  format: string | null;
  imported_at: string | null;
  imported_by: string | null;
}

/** "Importversion 2 · 30.09.2026 10:12 · 3_1.OG.dxf (DXF) · mueller · aktuell". Newest first in the list. */
export function importVersionLabel(versions: VersionLike[], index: number): string {
  const v = versions[index];
  const number = versions.length - index;
  const when = v.imported_at ? formatDateTime(v.imported_at) : "";
  const file = v.file_name ? `${v.file_name}${v.format ? ` (${v.format.toUpperCase()})` : ""}` : "Plandatei entfernt";
  return [`Importversion ${number}`, when, file, v.imported_by ?? "", index === 0 ? "aktuell" : ""]
    .filter(Boolean)
    .join(" · ");
}

export function formatDateTime(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso);
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : iso;
}

/** "3 → 5 · +2" */
export function countChange(before: number, after: number): string {
  const delta = after - before;
  return `${before} → ${after} · ${delta > 0 ? `+${delta}` : delta}`;
}

export function changeWords(s: { neu: number; weg: number; geaendert: number }): string {
  const parts: string[] = [];
  if (s.neu) parts.push(`${s.neu} neu`);
  if (s.weg) parts.push(`${s.weg} entfallen`);
  if (s.geaendert) parts.push(`${s.geaendert} Anzahl geändert`);
  return parts.join(", ");
}

// -- layer state of a category -------------------------------------------------

export interface LayerStateLike {
  state: "automatisch" | "manuell" | "waehlen" | "unbenutzt";
  layer: string;
  color: string;
  reason: string;
  used: number;
  layer_missing: boolean;
  no_color: boolean;
}

export function layerStateText(c: LayerStateLike): { cls: string; text: string; detail: string } {
  let detail = "";
  if (c.layer_missing) detail = `Ebene ${c.layer} ist in den Plänen nicht vorhanden.`;
  else if (c.no_color && c.layer) detail = `Ebene ${c.layer} ist vorhanden, hat aber keine Farbangabe.`;
  else if (!c.layer && c.reason) detail = `Grund: ${c.reason}.`;
  switch (c.state) {
    case "manuell":
      return { cls: "manual", text: `Manuell → ${c.layer}`, detail };
    case "automatisch":
      return { cls: "auto", text: `Automatisch → ${c.layer}`, detail };
    case "waehlen":
      return { cls: "choose", text: "Ebene wählen", detail };
    default:
      return {
        cls: "unused",
        text: "Im Projekt nicht verwendet",
        detail: c.layer ? `Automatisch passend wäre ${c.layer}.` : detail,
      };
  }
}

// -- category draft ------------------------------------------------------------

export interface CategoryLike {
  id: string;
  title: string;
  parent: string | null;
  layer: string | null;
  columns: number;
  spacing: number;
  hidden: boolean;
  sheets: string[];
}

export interface CategoryDraft {
  title: string;
  parent: string;
  layer: string;
  columns: string;
  spacing: string;
  sheets: string;
}

export function draftOf(c: CategoryLike): CategoryDraft {
  return {
    title: c.title,
    parent: c.parent ?? "",
    layer: c.layer ?? "",
    columns: String(c.columns),
    spacing: String(c.spacing),
    sheets: c.sheets.join(", "),
  };
}

/** Changed fields as an API patch, or an error text. Empty patch = nothing to save. */
export function draftPatch(
  draft: CategoryDraft,
  orig: CategoryLike,
): { patch: Partial<CategoryLike>; error: string } {
  const patch: Partial<CategoryLike> = {};
  const title = draft.title.trim();
  if (!title) return { patch, error: "Titel darf nicht leer sein" };
  if (title !== orig.title) patch.title = title;
  const parent = draft.parent || null;
  if (parent !== (orig.parent ?? null)) patch.parent = parent;
  const layer = draft.layer.trim();
  if (layer !== (orig.layer ?? "")) patch.layer = layer;
  const columns = Number(draft.columns);
  if (!Number.isInteger(columns) || columns < 1 || columns > 6) return { patch, error: "Spalten: ganze Zahl von 1 bis 6" };
  if (columns !== orig.columns) patch.columns = columns;
  const spacing = Number(String(draft.spacing).replace(",", "."));
  if (!Number.isFinite(spacing) || spacing <= 0) return { patch, error: "Zeilenabstand muss grösser als 0 sein" };
  if (spacing !== orig.spacing) patch.spacing = spacing;
  const sheets = parseSheets(draft.sheets);
  if (JSON.stringify(sheets) !== JSON.stringify(orig.sheets)) patch.sheets = sheets;
  return { patch, error: "" };
}

export function isDirty(draft: CategoryDraft | null, orig: CategoryLike | undefined): boolean {
  if (!draft || !orig) return false;
  const { patch, error } = draftPatch(draft, orig);
  return Boolean(error) || Object.keys(patch).length > 0;
}
