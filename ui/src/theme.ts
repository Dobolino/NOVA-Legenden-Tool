// Light or dark mode per user (this computer). "system" follows Windows.
export type ThemeMode = "system" | "light" | "dark";

const KEY = "nova-legenden-theme";

export function loadTheme(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === "system") delete root.dataset.theme;
  else root.dataset.theme = mode;
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* private window: mode lasts for this session */
  }
}

export function effectiveDark(mode: ThemeMode): boolean {
  if (mode !== "system") return mode === "dark";
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}
