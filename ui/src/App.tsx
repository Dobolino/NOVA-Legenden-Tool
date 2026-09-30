import { useCallback, useEffect, useState } from "react";
import { api, Category, Options, Status, UpdateInfo } from "./api";
import Library from "./components/Library";
import Categories from "./components/Categories";
import SettingsPage from "./components/SettingsPage";

type Tab = "library" | "categories" | "settings";

export interface Toast {
  text: string;
  error?: boolean;
}

export default function App() {
  const [tab, setTab] = useState<Tab>("library");
  const [status, setStatus] = useState<Status | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [options, setOptions] = useState<Options | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [revision, setRevision] = useState(0); // bumps when library data changes
  const [update, setUpdate] = useState<UpdateInfo | null>(null);

  const notify = useCallback((text: string, error = false) => {
    setToast({ text, error });
    window.setTimeout(() => setToast(null), error ? 6000 : 2500);
  }, []);

  const reload = useCallback(async () => {
    try {
      const [s, c, o] = await Promise.all([api.status(), api.categories(), api.options()]);
      setStatus(s);
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

  const noDatasets = status && status.datasets.length === 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">NL</span> NOVA-Legenden
        </div>
        <nav className="tabs">
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
          <>
            <span className={`chip ${noDatasets ? "warn" : ""}`} title="Geladene Nova-Datensätze">
              <span className={`dot ${noDatasets ? "warn" : ""}`} />
              {status.datasets.length} Datensätze · {status.symbol_count} Symbole
            </span>
            <span className={`chip ${status.company_error ? "warn" : ""}`} title={status.company_db}>
              <span className={`dot ${status.company_error || !status.settings.company_folder ? "warn" : ""}`} />
              {status.settings.company_folder ? "Firmenordner" : "Firmenordner fehlt"}
            </span>
            <span className="chip">Nova {status.settings.nova_version}</span>
            {update?.available && (
              <button className="chip update" onClick={() => setTab("settings")} title="Zum Update">
                Update {update.latest} verfügbar
              </button>
            )}
          </>
        )}
      </header>
      <div className="main">
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
          <SettingsPage status={status} update={update} onUpdate={setUpdate} notify={notify} onChanged={reload} />
        )}
      </div>
      {toast && <div className={`toast ${toast.error ? "error" : ""}`}>{toast.text}</div>}
    </div>
  );
}
