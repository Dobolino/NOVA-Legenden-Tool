import { useCallback, useEffect, useRef, useState } from "react";
import { api, Category, ProjectSummary } from "../api";
import { formatDateTime } from "../uiState";
import { Icon, TrashIcon } from "./Icons";
import ProjectView from "./ProjectView";
import { useDialogFocus } from "../useDialogFocus";

interface Props {
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
  onOpenSettings: () => void;
}

export default function ProjectsPage({ categories, notify, onOpenSettings }: Props) {
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [folder, setFolder] = useState("");
  const [folderExists, setFolderExists] = useState(true);
  const [sharedFolder, setSharedFolder] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const [dialog, setDialog] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("modified");

  const load = useCallback(async () => {
    try {
      const res = await api.projects();
      setItems(res.items);
      setFolder(res.folder);
      setFolderExists(res.folder_exists);
      setSharedFolder(res.shared !== false);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }, [notify]);

  useEffect(() => {
    load();
  }, [load]);

  if (open) {
    return (
      <ProjectView
        projectId={open}
        projects={items}
        categories={categories}
        notify={notify}
        onBack={() => {
          setOpen(null);
          load();
        }}
        onOpenProject={(id) => {
          setOpen(id);
          load();
        }}
      />
    );
  }

  const shown = items.filter((p) => `${p.project_number} ${p.name}`.toLocaleLowerCase("de-CH").includes(query.toLocaleLowerCase("de-CH")))
    .sort((a, b) => sort === "name" ? a.name.localeCompare(b.name, "de-CH") : b.modified.localeCompare(a.modified));

  return (
    <div className="page projects-page">
      <div className="page-inner">
        <div className="page-heading">
            <div>
              <div className="eyebrow">Projektübersicht</div>
              <h1>Deine Projekte</h1>
              <p>Pläne verwalten. Symbole zuordnen. Legenden erstellen.</p>
            </div>
            <button className="btn primary" onClick={() => setDialog(true)}>
              <Icon name="plus" size={18} /> Legende erstellen
            </button>
        </div>

        <div className="project-metrics" aria-label="Projektübersicht in Zahlen">
          <div><span>Projekte</span><strong>{items.length}</strong><Icon name="projects" size={22} /></div>
          <div><span>Als Vorlage verfügbar</span><strong>{items.filter((p) => p.use_as_template !== false).length}</strong><Icon name="library" size={22} /></div>
        </div>

        {items.length === 0 ? (
          <div className="card">
            <p className="desc">
              Noch keine Projekte. Klicke auf «Legende erstellen». Den Projektordner änderst du in den{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); onOpenSettings(); }}>Einstellungen</a>.
            </p>
          </div>
        ) : (
          <div className="card project-list">
            <div className="project-list-toolbar">
              <label className="search-field"><Icon name="search" size={18} /><input className="search" aria-label="Projekte suchen" placeholder="Projektname oder Nummer suchen …" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
              <label className="filter-label">Sortieren<select className="select" aria-label="Projekte sortieren" value={sort} onChange={(e) => setSort(e.target.value)}><option value="modified">Zuletzt geändert</option><option value="name">Projektname A–Z</option></select></label>
            </div>
            <div className="table-scroll">
            <table className="list-table">
              <thead>
                <tr>
                  <th>Projekt</th>
                  <th>Nova-Version</th>
                  <th>Geschosse</th>
                  <th>Geändert</th>
                  <th>Angelegt von</th>
                  <th style={{ width: 52 }} />
                </tr>
              </thead>
              <tbody>
                {shown.map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => setOpen(p.id)}>
                    <td>
                      {p.project_number && <span className="hint">{p.project_number} · </span>}
                      <button className="project-open" onClick={(e) => { e.stopPropagation(); setOpen(p.id); }}>{p.name}</button>
                      {p.template_from && <div className="hint">Vorlage: {p.template_from}</div>}
                    </td>
                    <td><span className="badge">Nova {p.nova_version}</span></td>
                    <td>{p.plan_count}</td>
                    <td>{formatDateTime(p.modified)}</td>
                    <td>{p.created_by}</td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        className="btn icon danger"
                        aria-label={`Projekt ${p.name} nach ‚Gelöscht‘ verschieben`}
                        title="Nach ‚Gelöscht‘ verschieben (Ordner _Geloescht, nichts wird endgültig gelöscht)"
                        onClick={async (e) => {
                          e.stopPropagation();
                          if (!window.confirm(`Projekt «${p.name}» in den Ordner _Geloescht verschieben? Nichts wird endgültig gelöscht.`)) return;
                          try {
                            await api.deleteProject(p.id);
                            notify("Projekt nach _Geloescht verschoben");
                            if (open === p.id) setOpen(null);
                            load();
                          } catch (err) {
                            notify((err as Error).message, true);
                          }
                        }}
                      >
                        <TrashIcon />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            {shown.length === 0 && <div className="empty">Keine Projekte für diese Suche.</div>}
            <div className="project-list-footer">{shown.length} von {items.length} Projekten</div>
          </div>
        )}
        <details className="project-location">
          <summary>Projektordner anzeigen</summary>
          <p>{folder}{!folderExists && " (wird beim ersten Projekt angelegt)"}{!sharedFolder && " Nur dieser Computer, bis in den Einstellungen ein gemeinsamer Ordner steht."}</p>
          <button className="btn small" onClick={onOpenSettings}>Ordner in den Einstellungen ändern</button>
        </details>
      </div>
      {dialog && (
        <CreateDialog
          projects={items}
          notify={notify}
          onClose={() => setDialog(false)}
          onDone={(id) => {
            setDialog(false);
            setOpen(id);
            load();
          }}
        />
      )}
    </div>
  );
}

