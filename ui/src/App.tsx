import { useCallback, useEffect, useState } from "react";
import { api, Category, Options, setDatasetNames, Status, UpdateInfo } from "./api";
import Library from "./components/Library";
import Categories from "./components/Categories";
import SettingsPage from "./components/SettingsPage";
import ProjectsPage from "./components/ProjectsPage";
import { applyTheme, effectiveDark, loadTheme, ThemeMode } from "./theme";

type Tab = "projects" | "library" | "categories" | "settings";

export interface Toast {
  text: string;
  error?: boolean;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("projects");
  const [status, setStatus] = useState<Status | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [options, setOptions] = useState<Options | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [revision, setRevision] = useState(0); // bumps when library data changes
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [installing, setInstalling] = useState(false);
  const [theme, setThemeState] = useState<ThemeMode>(loadTheme);
  const setTheme = useCallback((mode: ThemeMode) => {
    applyTheme(mode);
    setThemeState(mode);
    api.saveTheme(mode).catch(() => undefined); // localStorage is empty after a restart of the window
  }, []);

  const notify = useCallback((text: string, error = false) => {
    setToast({ text, error });
    window.setTimeout(() => setToast(null), error ? 6000 : 2500);
  }, []);

  const reload = useCallback(async () => {
    try {
      const [s, c, o] = await Promise.all([api.status(), api.categories(), api.options()]);
      setDatasetNames(s.datasets);
      setStatus(s);
      const saved = s.settings.ui_theme;
      if (saved === "light" || saved === "dark" || saved === "system") {
        applyTheme(saved);
        setThemeState(saved);
      }
      setCategories(c.items);
      setOptions(o);
      setRevision((r) => r + 1);
    } catch (e) {
      notify(`Verbindung zum Programm fehlgeschlagen: ${(e as Error).message}`, true);
    }
  }, [notify]);

  const reloadCategories = useCallback(async () => {
    const c = await api.categories();
    setCategories(c.items);
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  // Look for a new program version once at start (silently, errors ignored)
  useEffect(() => {
    api.updateCheck().then(setUpdate).catch(() => undefined);
  }, []);

  /** Same as «Jetzt aktualisieren» in the settings: confirm, download, check, silent setup, restart. */
  async function installUpdate() {
    if (!update) return;
    if (!update.can_install) {
      notify(update.message || "Das Update läuft nur im installierten Windows-Programm.");
      return;
    }
    if (!window.confirm(`Update ${update.latest} jetzt installieren? Das Programm schliesst sich und startet danach neu.`)) return;
    setInstalling(true);
    try {
      const r = await api.updateInstall();
      notify(r.message);
    } catch (e) {
      notify((e as Error).message, true);
      setInstalling(false);
    }
  }

  const noDatasets = status && status.datasets.length === 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">NL</span> NOVA-Legenden
        </div>
        <nav className="tabs">
          <button className={`tab ${tab === "projects" ? "active" : ""}`} onClick={() => setTab("projects")}>
            Projekte
          </button>
          <button className={`tab ${tab === "library" ? "active" : ""}`} onClick={() => setTab("library")}>
            Bibliothek
          </button>
          <button className={`tab ${tab === "categories" ? "active" : ""}`} onClick={() => setTab("categories")}>
            Kategorien
          </button>
          <button className={`tab ${tab === "settings" ? "active" : ""}`} onClick={() => setTab("settings")}>
            Einstellungen
          </button>
        </nav>
        <div className="spacer" />
        {status && (
          <div className="top-chips">
            <span className={`chip ${noDatasets ? "warn" : ""}`} title="Geladene Nova-Symbol-Datensätze (z. B. V1 2022, V2 2025)">
              <span className={`dot ${noDatasets ? "warn" : ""}`} />
              {status.datasets.length} Symbol-Datensätze · {status.symbol_count} Symbole
            </span>
            <span className={`chip ${status.company_error ? "warn" : ""}`} title={`Firmenweite Daten: ${status.company_db}`}>
              <span className={`dot ${status.company_error || !status.settings.company_folder ? "warn" : ""}`} />
              {status.settings.company_folder ? "Firmenordner" : "Firmenordner fehlt"}
            </span>
            <span className="chip" title="Standard für neue Projekte. Jedes Projekt speichert seine eigene Nova-Version.">
              Nova-Version {status.settings.nova_version}
            </span>
            <button
              className="chip theme-btn"
              onClick={() => setTheme(effectiveDark(theme) ? "light" : "dark")}
              title={effectiveDark(theme) ? "Zum hellen Modus wechseln" : "Zum dunklen Modus wechseln"}
              aria-label={effectiveDark(theme) ? "Heller Modus" : "Dunkler Modus"}
            >
              {effectiveDark(theme) ? "☀ Hell" : "☾ Dunkel"}
            </button>
            {update?.available && (
              <button
                className="chip update"
                disabled={installing}
                onClick={() => installUpdate()}
                title={update.can_install ? "Update jetzt installieren" : "Update läuft nur im installierten Programm"}
              >
                {installing ? "Update läuft …" : `Update ${update.latest} verfügbar`}
              </button>
            )}
          </div>
        )}
      </header>
      <div className="main">
        {tab === "projects" && (
          <ProjectsPage categories={categories} notify={notify} onOpenSettings={() => setTab("settings")} />
        )}
        {tab === "library" && options && (
          <Library
            categories={categories}
            options={options}
            revision={revision}
            datasets={status?.datasets ?? []}
            notify={notify}
            onCategoriesChanged={reloadCategories}
            onOpenSettings={() => setTab("settings")}
          />
        )}
        {tab === "categories" && options && (
          <Categories
            categories={categories}
            options={options}
            notify={notify}
            onChanged={reload}
          />
        )}
        {tab === "settings" && status && (
          <SettingsPage
            status={status}
            update={update}
            onUpdate={setUpdate}
            notify={notify}
            onChanged={reload}
            theme={theme}
            onTheme={setTheme}
          />
        )}
      </div>
      {toast && <div className={`toast ${toast.error ? "error" : ""}`}>{toast.text}</div>}
    </div>
  );
}
