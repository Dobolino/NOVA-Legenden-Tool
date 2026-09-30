import { useEffect, useState } from "react";
import { api, DATASET_LABEL, Status, UpdateInfo } from "../api";

interface Props {
  status: Status;
  update: UpdateInfo | null;
  onUpdate: (u: UpdateInfo) => void;
  notify: (text: string, error?: boolean) => void;
  onChanged: () => void;
}

export default function SettingsPage({ status, update, onUpdate, notify, onChanged }: Props) {
  const [paths, setPaths] = useState<string[]>(status.settings.dataset_paths);
  const [newPath, setNewPath] = useState("");
  const [company, setCompany] = useState(status.settings.company_folder);
  const [projectsFolder, setProjectsFolder] = useState(status.settings.projects_folder);
  const [nova, setNova] = useState(status.settings.nova_version);
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

  const cleanPath = (p: string) => p.trim().replace(/^"(.*)"$/, "$1");
  const norm = (p: string) => p.replace(/\//g, "\\").toLowerCase();

  function removeAll() {
    if (!window.confirm("Alle Datensätze aus der Liste entfernen? Die Dateien selbst bleiben unverändert.")) return;
    save({ dataset_paths: [] }, "Alle Datensätze entfernt");
  }

  return (
    <div className="page">
      <div className="page-inner">
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
                  <span>{p}</span>
                  {ds && (
                    <span className="badge up" style={{ flex: "none" }}>
                      {DATASET_LABEL(ds.id)} · {ds.version} · {ds.symbol_count} Symbole
                    </span>
                  )}
                  {!ds && doubled && (
                    <span className="badge warn" style={{ flex: "none" }}>
                      doppelt, übersprungen
                    </span>
                  )}
                  <button
                    className="btn small danger"
                    disabled={busy}
                    onClick={() => save({ dataset_paths: paths.filter((x) => x !== p) }, "Entfernt")}
                  >
                    Entfernen
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
              onChange={(e) => setProjectsFolder(e.target.value)}
            />
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
            Hier liegen die gemeinsamen Kategorien und Zuordnungen (Datei firma.sqlite). Alle Mitarbeitenden tragen
            denselben Ordner ein, zum Beispiel T:\_CAD\NOVA-Legenden. Ohne Eintrag speichert das Programm nur lokal.
          </p>
          <div className="row">
            <input
              className="input"
              style={{ flex: 1, minWidth: 260 }}
              placeholder="T:\_CAD\NOVA-Legenden"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
            <button
              className="btn primary"
              disabled={busy || company === status.settings.company_folder}
              onClick={() => save({ company_folder: cleanPath(company) }, "Firmenordner gespeichert")}
            >
              Speichern
            </button>
          </div>
          <p className="hint">Aktuelle Datei: {status.company_db}</p>
          {status.company_error && <p className="warn-text">{status.company_error}</p>}
        </div>

        <div className="card">
          <h3>Nova-Version</h3>
          <p className="desc">Steuert später das Format für Import und Export. Pro Projekt änderbar (ab Phase 2).</p>
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
            Nur für DWG-Dateien nötig. DXF und N4D funktionieren ohne. Der Converter ist kostenlos und wird separat von
            der Open Design Alliance installiert.
          </p>
          {status.oda ? (
            <p>
              <span className="badge manual">gefunden</span> {status.oda}
            </p>
          ) : (
            <p>
              <span className="badge warn">nicht installiert</span> DWG-Import und -Export bleiben ausgeschaltet.
              Download: opendesign.com → Guest Files → ODA File Converter.
            </p>
          )}
        </div>

        <div className="card">
          <h3>Info</h3>
          <dl className="kv">
            <dt>Version</dt>
            <dd>{status.version_label}</dd>
            <dt>Benutzer</dt>
            <dd>{status.user}</dd>
            <dt>Lokale Daten</dt>
            <dd>{status.local_home}</dd>
          </dl>
        </div>
      </div>
    </div>
  );
}