function CreateDialog({
  projects,
  notify,
  onClose,
  onDone,
}: {
  projects: ProjectSummary[];
  notify: (text: string, error?: boolean) => void;
  onClose: () => void;
  onDone: (id: string) => void;
}) {
  const [mode, setMode] = useState<"new" | "existing">(projects.length ? "existing" : "new");
  const [existing, setExisting] = useState(projects[0]?.id ?? "");
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [nova, setNova] = useState("19.2");
  const [template, setTemplate] = useState("");
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  useDialogFocus(dialogRef, onClose, busy);

  async function submit() {
    if (mode === "existing") {
      if (existing) onDone(existing);
      return;
    }
    if (!name.trim()) {
      notify("Bitte einen Projektnamen eingeben", true);
      return;
    }
    setBusy(true);
    try {
      const p = await api.createProject(name.trim(), nova, template || null, number.trim());
      notify(`Projekt «${p.meta.name}» angelegt`);
      onDone(p.id);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div ref={dialogRef} className="modal" role="dialog" aria-modal="true" aria-labelledby="create-project-title" tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h3 id="create-project-title">Legende erstellen</h3>
        <p className="desc">Jede Legende gehört zu einem Projekt.</p>
        <label className="toggle choice">
          <input type="radio" checked={mode === "existing"} disabled={!projects.length} onChange={() => setMode("existing")} />
          Vorhandenes Projekt
        </label>
        {mode === "existing" && (
          <select className="select full" value={existing} onChange={(e) => setExisting(e.target.value)}>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.project_number ? `${p.project_number} · ` : ""}{p.name} (Nova {p.nova_version}, {p.plan_count} Geschosse)
              </option>
            ))}
          </select>
        )}
        <label className="toggle choice">
          <input type="radio" checked={mode === "new"} onChange={() => setMode("new")} />
          Neues Projekt
        </label>
        {mode === "new" && (
          <div className="form-grid">
            <label htmlFor="create-number">Projektnummer</label>
            <input id="create-number" className="input" autoFocus value={number} onChange={(e) => setNumber(e.target.value)} placeholder="z. B. 2026-014" />
            <label htmlFor="create-name">Bezeichnung</label>
            <input id="create-name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Wohn- und Geschäftshaus Basel" />
            <label htmlFor="create-nova">Nova-Version</label>
            <select id="create-nova" className="select" value={nova} onChange={(e) => setNova(e.target.value)}>
              <option value="19.2">Nova 19.2</option>
              <option value="20">Nova 20</option>
            </select>
            <label htmlFor="create-template">Vorlage (Einstellungen und Ebenen)</label>
            <select id="create-template" className="select" value={template} onChange={(e) => setTemplate(e.target.value)}>
              <option value="">keine Vorlage</option>
              {projects.filter((p) => p.use_as_template !== false).map((p) => (
                <option key={p.id} value={p.id}>
                  Einstellungen und Ebenen von «{p.name}»
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn" onClick={onClose}>
            Abbrechen
          </button>
          <button className="btn primary" disabled={busy} onClick={submit}>
            {mode === "new" ? "Projekt anlegen" : "Öffnen"}
          </button>
        </div>
      </div>
    </div>
  );
}
