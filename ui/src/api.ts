import type { LegendDoc } from "./legend";
// Thin client for the local Python API.

export interface SymbolBrief {
  key: string;
  name: string;
  item: string;
  graphic_id: string;
  dataset: string;
  sheet: string;
  folder: string;
  mounting: string | null;
  label_variant: string;
  orientation: string;
  kind: string;
  svg: string;
  has_fill?: boolean;
  is_representative?: boolean;
}

export interface FamilyItem {
  id: string;
  key: string;
  title: string;
  dataset: string;
  representative: SymbolBrief;
  mountings: string[];
  variant_count: number;
  categories: string[];
  category_source: string;
  conflicts: string[];
  is_representative: boolean;
  has_fill: boolean;
  show_fill: boolean;
  members?: SymbolBrief[];
}

export interface Category {
  id: string;
  title: string;
  parent: string | null;
  layer: string | null;
  columns: number;
  spacing: number;
  sort: number;
  hidden: boolean;
  sheets: string[];
  family_count?: number;
  updated_by?: string;
  updated_at?: string;
}

export interface Options {
  merge_labels: boolean;
  merge_orientation: boolean;
  show_empty_categories: boolean;
  legend_by_category: boolean;
}

export interface DatasetInfo {
  id: string;
  file: string;
  version: string;
  long_name: string;
  predecessor: string;
  symbol_count: number;
}

export interface Settings {
  dataset_paths: string[];
  company_folder: string;
  projects_folder: string;
  nova_version: string;
  oda_path: string;
  ui_theme?: string;
  update_channel?: "stable" | "test";
  stencil_folder?: string;
}

export interface UpdateInfo {
  current: string;
  latest: string;
  available: boolean;
  can_install: boolean;
  notes: string;
  published: string;
  asset_name: string;
  size: number;
  page_url: string;
  message: string;
}

export interface Status {
  version: string;
  version_label: string;
  user: string;
  settings: Settings;
  company_db: string;
  company_error: string;
  datasets: DatasetInfo[];
  symbol_count: number;
  sync: { neu?: string[]; unveraendert?: string[]; entfernt?: string[]; fehler?: string[]; doppelt?: string[] };
  oda: string;
  local_home: string;
  dialogs?: boolean;
  is_admin?: boolean;
}

export interface SymbolDetail {
  key: string;
  name: string;
  part_name: string;
  item: string;
  graphic_id: string;
  dataset: string;
  sheet: string;
  sheet_name: string;
  folder: string;
  folder_path: string[] | null;
  stencils: string[] | null;
  kind: string;
  mounting: string | null;
  engine: string | null;
  lib_ref: string | null;
  files_3d: string[] | null;
  attributes: Record<string, string> | null;
  points: Record<string, number[]> | null;
  svg_points: string;
  stats: Record<string, number>;
}

export interface ProjectSummary {
  id: string;
  name: string;
  project_number: string;
  nova_version: string;
  created_at: string;
  created_by: string;
  template_from: string;
  use_as_template: boolean;
  plan_count: number;
  modified: string;
}

export interface CategoryColor {
  id: string;
  title: string;
  legend_layer: string;
  color: string;
  layer: string;
  reason: string;
  manual: boolean;
  parent?: string | null;
  state: "automatisch" | "manuell" | "waehlen" | "unbenutzt";
  used: number;
  layer_missing: boolean;
  no_color: boolean;
}

export interface Plan {
  id: number;
  name: string;
  sort: number;
  current_version: number | null;
  file_name: string | null;
  format: string | null;
  imported_at: string | null;
  imported_by: string | null;
  versions: number;
  change_summary: ChangeSummary | null;
}

export interface ChangeSummary {
  neu: number;
  weg: number;
  geaendert: number;
}

export interface VersionInfo {
  id: number;
  file_name: string | null;
  format: string | null;
  imported_at: string | null;
  imported_by: string | null;
}

