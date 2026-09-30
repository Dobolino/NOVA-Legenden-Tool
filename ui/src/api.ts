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
  nova_version: string;
  oda_path: string;
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

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
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

const qs = (params: Record<string, string | boolean | number>) =>
  new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();

export const api = {
  status: () => request<Status>("GET", "/api/status"),
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
