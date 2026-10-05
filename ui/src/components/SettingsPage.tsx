import { useEffect, useState } from "react";
import CompanyLegendCard from "./CompanyLegendCard";
import CompanyTextsCard from "./CompanyTextsCard";
import { api, DATASET_LABEL, StencilData, Status, UpdateInfo } from "../api";
import { TrashIcon } from "./Icons";
import type { ThemeMode } from "../theme";

interface Props {
  status: Status;
  update: UpdateInfo | null;
  onUpdate: (u: UpdateInfo) => void;
  notify: (text: string, error?: boolean) => void;
  onChanged: () => void;
  theme: ThemeMode;
  onTheme: (mode: ThemeMode) => void;
}

export default function SettingsPage({ status, update, onUpdate, notify, onChanged, theme, onTheme }: Props) {
  const [paths, setPaths] = useState<string[]>(status.settings.dataset_paths);
  const [newPath, setNewPath] = useState("");
  const [company, setCompany] = useState(status.settings.company_folder);
  const [projectsFolder, setProjectsFolder] = useState(status.settings.projects_folder);
  const [nova, setNova] = useState(status.settings.nova_version);
  const [stencilFolder, setStencilFolder] = useState(status.settings.stencil_folder ?? "");
  const [stencilInfo, setStencilInfo] = useState<StencilData | null>(null);
  const [busy, setBusy] = useState(false);
  const [updating, setUpdating] = useState(false);

  async function checkUpdate() {
    setBusy(true);
    try {
      const u = await api.updateCheck();
      onUpdate(u);
      if (!u.available) notify(u.message || "Du hast die neueste Version.", Boolean(u.message && !u.latest));
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function installUpdate() {
    if (!window.confirm("Update jetzt installieren? Das Programm schliesst sich und startet danach neu.")) return;
    setUpdating(true);
    try {
      const r = await api.updateInstall();
      notify(r.message);
    } catch (e) {
      notify((e as Error).message, true);
      setUpdating(false);
    }
  }

  useEffect(() => {
    setPaths(status.settings.dataset_paths);
    setCompany(status.settings.company_folder);
    setProjectsFolder(status.settings.projects_folder);
    setNova(status.settings.nova_version);
    setStencilFolder(status.settings.stencil_folder ?? "");
    api.stencils("", status.settings.nova_version).then(setStencilInfo).catch(() => setStencilInfo(null));
  }, [status]);

  async function save(values: Parameters<typeof api.saveSettings>[0], ok: string) {
    setBusy(true);
    try {
      const s = await api.saveSettings(values);
      const errors = s.sync.fehler ?? [];
      const doubles = s.sync.doppelt ?? [];
      if (errors.length) notify(errors.join(" · "), true);
      else if (doubles.length) notify(`${ok}. ${doubles.length} doppelte Datei(en) übersprungen.`);
      else notify(ok);
      onChanged();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function search() {
    setBusy(true);
    try {
      const res = await api.searchDatasets();
      const merged = Array.from(new Set([...paths, ...res.found]));
      if (res.found.length === 0) notify(`Keine neuen Datensätze in ${res.folders.join(", ")} gefunden`);
      else await save({ dataset_paths: merged }, `${res.found.length} Datensätze hinzugefügt`);
    } finally {
      setBusy(false);
    }
  }

  const canPick = Boolean(status.dialogs);
  const pickHint = canPick ? "" : "Dateidialoge gibt es nur im Programmfenster. Pfad bitte einfügen.";

  /** Native dialog of the program window. Cancel keeps the previous value. */
  async function choose(kind: "dataset" | "folder" | "legend", start: string): Promise<string | null> {
    try {
      const r = await api.dialog(kind, start);
      if (!r.available) {
        notify("Dateidialoge gibt es nur im Programmfenster. Pfad bitte von Hand einfügen.", true);
        return null;
      }
      return r.path;
    } catch (e) {
      notify((e as Error).message, true);
      return null;
    }
  }

  const cleanPath = (p: string) => p.trim().replace(/^"(.*)"$/, "$1");
  const norm = (p: string) => p.replace(/\//g, "\\").toLowerCase();

  function removeAll() {
    if (!window.confirm("Alle Datensätze aus der Liste entfernen? Die Dateien selbst bleiben unverändert.")) return;
    save({ dataset_paths: [] }, "Alle Datensätze entfernt");
  }

  return (
    <div className="page settings-page">
      <div className="page-inner">
        <div className="page-heading"><div><div className="eyebrow">Konfiguration</div><h1>Einstellungen</h1><p>Darstellung, Bibliotheken und gemeinsame Daten verwalten.</p></div></div>
        <div className="card">
          <h3>Darstellung</h3>
          <p className="desc">Gilt nur auf diesem Computer. Die Legende bleibt immer weiss wie auf dem Plan.</p>
          <div className="row" role="radiogroup" aria-label="Darstellung">
            {(
              [
                ["light", "Hell"],
                ["dark", "Dunkel"],
                ["system", "Wie Windows"],
              ] as [ThemeMode, string][]
            ).map(([mode, label]) => (
              <label key={mode} className="toggle" style={{ color: "var(--fg)" }}>
                <input type="radio" name="theme" checked={theme === mode} onChange={() => onTheme(mode)} />
                {label}
              </label>
            ))}
          </div>
        </div>

        <div className="card">
          <h3>Programm-Update</h3>
          <p className="desc">
            Installiert: {status.version_label}.
            {update?.latest ? ` Neueste Version: ${update.latest}.` : ""}
          </p>
          {update?.available && (
            <p>
              <span className="badge manual">neu</span> Version {update.latest} ist verfügbar
              {update.size ? ` (${Math.round(update.size / 1e6)} MB)` : ""}.
            </p>
          )}
          <label className="field" style={{ maxWidth: 420 }}>
            <span>Welche Versionen</span>
            <select
              className="select"
              value={status.settings.update_channel ?? "stable"}
              disabled={busy || updating}
              onChange={async (e) => {
                await save({ update_channel: e.target.value as "stable" | "test" }, "Update-Kanal gespeichert");
                checkUpdate();
              }}
              aria-label="Update-Kanal"
            >
              <option value="stable">Freigegebene Versionen</option>
              <option value="test">Auch Testversionen (Entwicklung)</option>
            </select>
          </label>
          <p className="hint">
            Freigegebene Versionen kommen aus dem Hauptstand. Testversionen entstehen bei jeder Änderung in der Entwicklung und
            können unfertig sein. Die Einstellung gilt nur für diesen Computer.
          </p>
          {update && !update.available && update.message && <p className="hint">{update.message}</p>}
          {update?.available && !update.can_install && <p className="warn-text">{update.message}</p>}
          <div className="row">
            <button className="btn" disabled={busy || updating} onClick={checkUpdate}>
              Nach Updates suchen
            </button>
            {update?.available && update.can_install && (
              <button className="btn primary" disabled={updating} onClick={installUpdate}>
                {updating ? "Update läuft …" : "Jetzt aktualisieren"}
              </button>
            )}
          </div>
        </div>

        <div className="card">
          <h3>Nova-Datensätze</h3>
          <p className="desc">
            Die Symbole stammen aus den Nova-Elektro-Datensätzen (.nzp). «Automatisch suchen» sucht in
            C:\Users\Public\Documents\Trimble\Warehouse und übernimmt nur Elektro-Datensätze mit Symbolen.
            Einzelne Dateien fügst du unten ein: im Explorer Shift + Rechtsklick → «Als Pfad kopieren».
          </p>
          <div className="path-list">
            {paths.length === 0 && <div className="hint">Noch kein Datensatz eingetragen.</div>}
            {paths.map((p) => {
              const ds = status.datasets.find((d) => norm(d.file) === norm(p));
              const doubled = (status.sync.doppelt ?? []).some((x) => norm(x) === norm(p));
              return (
                <div key={p} className="path-item">
                  <span className="path" title={p}>{p}</span>
                  <span className="info">
                    {ds && (
                      <span className="badge up" title={`Stand des Datensatzes: ${ds.version}`}>
                        Symbol-Datensatz {DATASET_LABEL(ds.id)} · Stand {ds.version} · {ds.symbol_count} Symbole
                      </span>
                    )}
                    {!ds && doubled && <span className="badge warn">doppelt, übersprungen</span>}
                    {!ds && !doubled && <span className="hint">nicht geladen</span>}
                  </span>
                  <button
                    className="btn icon danger"
                    disabled={busy}
                    aria-label={`${p} entfernen`}
                    title="Aus der Liste entfernen. Die Datei selbst bleibt unverändert."
                    onClick={() => save({ dataset_paths: paths.filter((x) => x !== p) }, "Entfernt")}
                  >
                    <TrashIcon />
                  </button>
                </div>
              );
            })}
          </div>
          <div className="row">
            <input
              className="input"
              style={{ flex: 1, minWidth: 260 }}
              placeholder="C:\…\Elektroinstallationen.V2.CH.nzp"
              aria-label="Pfad eines Nova-Datensatzes"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
            />
            <button
              className="btn primary"
              disabled={busy || !cleanPath(newPath)}
              onClick={() => {
                const p = cleanPath(newPath);
                setNewPath("");
                save({ dataset_paths: Array.from(new Set([...paths, p])) }, "Datensatz hinzugefügt");
              }}
            >
              Hinzufügen
            </button>
            <button
              className="btn"
              disabled={busy || !canPick}
              title={pickHint || "Nova-Datensatz (.nzp) im Explorer wählen"}
              onClick={async () => {
                const p = await choose("dataset", paths[paths.length - 1] ?? "C:\\Users\\Public\\Documents\\Trimble\\Warehouse");
                if (!p) return;
                if (paths.some((x) => norm(x) === norm(p))) {
                  notify("Dieser Datensatz ist schon eingetragen");
                  return;
                }
                save({ dataset_paths: [...paths, p] }, "Datensatz hinzugefügt");
              }}
            >
              Datei wählen …
            </button>
            <button className="btn" disabled={busy} onClick={search}>
              Automatisch suchen
            </button>
            <button
              className="btn"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await api.sync();
                  notify(r.fehler?.length ? r.fehler.join(" · ") : "Bibliothek ist aktuell", Boolean(r.fehler?.length));
                  onChanged();
                } finally {
                  setBusy(false);
                }
              }}
            >
              Neu einlesen
            </button>
            <button className="btn danger" disabled={busy || paths.length === 0} onClick={removeAll}>
              Alle entfernen
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Projektordner</h3>
          <p className="desc">
            Hier legt das Programm pro Projekt einen Ordner an (Projektdatei, importierte Pläne, später die Legenden).
            Alle Mitarbeitenden tragen denselben Ordner ein.
          </p>
          <div className="row">
            <input
              className="input"
              style={{ flex: 1, minWidth: 260 }}
              placeholder="T:\_CAD\NovaDat\NovaFirma12\Makro\Legenden"
              value={projectsFolder}
              title={projectsFolder}
              aria-label="Projektordner"
              onChange={(e) => setProjectsFolder(e.target.value)}
            />
            <button
              className="btn"
              disabled={busy || !canPick}
              title={pickHint || "Projektordner im Explorer wählen"}
              onClick={async () => {
                const p = await choose("folder", projectsFolder || status.settings.projects_folder);
                if (!p) return;
                setProjectsFolder(p);
                if (p !== status.settings.projects_folder) save({ projects_folder: p }, "Projektordner gespeichert");
              }}
            >
              Ordner wählen …
            </button>
            <button
              className="btn primary"
              disabled={busy || projectsFolder === status.settings.projects_folder}
              onClick={() => save({ projects_folder: cleanPath(projectsFolder) }, "Projektordner gespeichert")}
            >
              Speichern
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Firmenordner</h3>
          <p className="desc">
            Hier liegen die gemeinsamen Kategorien und Zuordnungen (Datei edeco ag-Legenden-firma.sqlite). Alle Mitarbeitenden tragen
            denselben Ordner ein, zum Beispiel T:\_CAD\NOVA-Legenden. Ohne Eintrag speichert das Programm nur lokal.
          </p>
          <div className="row">
            <input
              className="input"
              style={{ flex: 1, minWidth: 260 }}
              placeholder="T:\_CAD\NOVA-Legenden"
              value={company}
              title={company}
              aria-label="Firmenordner"
              onChange={(e) => setCompany(e.target.value)}
            />
            <button
              className="btn"
              disabled={busy || !canPick}
              title={pickHint || "Firmenordner im Explorer wählen"}
              onClick={async () => {
                const p = await choose("folder", company || status.settings.company_folder);
                if (!p) return;
                setCompany(p);
                if (p !== status.settings.company_folder) save({ company_folder: p }, "Firmenordner gespeichert");
              }}
            >
              Ordner wählen …
            </button>
            <button
              className="btn primary"
              disabled={busy || company === status.settings.company_folder}
              onClick={() => save({ company_folder: cleanPath(company) }, "Firmenordner gespeichert")}
            >
              Speichern
            </button>
          </div>
          {!canPick && <p className="hint">{pickHint}</p>}
          <p className="hint" style={{ wordBreak: "break-all" }}>Aktuelle Datei: {status.company_db}</p>
          {status.company_error && <p className="warn-text">{status.company_error}</p>}
        </div>

        <div className="card">
          <h3>Benutzerschablonen</h3>
          <p className="desc">
            Deine Nova-Schablonen (.n5q). Der Legenden-Editor zeigt sie links unter «Benutzerschablone», und der Vorschlag nimmt ihre
            Bezeichnungen, wenn es keinen Firmentext gibt. {"{nova}"} im Pfad ersetzt das Programm durch die Nova-Version des
            Projekts: 19 für Nova 19.2, 20 für Nova 20. %USERPROFILE% ist dein Benutzerordner.
          </p>
          <div className="row">
            <input className="input" style={{ flex: 1, minWidth: 260 }} value={stencilFolder} title={stencilFolder}
              aria-label="Ordner der Benutzerschablonen" onChange={(e) => setStencilFolder(e.target.value)} />
            <button className="btn primary" disabled={busy || stencilFolder === (status.settings.stencil_folder ?? "")}
              onClick={() => save({ stencil_folder: cleanPath(stencilFolder) }, "Ordner der Benutzerschablonen gespeichert")}>
              Speichern
            </button>
          </div>
          {stencilInfo && (
            <p className="hint" style={{ wordBreak: "break-all" }}>
              Nova {stencilInfo.nova}: {stencilInfo.folder} ·{" "}
              {!stencilInfo.found ? "Ordner nicht gefunden"
                : stencilInfo.files.length ? `${stencilInfo.files.join(", ")} (${stencilInfo.sets.length} Schablonen-Sätze)` : "keine .n5q-Datei im Ordner"}
            </p>
          )}
        </div>

        <CompanyLegendCard canPick={canPick} choose={choose} notify={notify} />

        <CompanyTextsCard notify={notify} />

        <div className="card">
          <h3>Nova-Version (Standard für neue Projekte)</h3>
          <p className="desc">
            Nova-Programmversion, zum Beispiel 19.2 oder 20. Jedes Projekt speichert seine eigene Angabe. Die Angabe ist
            eine Information zum Projekt: Der Import liest heute alle Pläne gleich und prüft die Nova-Version nicht.
            Geprüft ist das Programm mit Nova 19.2 Patch 3, Nova 20 noch nicht.
          </p>
          <div className="row">
            <select
              className="select"
              value={nova}
              onChange={(e) => {
                setNova(e.target.value);
                save({ nova_version: e.target.value }, "Nova-Version gespeichert");
              }}
            >
              <option value="19.2">Nova 19.2</option>
              <option value="20">Nova 20</option>
            </select>
          </div>
        </div>

        <div className="card">
          <h3>DWG-Unterstützung (ODA File Converter)</h3>
          <p className="desc">
            Nur für DWG-Dateien nötig. DXF, N4D und N4M funktionieren ohne. Der Converter ist kostenlos und wird separat von
            der Open Design Alliance installiert.
          </p>
          {status.oda ? (
            <p>
              <span className="badge manual">gefunden</span> {status.oda}
            </p>
          ) : (
            <p>
              <span className="badge warn">nicht installiert</span> DWG-Import und -Export bleiben ausgeschaltet.
              DXF funktioniert ohne Converter.{" "}
              <a href="https://www.opendesign.com/guestfiles/oda_file_converter" target="_blank" rel="noreferrer">ODA File Converter herunterladen</a>.
            </p>
          )}
        </div>

        <div className="card">
          <h3>Info</h3>
          <dl className="kv">
            <dt>Programmversion</dt>
            <dd>{status.version_label}</dd>
            <dt>Benutzer</dt>
            <dd>{status.user}</dd>
            <dt>Lokale Daten</dt>
            <dd>{status.local_home}</dd>
          </dl>
          <div className="section">Begriffe</div>
          <dl className="kv">
            <dt>Programmversion</dt>
            <dd>Version und Build von NOVA-Legenden. Das Update oben ändert nur sie.</dd>
            <dt>Nova-Version</dt>
            <dd>Version des Programms Trimble Nova, zum Beispiel 19.2 oder 20.</dd>
            <dt>Symbol-Datensatz</dt>
            <dd>Nova-Symbolbibliothek, zum Beispiel V1 (2022) oder V2 (2025). Keine Planrevision und keine Nova-Version.</dd>
            <dt>Importversion</dt>
            <dd>Ein gespeicherter Import eines Geschossplans. Jede neue Planversion eines Geschosses ergibt eine weitere.</dd>
          </dl>
        </div>
      </div>
    </div>
  );
}