export interface CountChange {
  source_key?: string;
  name: string;
  title?: string;
  item?: string;
  svg?: string;
  status?: string;
  reason?: string;
  kind: "neu" | "weg" | "geaendert";
  before: number;
  after: number;
  delta: number;
}

export interface PlanChanges {
  plan_id: number;
  name: string;
  versions: VersionInfo[];
  older: number | null;
  newer: number | null;
  comparable: boolean;
  changes: CountChange[];
  ignored_changes: CountChange[];
  unchanged: number;
  summary: ChangeSummary;
}

export interface PreviewChange {
  key: string;
  title: string;
  item: string;
  svg: string;
  kind: "neu" | "weg" | "geaendert";
  before: number;
  after: number;
  delta: number;
}

export interface ImportPreview {
  token: string;
  file_name: string;
  format: string;
  plan: { id: number; name: string } | null;
  floor: string;
  existing: boolean;
  changes: PreviewChange[];
  unchanged: number;
  summary: { neu: number; weg: number; geaendert: number };
  total_before: number;
  total_after: number;
  kinds_after: number;
  unknown_after: number;
  new_unknown: { name: string; count: number }[];
  warnings: { level: "warn" | "info"; text: string }[];
}

export interface ReviewCheck {
  id: string;
  title: string;
  target: "unknown" | "list" | "layers" | "legend" | "ignored" | "changes";
  level: "block" | "warn" | "ok";
  count: number;
  detail: string;
  items: { title: string; detail: string }[];
}

export interface Review {
  ready: boolean;
  blocks: number;
  warns: number;
  checks: ReviewCheck[];
}

export interface StoredLegend {
  id?: number;
  name?: string;
  doc: LegendDoc;
  updated_at: string;
  updated_by: string;
}

/** One of the named legends of a project. */
export interface LegendListItem {
  id: number;
  name: string;
  updated_at: string;
  updated_by: string;
  entries: number;
}

export interface GeneralInfo {
  source: string;
  kind: "" | "dxf" | "project";
  error: string;
  w: number;
  h: number;
  file?: string;
  /** a DXF / DWG split into rows (graphic + text): they flow into the legend columns */
  rows?: { id: string; key?: string; text: string; heading: boolean; names: string[]; text_scale?: number; symbol_factor?: number; rotation?: number; text_place?: "top" | "middle" | "bottom"; line?: boolean; picture?: "line" | "swatch" | "symbol"; swatch?: string }[];
  /** drawing of every row graphic (preview), by row id */
  row_svgs?: Record<string, { vb: string; svg: string }>;
}

/** One row of the general part as the settings editor shows it. */
export interface GeneralRow {
  id: string;
  key: string;
  original: string;
  text: string;
  hidden: boolean;
  links: string[];
  heading: boolean;
  names: string[];
  vb: string;
  svg: string;
  by: string;
  at: string;
}

export interface CompanyGeneral extends GeneralInfo {
  file_time: number | null;
  rows: GeneralRow[];
  company: CompanyLegend;
}

export interface CompanyLegend {
  general_path: string;
  admins: string[];
  text_size: number;
  symbol_scale: number;
  hatch_off: boolean;
  fill_off: boolean;
  user: string;
  is_admin: boolean;
  bootstrap: boolean;
}

/** A company legend text of one symbol family. */
export interface CompanyText {
  family_key: string;
  text: string;
  updated_by: string | null;
  updated_at: string | null;
  title: string;
  svg: string;
  known: boolean;
}

/** One entry of your Nova user stencil (Benutzerschablone). */
export interface StencilEntry {
  name: string;
  description: string;
  item: string | null;
  layer: string | null;
  symbol_key: string | null;
  family_key: string | null;
  categories: string[];
  macro: string | null;
  macro_found: boolean;
}

export interface StencilData {
  folder: string;
  found: boolean;
  files: string[];
  errors: string[];
  nova: string;
  sets: { name: string; description: string; tabs: { name: string; description: string; entries: StencilEntry[] }[] }[];
}

