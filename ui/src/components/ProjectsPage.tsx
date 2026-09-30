import { useCallback, useEffect, useState } from "react";
import { api, Category, ProjectSummary } from "../api";
import { formatDateTime } from "../uiState";
import { TrashIcon } from "./Icons";
import ProjectView from "./ProjectView";

interface Props {
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
  onOpenSettings: () => void;
}

export default function ProjectsPage({ categories, notify, onOpenSettings }: Props) {
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [folder, setFolder] = useState("");
  const [folderExists, setFolderExists] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const [dialog, setDialog] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.projects();
      setItems(res.items);
      setFolder(res.folder);
      setFolderExists(res.folder_exists);
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

  return (
    <div className="page">
      <div className="page-inner">
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <h3>Projekte</h3>
              <p className="desc" style={{ marginBottom: 0 }}>
                Projektordner: {folder}
                {!folderExists && " (wird beim ersten Projekt angelegt)"}
              </p>
            </div>
            <button className="btn primary" onClick={() => setDialog(true)}>
              Legende erstellen
            </button>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="card">
            <p className="desc">
              Noch keine Projekte. Klicke auf «Legende erstellen». Den Projektordner änderst du in den{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); onOpenSettings(); }}>Einstellungen</a>.
            </p>
          </div>
        ) : (
          <div className="card">
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
                {items.map((p) => (
                  <tr key={p.id} className="clickable" onClick={() => setOpen(p.id)}>
                    <td>
                      {p.project_number && <span className="hint">{p.project_number} · </span>}
                      <b>{p.name}</b>
                      {p.template_from && <div className="hint">Vorlage: {p.template_from}</div>}
                    </td>
                    <td>Nova {p.nova_version}</td>
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
        )}
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
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Legende erstellen</h3>
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
            <label>Projektnummer</label>
            <input className="input" autoFocus value={number} onChange={(e) => setNumber(e.target.value)} placeholder="z. B. 2026-014" />
            <label>Bezeichnung</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Wohn- und Geschäftshaus Basel" />
            <label>Nova-Version</label>
            <select className="select" value={nova} onChange={(e) => setNova(e.target.value)}>
              <option value="19.2">Nova 19.2</option>
              <option value="20">Nova 20</option>
            </select>
            <label>Vorlage (Einstellungen und Ebenen)</label>
            <select className="select" value={template} onChange={(e) => setTemplate(e.target.value)}>
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