export interface LegendInfo {
  legend: StoredLegend | null;
  template_texts: string[];
  descriptions: Record<string, string>;
  stencil_names?: Record<string, string>;
  grids: { id: string; label: string; row: number; text_offset: number }[];
  style: LegendDoc["style"];
  company: CompanyLegend;
  oda: boolean;
  in_general: GeneralContents;
}

/** What the general part already shows (texts normalised like normText in legend.ts). */
export interface GeneralContents {
  texts: string[];
  symbol_keys: string[];
  family_keys: string[];
  covered: string[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type LegendPrim = { t: string; [key: string]: any };

export interface LegendLayout {
  width: number;
  height: number;
  prims: LegendPrim[];
  general: GeneralInfo;
}

export interface SymbolRender {
  svg: string;
  box?: [number, number, number, number];
  kind?: string;
  engine?: boolean;
  length_mm?: number | null;
  width_mm?: number | null;
  missing?: boolean;
}

export interface SummaryRow {
  family_id: string;
  family_key: string;
  symbol_key: string;
  datasets: string[];
  title: string;
  item: string;
  dataset: string;
  svg: string;
  kind: string;
  categories: string[];
  counts: Record<string, number>;
  mountings: Record<string, number>;
  names: string[];
  methods: string[];
  sources: string[];
  total: number;
}

export interface UnknownElement {
  source_key: string;
  name: string;
  item: string;
  graphic_name: string;
  dataset: string;
  counts: Record<string, number>;
  layers: Record<string, number>;
  total: number;
}

export interface IgnoredElement {
  source_key: string;
  name: string;
  reason: string;
  manual: boolean;
  total: number;
}

export interface LayerInfo {
  name: string;
  color: string;
  linetype: string;
  source: string;
}

export interface ProjectDetail {
  id: string;
  folder: string;
  meta: {
    name: string;
    project_number?: string;
    nova_version: string;
    created_at: string;
    created_by: string;
    template_from: string;
    use_as_template?: boolean;
  };
  settings: Record<string, unknown>;
  layers: LayerInfo[];
  category_colors: CategoryColor[];
  export_name: string;
  plans: Plan[];
  rows: SummaryRow[];
  unknown: UnknownElement[];
  ignored: IgnoredElement[];
  stats: Record<string, number>;
}

export interface Suggestion {
  symbol_key: string;
  name: string;
  item: string;
  dataset: string;
  mounting: string | null;
  svg: string;
  score: number;
  parts: Record<string, number>;
}

async function request<T>(method: string, url: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data.detail) msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

async function upload<T>(url: string, fields: Record<string, string>, file: File): Promise<T> {
  const form = new FormData();
  for (const [k, v] of Object.entries(fields)) form.append(k, v);
  form.append("file", file);
  const res = await fetch(url, { method: "POST", body: form });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (data.detail) msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const qs = (params: Record<string, string | boolean | number>) =>
  new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();

export const api = {
  status: () => request<Status>("GET", "/api/status"),
  projects: () => request<{ folder: string; folder_exists: boolean; shared?: boolean; items: ProjectSummary[] }>("GET", "/api/projects"),
  createProject: (name: string, nova_version: string, template: string | null, projectNumber = "") =>
    request<ProjectDetail>("POST", "/api/projects", { name, nova_version, template, project_number: projectNumber }),
  project: (id: string) => request<ProjectDetail>("GET", `/api/projects/${encodeURIComponent(id)}`),
  updateProject: (id: string, values: { name?: string; project_number?: string; nova_version?: string; use_as_template?: boolean }) =>
    request<ProjectDetail>("PUT", `/api/projects/${encodeURIComponent(id)}`, values),
  copyProject: (id: string, name: string) =>
    request<ProjectDetail>("POST", `/api/projects/${encodeURIComponent(id)}/copy`, { name }),
  deleteProject: (id: string) => request<{ ok: boolean; moved_to: string }>("DELETE", `/api/projects/${encodeURIComponent(id)}`),
  exportUrl: (id: string) => `/api/projects/${encodeURIComponent(id)}/export`,
  review: (id: string) => request<Review>("GET", `/api/projects/${encodeURIComponent(id)}/review`),
  previewPlan: (id: string, name: string, file: File, planId?: number) =>
    upload<ImportPreview>(`/api/projects/${encodeURIComponent(id)}/plans/preview`, { name, ...(planId ? { plan_id: String(planId) } : {}) }, file),
  commitPlan: (id: string, token: string) => request<ProjectDetail>("POST", `/api/projects/${encodeURIComponent(id)}/plans/commit`, { token }),
  discardPreview: (id: string, token: string) =>
    request<{ ok: boolean }>("DELETE", `/api/projects/${encodeURIComponent(id)}/plans/preview/${encodeURIComponent(token)}`),
  importPlan: (id: string, name: string, file: File, planId?: number) =>
    upload<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}/plans`, { name, ...(planId ? { plan_id: String(planId) } : {}) }, file),
  renamePlan: (id: string, planId: number, name: string) =>
    request<ProjectDetail>("PUT", `/api/projects/${encodeURIComponent(id)}/plans/${planId}`, { name }),
  reorderPlans: (id: string, ids: number[]) =>
    request<ProjectDetail>("POST", `/api/projects/${encodeURIComponent(id)}/plans/reorder`, { ids }),
  changes: (id: string) =>
    request<{ plans: PlanChanges[] }>("GET", `/api/projects/${encodeURIComponent(id)}/changes`),
  planChanges: (id: string, planId: number, older: number, newer: number) =>
    request<{ plan: PlanChanges }>(
      "GET",
      `/api/projects/${encodeURIComponent(id)}/plans/${planId}/changes?${qs({ older, newer })}`,
    ),
  deletePlan: (id: string, planId: number) =>
    request<ProjectDetail>("DELETE", `/api/projects/${encodeURIComponent(id)}/plans/${planId}`),
  detachPlan: (id: string, planId: number) =>
    request<ProjectDetail>("POST", `/api/projects/${encodeURIComponent(id)}/plans/${planId}/detach`),
  deleteRows: (id: string, sourceKeys: string[]) =>
    request<ProjectDetail>("POST", `/api/projects/${encodeURIComponent(id)}/rows/delete`, { source_keys: sourceKeys }),
  setCategoryLayer: (id: string, categoryId: string, layer: string | null) =>
    request<ProjectDetail>("PUT", `/api/projects/${encodeURIComponent(id)}/category-layer`, {
      category_id: categoryId,
      layer,
    }),
  suggestions: (id: string, sourceKey: string) =>
    request<{ items: Suggestion[] }>("GET", `/api/projects/${encodeURIComponent(id)}/suggestions?${qs({ source_key: sourceKey })}`),
  setMapping: (sourceKey: string, symbolKey: string | null, name = "") =>
    request<{ ok: boolean }>("PUT", "/api/mappings", { source_key: sourceKey, symbol_key: symbolKey, name }),
  saveTheme: (mode: "system" | "light" | "dark") => request<{ mode: string }>("PUT", "/api/settings/theme", { mode }),
  saveSettings: (s: Partial<Settings>) => request<Status>("PUT", "/api/settings", s),
  searchDatasets: () => request<{ found: string[]; folders: string[] }>("POST", "/api/settings/search-datasets"),
  sync: () => request<Status["sync"]>("POST", "/api/library/sync"),
  updateCheck: () => request<UpdateInfo>("GET", "/api/update/check"),
  updateInstall: () => request<{ ok: boolean; message: string }>("POST", "/api/update/install"),
  options: () => request<Options>("GET", "/api/options"),
  saveOptions: (o: Partial<Options>) => request<Options>("PUT", "/api/options", o),
  families: (p: { q: string; category: string; dataset: string; mounting: string; all_variants: boolean }) =>
    request<{ total: number; items: FamilyItem[] }>("GET", `/api/library/families?${qs(p)}`),
  family: (id: string) => request<FamilyItem>("GET", `/api/library/family?${qs({ id })}`),
  symbol: (key: string, fill = true) => request<SymbolDetail>("GET", `/api/library/symbol?${qs({ key, fill })}`),
  setFill: (id: string, show_fill: boolean | null) =>
    request<FamilyItem>("PUT", `/api/library/family/fill?${qs({ id })}`, { show_fill }),
  assign: (id: string, categories: string[] | null) =>
    request<FamilyItem>("PUT", `/api/library/family/categories?${qs({ id })}`, { categories }),
  categories: (dataset = "") =>
    request<{ items: Category[] }>("GET", dataset ? `/api/categories?${qs({ dataset })}` : "/api/categories"),
  createCategory: (title: string, parent: string | null) =>
    request<Category>("POST", "/api/categories", { title, parent }),
  updateCategory: (id: string, values: Partial<Category>) =>
    request<Category>("PUT", `/api/categories/${encodeURIComponent(id)}`, values),
  deleteCategory: (id: string) => request<{ ok: boolean }>("DELETE", `/api/categories/${encodeURIComponent(id)}`),
  reorder: (ids: string[]) => request<{ items: Category[] }>("POST", "/api/categories/reorder", { ids }),
  dialog: (kind: "dataset" | "folder" | "legend", start = "") =>
    request<{ available: boolean; path: string | null }>("POST", `/api/dialog/${kind}`, { start }),
  legend: (id: string, legendId?: number | null) =>
    request<LegendInfo>("GET", `/api/projects/${encodeURIComponent(id)}/legend${legendId ? `?legend=${legendId}` : ""}`),
  saveLegend: (id: string, doc: LegendDoc, signal?: AbortSignal, legendId?: number | null) =>
    request<{ legend: StoredLegend }>("PUT", `/api/projects/${encodeURIComponent(id)}/legend${legendId ? `?legend=${legendId}` : ""}`, { doc }, signal),
  legends: (id: string) => request<{ items: LegendListItem[] }>("GET", `/api/projects/${encodeURIComponent(id)}/legends`),
  newLegend: (id: string, body: { name: string; source: "proposal" | "empty" | "copy"; categories?: string[]; copy_of?: number | null }) =>
    request<{ legend: StoredLegend; items: LegendListItem[] }>("POST", `/api/projects/${encodeURIComponent(id)}/legends`, body),
  renameLegend: (id: string, legendId: number, name: string) =>
    request<{ items: LegendListItem[] }>("PUT", `/api/projects/${encodeURIComponent(id)}/legends/${legendId}`, { name }),
  deleteLegend: (id: string, legendId: number) =>
    request<{ items: LegendListItem[] }>("DELETE", `/api/projects/${encodeURIComponent(id)}/legends/${legendId}`),
  proposeLegend: (id: string, style?: LegendDoc["style"]) =>
    request<{ doc: LegendDoc }>("POST", `/api/projects/${encodeURIComponent(id)}/legend/propose`, { style: style ?? null }),
  layoutLegend: (id: string, doc: LegendDoc, signal?: AbortSignal) =>
    request<LegendLayout>("POST", `/api/projects/${encodeURIComponent(id)}/legend/layout`, { doc }, signal),
  legendGeneral: (id: string) =>
    request<GeneralInfo & { svg: string; prims: LegendPrim[] }>("GET", `/api/projects/${encodeURIComponent(id)}/legend/general`),
  legendExportName: (id: string, format: "dxf" | "dwg" | "pdf", block: string, legendId?: number | null) =>
    request<{ name: string }>("GET", `/api/projects/${encodeURIComponent(id)}/legend/export-name?${qs({ format, block, ...(legendId ? { legend: legendId } : {}) })}`),
  /** The file name is part of the path, so the download keeps it even if the header is ignored. */
  legendExportUrl: (id: string, name: string, format: "dxf" | "dwg" | "pdf", block: string, general: boolean, legendId?: number | null) =>
    `/api/projects/${encodeURIComponent(id)}/legend/export/${encodeURIComponent(name)}?${qs({ format, block, general, ...(legendId ? { legend: legendId } : {}) })}`,
  descriptions: () => request<{ items: CompanyText[]; file: string }>("GET", "/api/descriptions"),
  stencils: (projectId: string, nova = "") =>
    request<StencilData>("GET", `/api/stencils?${qs(projectId ? { project_id: projectId } : { nova })}`),
  macroPreviewUrl: (projectId: string, path: string) => `/api/stencils/macro-preview?${qs({ project_id: projectId, path })}`,
  descriptionsExportUrl: "/api/descriptions/export/edeco%20ag-Firmentexte.csv",
  importDescriptions: (file: File) => upload<{ changed: number; removed: number; rows: number }>("/api/descriptions/import", {}, file),
  legendExportFile: async (url: string): Promise<Blob> => {
    const res = await fetch(url);
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const data = await res.json();
        if (data.detail) msg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      } catch {
        /* keep status text */
      }
      throw new Error(msg);
    }
    return res.blob();
  },
  rememberLegend: (id: string, doc: LegendDoc) =>
    request<CompanyLegend>("POST", `/api/projects/${encodeURIComponent(id)}/legend/remember`, { doc }),
  companyLegend: () => request<CompanyLegend & { general: GeneralInfo }>("GET", "/api/company/legend"),
  companyGeneral: () => request<CompanyGeneral>("GET", "/api/company/general"),
  saveGeneralRow: (row: { key: string; text?: string; hidden?: boolean; links?: string[]; text_scale?: number; symbol_factor?: number; rotation?: number; text_place?: "top" | "middle" | "bottom" }) =>
    request<CompanyGeneral>("PUT", "/api/company/general/row", row),
  reloadGeneral: () => request<CompanyGeneral>("POST", "/api/company/general/reload"),
  saveCompanyLegend: (values: { general_path?: string; admins?: string[]; text_size?: number; symbol_scale?: number; hatch_off?: boolean; fill_off?: boolean }) =>
    request<CompanyLegend & { general: GeneralInfo }>("PUT", "/api/company/legend", values),
  legendSymbols: (items: { symbol_key: string; family_key: string | null; length_mm: number | null; width_mm: number | null; flat?: boolean }[], fills: { hatch_off: boolean; fill_off: boolean } = { hatch_off: false, fill_off: false }) =>
    request<{ items: SymbolRender[] }>("POST", "/api/legend/symbols", { items, ...fills }),
  diagnostics: (projectId = "") =>
    request<Record<string, unknown>>("GET", `/api/diagnostics${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ""}`),
  legendTexts: (q: string, familyKey = "") =>
    request<{ items: { text: string; score: number; source: string }[] }>(
      "GET",
      `/api/legend/texts?${qs({ q, family_key: familyKey })}`,
    ),
  setDescription: (familyKey: string, text: string | null) =>
    request<{ ok: boolean; text: string | null }>("PUT", "/api/descriptions", { family_key: familyKey, text }),
  resetCategories: () => request<{ items: Category[] }>("POST", "/api/categories/reset"),
};

// Readable dataset names, filled from /api/status (long name of each dataset)
const datasetNames: Record<string, string> = {};

export function setDatasetNames(datasets: DatasetInfo[]) {
  for (const d of datasets) {
    const hidden = /\binvisible\b/i.test(d.long_name);
    const name = d.long_name.replace(/\s*\binvisible\b/i, "").trim() || d.id;
    datasetNames[d.id] = hidden ? `${name} (in Nova ausgeblendet)` : name;
  }
}

export const DATASET_LABEL = (id: string) => {
  if (id === "Trimble.Elektroinstallationen.V2.CH") return "V2 (2025)";
  if (id === "Trimble.Elektroinstallationen.CH") return "V1 (2022)";
  return datasetNames[id] ?? id;
};
