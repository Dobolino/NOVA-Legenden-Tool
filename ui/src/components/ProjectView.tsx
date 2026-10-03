import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Category, DATASET_LABEL, FamilyItem, ProjectDetail, ProjectSummary, Review, Suggestion, UnknownElement } from "../api";
import { planFiles } from "../floors";
import { formatDateTime, layerStateText, plansOpen, rememberPlansOpen } from "../uiState";
import ChangesTab, { changeHint } from "./ChangesTab";
import LegendEditor from "./LegendEditor";
import ImportDialog from "./ImportDialog";
import ReviewPanel from "./ReviewPanel";
import Menu from "./Menu";
import { TrashIcon } from "./Icons";
import { useNavigation } from "../Navigation";

interface Props {
  projectId: string;
  projects: ProjectSummary[];
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
  onBack: () => void;
  onOpenProject: (id: string) => void;
}

type Tab = "list" | "legend" | "unknown" | "layers" | "ignored" | "changes" | "review";

interface ImportStatus {
  kind: "busy" | "ok" | "error";
  text: string;
}

const DETACH_TEXT = "Entfernt nur die gespeicherte Plandatei. Importierte Anzahlen und Versionen bleiben erhalten.";

export default function ProjectView({ projectId, projects, categories, notify, onBack, onOpenProject }: Props) {
  const { navigate } = useNavigation();
  const loadGeneration = useRef(0);
  const [data, setData] = useState<ProjectDetail | null>(null);
  const [tab, setTab] = useState<Tab>("list");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ files: File[]; planId?: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const reimportRef = useRef<HTMLInputElement>(null);
  const [reimportPlan, setReimportPlan] = useState<number | null>(null);
  const [number, setNumber] = useState("");
  const [title, setTitle] = useState("");
  const [dragPlan, setDragPlan] = useState<number | null>(null);
  const [dropHot, setDropHot] = useState(false);
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const [open, setOpen] = useState(true);
  const [allCategories, setAllCategories] = useState(false);
  const [review, setReview] = useState<Review | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const reviewGeneration = useRef(0);

  const loadReview = useCallback(async () => {
    const generation = ++reviewGeneration.current;
    setReviewLoading(true);
    try {
      const r = await api.review(projectId);
      if (generation === reviewGeneration.current) setReview(r);
    } catch {
      /* the check is optional; the tab shows «Noch nicht geprüft» */
    } finally {
      if (generation === reviewGeneration.current) setReviewLoading(false);
    }
  }, [projectId]);

  // check again after every change of the project and when the tab is opened
  useEffect(() => {
    if (data) loadReview();
  }, [data, loadReview]);
  useEffect(() => {
    if (tab === "review") loadReview();
  }, [tab, loadReview]);

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    try {
      const next = await api.project(projectId);
      if (generation !== loadGeneration.current) return;
      setData(next);
      setNumber(next.meta.project_number || "");
      setTitle(next.meta.name || "");
      setOpen(plansOpen(projectId, next.plans.length));
    } catch (e) {
      if (generation === loadGeneration.current) notify((e as Error).message, true);
    }
  }, [projectId, notify]);

  useEffect(() => {
    setImportStatus(null);
    load();
    return () => { loadGeneration.current += 1; };
  }, [load]);

  async function run<T>(action: () => Promise<T>, ok?: string): Promise<T | undefined> {
    setBusy(true);
    try {
      const result = await action();
      if (ok) notify(ok);
      return result;
    } catch (e) {
      notify((e as Error).message, true);
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  /** New plan version of one floor (per-floor action). New floors go through the import dialog. */
  function openImport(list: File[]) {
    const files = planFiles(list);
    if (!files.length) {
      notify("Nur DXF-, DWG-, N4D- oder N4M-Dateien können importiert werden.", true);
      return;
    }
    setPending({ files });
  }

  function toggleOpen(next: boolean) {
    setOpen(next);
    rememberPlansOpen(projectId, next);
  }

  async function reorder(ids: number[]) {
    const r = await run(() => api.reorderPlans(projectId, ids));
    if (r) setData(r);
  }

  const catById = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c])), [categories]);
  const colorById = useMemo(
    () => Object.fromEntries((data?.category_colors ?? []).map((c) => [c.id, c])),
    [data],
  );

  if (!data || data.id !== projectId) {
    return (
      <div className="page">
        <div className="page-inner">
          <div className="hint">lädt …</div>
        </div>
      </div>
    );
  }

  const plans = data.plans;
  const planTotals = Object.fromEntries(plans.map((p) => [p.id, data.rows.reduce((n, r) => n + (r.counts[p.id] ?? 0), 0)]));
  const changeCount = plans.reduce(
    (n, p) => n + (p.change_summary ? p.change_summary.neu + p.change_summary.weg + p.change_summary.geaendert : 0),
    0,
  );
  const toChoose = data.category_colors.filter((c) => c.state === "waehlen").length;
  const usedCats = data.category_colors.filter((c) => c.used > 0 || c.manual);
  const shownCats = allCategories ? data.category_colors : usedCats;
  const headDirty = number !== (data.meta.project_number || "") || title !== data.meta.name;

  // Group the overall list by the first category of each row
  const groups: { cat: Category | null; rows: typeof data.rows }[] = [];
  for (const row of data.rows) {
    const cat = catById[row.categories[0]] ?? null;
    const last = groups[groups.length - 1];
    if (last && last.cat?.id === cat?.id) last.rows.push(row);
    else groups.push({ cat, rows: [row] });
  }

  async function saveHead() {
    if (!title.trim()) {
      notify("Bezeichnung fehlt", true);
      return;
    }
    await navigate(async () => {
      const r = await run(
        () => api.updateProject(projectId, { name: title.trim(), project_number: number.trim() }),
        "Projekt gespeichert",
      );
      if (r) {
        if (r.id !== projectId) onOpenProject(r.id);
        else setData(r);
      }
    });
  }

  return (
    <div className="page">
      <div className="page-inner full">
        <div className="card project-head">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <button className="btn small" onClick={() => navigate(onBack)}>
              ← Alle Projekte
            </button>
            <label className="filter-label">
              Projekt wechseln
              <select
                className="select"
                style={{ maxWidth: 320 }}
                value={projectId}
                title="Öffnet ein anderes Projekt aus dem Projektordner"
                onChange={(e) => {
                  const id = e.target.value;
                  navigate(() => onOpenProject(id));
                }}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.project_number ? `${p.project_number} · ` : ""}
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <h2 className="project-title">
            {data.meta.project_number && <span className="number">{data.meta.project_number}</span>}
            {data.meta.name}
          </h2>
          <div className="head-fields">
            <label className="field">
              <span>Projektnummer</span>
              <input
                className="input"
                style={{ width: 150 }}
                value={number}
                onChange={(e) => setNumber(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && headDirty && saveHead()}
              />
            </label>
            <label className="field grow">
              <span>Bezeichnung</span>
              <input
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && headDirty && saveHead()}
              />
            </label>
            <button className="btn primary" disabled={busy || !headDirty} onClick={saveHead}>
              Speichern
            </button>
            <label className="field">
              <span>Nova-Version des Projekts</span>
              <select
                className="select"
                value={data.meta.nova_version}
                title="Gespeicherte Angabe zum Projekt. Keine Zusage, dass der Import versionsabhängig arbeitet."
                onChange={async (e) => {
                  const r = await run(() => api.updateProject(projectId, { nova_version: e.target.value }), "Nova-Version gespeichert");
                  if (r) setData(r);
                }}
              >
                <option value="19.2">Nova 19.2</option>
                <option value="20">Nova 20</option>
              </select>
            </label>
          </div>
          <div className="head-actions">
            <button
              className="btn small"
              disabled={busy}
              onClick={async () => {
                const name = window.prompt("Name des duplizierten Projekts", `${data.meta.name} Kopie`);
                if (!name) return;
                await navigate(async () => {
                  const r = await run(() => api.copyProject(projectId, name), "Projekt dupliziert");
                  if (r) onOpenProject(r.id);
                });
              }}
            >
              Projekt duplizieren
            </button>
            <a
              className="btn small"
              href={api.exportUrl(projectId)}
              download={data.export_name}
              onClick={(e) => {
                e.preventDefault();
                navigate(() => {
                  const link = document.createElement("a");
                  link.href = api.exportUrl(projectId);
                  link.download = data.export_name;
                  document.body.appendChild(link);
                  link.click();
                  link.remove();
                });
              }}
              title={`Speichert ${data.export_name}: Projektdatei projekt.nlproj und eine Plandatei pro Geschoss.`}
            >
              Projekt als ZIP exportieren
            </a>
            <button
              className="btn small"
              disabled={busy}
              title="Ändert nur, ob das Projekt beim Anlegen eines neuen Projekts als Vorlage erscheint."
              onClick={async () => {
                const next = data.meta.use_as_template === false;
                const r = await run(
                  () => api.updateProject(projectId, { use_as_template: next }),
                  next ? "Wieder als Vorlage wählbar" : "Nicht mehr als Vorlage angeboten",
                );
                if (r) setData(r);
              }}
            >
              {data.meta.use_as_template === false ? "Als Vorlage anbieten" : "Vorlage ausblenden"}
            </button>
            <span className="sep" />
            <button
              className="btn icon danger"
              disabled={busy}
              aria-label="Projekt nach ‚Gelöscht‘ verschieben"
              title="Nach ‚Gelöscht‘ verschieben: der Projektordner kommt nach _Geloescht, nichts wird endgültig gelöscht."
              onClick={async () => {
                if (!window.confirm(`Projekt «${data.meta.name}» in den Ordner _Geloescht verschieben? Nichts wird endgültig gelöscht.`)) return;
                await navigate(async () => {
                  const r = await run(() => api.deleteProject(projectId), "Projekt nach _Geloescht verschoben");
                  if (r) onBack();
                });
              }}
            >
              <TrashIcon />
            </button>
          </div>
          <div className="muted-line" title={data.folder}>
            Ordner: {data.folder} · angelegt {data.meta.created_at?.slice(0, 10)} von {data.meta.created_by}
            {data.meta.template_from ? ` · Vorlage: ${data.meta.template_from}` : ""}
          </div>
        </div>

        <details
          className={`card fold ${dropHot ? "drop-hot" : ""}`}
          open={open || plans.length === 0}
          onToggle={(e) => {
            const next = (e.currentTarget as HTMLDetailsElement).open;
            if (next !== (open || plans.length === 0)) toggleOpen(next);
          }}
          onDragOver={(e) => {
            if (![...e.dataTransfer.types].includes("Files")) return;
            e.preventDefault();
            setDropHot(true);
          }}
          onDragLeave={() => setDropHot(false)}
          onDrop={(e) => {
            if (!e.dataTransfer.files?.length) return;
            e.preventDefault();
            setDropHot(false);
            openImport([...e.dataTransfer.files]);
          }}
        >
          <summary onClick={(e) => plans.length === 0 && e.preventDefault()}>
            Pläne · {plans.length === 1 ? "1 Geschoss" : `${plans.length} Geschosse`}
            {!open && plans.length > 0 && <span className="hint">Dateien hierher ziehen importiert Geschosse (mehrere möglich)</span>}
            {importStatus?.kind === "busy" && <span className="hint">· importiert …</span>}
          </summary>
          <p className="desc">
            Ein Plan pro Geschoss. Datei hierher ziehen oder unten wählen. Formate: DXF, N4D und N4M (Nova-Modell), DWG mit ODA File
            Converter. Geschosse sortierst du durch Ziehen am Griff ⠿ oder mit ↑ ↓.
          </p>
          {plans.length > 0 && (
            <div className="table-scroll">
              <table className="list-table">
                <thead>
                  <tr>
                    <th>Geschoss</th>
                    <th>Plandatei</th>
                    <th className="type-col">Typ</th>
                    <th>Letzter Import</th>
                    <th className="num-col">Apparate</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {plans.map((p, i) => (
                    <tr
                      key={p.id}
                      draggable
                      onDragStart={() => setDragPlan(p.id)}
                      onDragOver={(e) => {
                        if ([...e.dataTransfer.types].includes("Files")) return;
                        e.preventDefault();
                      }}
                      onDrop={(e) => {
                        if (e.dataTransfer.files?.length || dragPlan == null || dragPlan === p.id) return;
                        e.preventDefault();
                        const ids = plans.map((x) => x.id);
                        ids.splice(ids.indexOf(dragPlan), 1);
                        ids.splice(i, 0, dragPlan);
                        setDragPlan(null);
                        reorder(ids);
                      }}
                    >
                      <td style={{ whiteSpace: "nowrap" }}>
                        <span className="handle" title="Ziehen zum Sortieren" aria-hidden>
                          ⠿
                        </span>
                        <b>{p.name}</b>
                      </td>
                      <td>
                        {p.file_name ? (
                          <span title={p.file_name}>{p.file_name}</span>
                        ) : (
                          <span className="hint">Plandatei entfernt</span>
                        )}
                        <div className="hint">
                          {p.versions === 1 ? "1 Importversion" : `${p.versions} Importversionen`}
                          {p.versions > 1 && p.change_summary ? ` · ${changeHint(p.change_summary)}` : ""}
                        </div>
                      </td>
                      <td className="type-col">{p.format ? p.format.toUpperCase() : ""}</td>
                      <td>
                        {p.imported_at ? formatDateTime(p.imported_at) : ""}
                        <div className="hint">{p.imported_by}</div>
                      </td>
                      <td className="num-col">{planTotals[p.id]}</td>
                      <td className="plan-actions">
                        <div>
                          <button
                            className="btn small"
                            disabled={busy}
                            title="Geänderten Plan dieses Geschosses einlesen. Die bisherigen Importe bleiben für den Vergleich erhalten."
                            onClick={() => {
                              setReimportPlan(p.id);
                              reimportRef.current?.click();
                            }}
                          >
                            Neue Planversion importieren
                          </button>
                          <button
                            className="btn small"
                            disabled={busy || i === 0}
                            aria-label={`${p.name} nach oben`}
                            title="Nach oben"
                            onClick={() => {
                              const ids = plans.map((x) => x.id);
                              [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
                              reorder(ids);
                            }}
                          >
                            ↑
                          </button>
                          <button
                            className="btn small"
                            disabled={busy || i === plans.length - 1}
                            aria-label={`${p.name} nach unten`}
                            title="Nach unten"
                            onClick={() => {
                              const ids = plans.map((x) => x.id);
                              [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]];
                              reorder(ids);
                            }}
                          >
                            ↓
                          </button>
                          <Menu label="Weitere Aktionen" disabled={busy}>
                            <button
                              onClick={async () => {
                                const name = window.prompt("Name des Geschosses", p.name);
                                if (!name || name === p.name) return;
                                const r = await run(() => api.renamePlan(projectId, p.id, name), "Geschoss umbenannt");
                                if (r) setData(r);
                              }}
                            >
                              Geschoss umbenennen
                            </button>
                            <button
                              className="danger"
                              disabled={!p.file_name}
                              onClick={async () => {
                                if (!window.confirm(`Datei von «${p.name}» entfernen?\n\n${DETACH_TEXT}`)) return;
                                const r = await run(() => api.detachPlan(projectId, p.id), "Plandatei entfernt, Anzahlen bleiben");
                                if (r) setData(r);
                              }}
                            >
                              Datei entfernen
                              <span className="hint">{p.file_name ? DETACH_TEXT : "Keine Plandatei gespeichert."}</span>
                            </button>
                          </Menu>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <input
            ref={reimportRef}
            type="file"
            accept=".dxf,.dwg,.n4d,.n4m"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f && reimportPlan) setPending({ files: [f], planId: reimportPlan });
              e.target.value = "";
            }}
          />
          <div className="head-fields" style={{ marginTop: 12 }}>
            <input
              ref={fileRef}
              type="file"
              accept=".dxf,.dwg,.n4d,.n4m"
              multiple
              style={{ display: "none" }}
              onChange={(e) => {
                const list = [...(e.target.files ?? [])];
                e.target.value = "";
                if (list.length) openImport(list);
              }}
            />
            <button className="btn primary" disabled={busy} onClick={() => fileRef.current?.click()}>
              Pläne importieren …
            </button>
            <span className="hint" style={{ lineHeight: "34px" }}>
              Mehrere DXF, DWG, N4D oder N4M auf einmal: wählen oder hierher ziehen. Danach Geschossnamen prüfen.
            </span>
          </div>
          {importStatus && (
            <div className={`import-status ${importStatus.kind}`} role="status" aria-live="polite">
              <b>{importStatus.kind === "busy" ? "Läuft: " : importStatus.kind === "ok" ? "Fertig: " : "Fehler: "}</b>
              {importStatus.text}
              {importStatus.kind !== "busy" && (
                <>
                  {" "}
                  <button className="btn small" onClick={() => setImportStatus(null)}>
                    Ausblenden
                  </button>
                </>
              )}
            </div>
          )}
        </details>

        {pending && (
          <ImportDialog
            projectId={projectId}
            files={pending.files}
            planId={pending.planId}
            plans={plans}
            onClose={() => setPending(null)}
            onDone={(result, summary) => {
              if (result) setData(result);
              setImportStatus({
                kind: summary.failed ? "error" : "ok",
                text: summary.failed
                  ? `${summary.ok} importiert, ${summary.failed} fehlgeschlagen. Details im Fenster.`
                  : `${summary.ok} ${summary.ok === 1 ? "Datei" : "Dateien"} importiert: ${summary.text}.`,
              });
              if (summary.ok) notify(`${summary.ok} ${summary.ok === 1 ? "Plan" : "Pläne"} importiert`);
            }}
          />
        )}

        {plans.length > 0 && (
          <div className="card">
            <div className="subtabs" role="tablist">
              <button
                className={`tab ${tab === "list" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("list"))}
                title={`${data.rows.length} Zeilen: eine Zeile pro Apparat (Symbolfamilie) über alle Geschosse`}
              >
                Gesamtliste ({data.rows.length})
              </button>
              <button
                className={`tab ${tab === "legend" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("legend"))}
                title="Legenden-Editor: Symbole anordnen, Texte bearbeiten, Abschnitte nach Kategorien"
              >
                Legende
              </button>
              <button
                className={`tab ${tab === "changes" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("changes"))}
                title="Vergleich von Importversionen. Die Zahl zählt geänderte Zeilen zum vorigen Import, über alle Geschosse."
              >
                Änderungen{changeCount ? ` (${changeCount})` : ""}
              </button>
              <button
                className={`tab ${tab === "unknown" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("unknown"))}
                title={`${data.unknown.length} Elementarten ohne sichere Erkennung`}
              >
                Unbekannt ({data.unknown.length})
              </button>
              <button
                className={`tab ${tab === "layers" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("layers"))}
                title={`${toChoose} verwendete Kategorien ohne passende Ebene · ${data.layers.length} Ebenen aus den importierten Plänen`}
              >
                Ebenen und Farben{toChoose ? ` · ${toChoose} Ebene wählen` : ""}
              </button>
              <button
                className={`tab ${tab === "ignored" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("ignored"))}
                title={`${data.ignored.length} Elementarten, die nicht als Apparat zählen (Leitungen, Masse, Beschriftungen, von Hand ignoriert)`}
              >
                Nicht berücksichtigt ({data.ignored.length})
              </button>
              <button
                className={`tab ${tab === "review" ? "active" : ""}`}
                onClick={() => navigate(() => setTab("review"))}
                title="Was vor der Weitergabe der Legende offen ist"
              >
                Prüfung
                {review && review.blocks > 0 && <span className="tab-dot">{review.blocks}</span>}
                {review?.ready && <span className="ok-text"> ✓</span>}
              </button>
              {tab !== "legend" && (
                <button className="btn primary tabs-end" onClick={() => navigate(() => setTab("legend"))} title="Legenden-Editor öffnen">
                  Legende bearbeiten
                </button>
              )}
            </div>

            {tab === "list" && (
              <>
              <div className="table-scroll sticky">
                <table className="list-table summary">
                  <thead>
                    <tr>
                      <th className="stick stick-1" />
                      <th className="stick stick-2">Symbol</th>
                      <th>Code · Symbol-Datensatz</th>
                      {plans.map((p) => (
                        <th key={p.id} className="num-col plan-col" title={p.name}>
                          {p.name}
                        </th>
                      ))}
                      <th className="num-col">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groups.map((g) => {
                      const info = g.cat ? colorById[g.cat.id] : undefined;
                      return (
                        <GroupRows
                          key={g.cat?.id ?? "none"}
                          title={g.cat?.title ?? "Ohne Kategorie"}
                          color={info?.color || undefined}
                          layer={info?.layer || ""}
                          state={info ? layerStateText(info).text : ""}
                          colSpan={4 + plans.length}
                          picker={
                            g.cat ? (
                              <LayerSelect
                                value={info?.manual ? info.layer : ""}
                                layers={data.layers}
                                disabled={busy}
                                label={`Ebene für ${g.cat.title}`}
                                onChange={async (layer) => {
                                  const r = await run(() => api.setCategoryLayer(projectId, g.cat!.id, layer));
                                  if (r) setData(r);
                                }}
                              />
                            ) : undefined
                          }
                        >
                          {g.rows.map((r) => (
                            <tr key={r.family_key}>
                              <td className="stick stick-1">
                                <div className="mini-pic">
                                  {r.svg ? (
                                    <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: r.svg }} />
                                  ) : (
                                    <span className="hint" title="Keine Symbolvorschau verfügbar. Das Symbol ist erkannt.">
                                      –
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="stick stick-2">
                                <b>{r.title}</b>
                                {r.names.length > 0 && <div className="hint">im Plan: {r.names.join(", ")}</div>}
                              </td>
                              <td>
                                {r.item}
                                <div className="hint">{r.datasets.map(DATASET_LABEL).join(", ")}</div>
                              </td>
                              {plans.map((p) => (
                                <td key={p.id} className="num-col plan-col">
                                  {r.counts[p.id] ?? ""}
                                </td>
                              ))}
                              <td className="num-col">
                                <b>{r.total}</b>
                                {r.total === 0 && r.sources.length > 0 && (
                                  <>
                                    {" "}
                                    <button
                                      className="btn small danger"
                                      disabled={busy}
                                      title="Entfernt die Zeile mit Total 0 aus den aktuellen Importen"
                                      onClick={async () => {
                                        const next = await run(() => api.deleteRows(projectId, r.sources), "Zeile gelöscht");
                                        if (next) setData(next);
                                      }}
                                    >
                                      Zeile löschen
                                    </button>
                                  </>
                                )}
                              </td>
                            </tr>
                          ))}
                        </GroupRows>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              </>
            )}

            {tab === "legend" && (
              <LegendEditor key={projectId} projectId={projectId} data={data} categories={categories} notify={notify} />
            )}

            {tab === "changes" && (
              <ChangesTab
                projectId={projectId}
                stamp={plans.map((p) => `${p.id}:${p.current_version}:${p.versions}`).join(",")}
                notify={notify}
              />
            )}

            {tab === "unknown" && (
              <UnknownList projectId={projectId} plans={plans} items={data.unknown} notify={notify} onChanged={load} />
            )}

            {tab === "layers" && (
              <>
                <p className="desc">
                  Jede Kategorie behält ihre Legendenebene. Für die Farbe sucht das Programm in den Plänen zuerst
                  denselben Ebenennamen, danach den Namensteil nach der BKP-Nummer (E_232.5_Licht passt zu E_Licht,
                  E_233_Leuchten nicht). Bei mehreren Treffern zählt die Ebene mit den meisten Apparaten. Eine manuell
                  gewählte Ebene gilt nur für dieses Projekt.
                </p>
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                  <span className="hint">
                    {allCategories
                      ? `Alle ${data.category_colors.length} Kategorien`
                      : `${usedCats.length} Kategorien mit Apparaten in den aktuellen Importen`}
                    {toChoose ? ` · ${toChoose} brauchen eine Ebene` : " · keine offene Entscheidung"}
                  </span>
                  <label className="toggle">
                    <input type="checkbox" checked={allCategories} onChange={(e) => setAllCategories(e.target.checked)} />
                    Alle Kategorien anzeigen
                  </label>
                </div>
                {shownCats.length === 0 ? (
                  <div className="empty">Keine Kategorie hat Apparate in den aktuellen Importen.</div>
                ) : (
                  <div className="table-scroll">
                    <table className="list-table">
                      <thead>
                        <tr>
                          <th>Kategorie</th>
                          <th>Zustand</th>
                          <th>Farbe</th>
                          <th>Ebene für dieses Projekt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shownCats.map((c) => {
                          const st = layerStateText(c);
                          return (
                            <tr key={c.id}>
                              <td>
                                <b>{c.title}</b>
                                <div className="hint">
                                  Legendenebene: {c.legend_layer || "keine"} ·{" "}
                                  {c.used ? `${c.used} Apparate` : "keine Apparate"}
                                </div>
                              </td>
                              <td>
                                <span className={`status ${st.cls}`}>{st.text}</span>
                                {st.detail && <div className="hint">{st.detail}</div>}
                              </td>
                              <td style={{ whiteSpace: "nowrap" }}>
                                {c.color ? (
                                  <>
                                    <span className="swatch big" style={{ background: c.color }} />{" "}
                                    <span className="hint">{c.color}</span>
                                  </>
                                ) : (
                                  <>
                                    <span className="swatch big none" />{" "}
                                    <span className="hint">{c.layer && c.no_color ? "ohne Farbangabe" : "keine Farbe"}</span>
                                  </>
                                )}
                              </td>
                              <td>
                                <LayerSelect
                                  value={c.manual ? c.layer : ""}
                                  layers={data.layers}
                                  disabled={busy}
                                  label={`Ebene für ${c.title}`}
                                  onChange={async (layer) => {
                                    const next = await run(() => api.setCategoryLayer(projectId, c.id, layer));
                                    if (next) setData(next);
                                  }}
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                <h4 style={{ margin: "20px 0 6px" }}>Ebenen aus den Plänen ({data.layers.length})</h4>
                <p className="hint" style={{ marginTop: 0 }}>
                  Alle Ebenen der importierten Pläne mit Farbe und Linienart, wie sie in der Datei stehen.
                </p>
                <div className="table-scroll">
                  <table className="list-table">
                    <thead>
                      <tr>
                        <th>Farbe</th>
                        <th>Ebene</th>
                        <th>Linienart</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.layers.map((l) => (
                        <tr key={l.name}>
                          <td style={{ whiteSpace: "nowrap" }}>
                            <span className={`swatch big ${l.color ? "" : "none"}`} style={l.color ? { background: l.color } : undefined} />{" "}
                            <span className="hint">{l.color || "ohne Farbangabe"}</span>
                          </td>
                          <td style={{ wordBreak: "break-word" }}>{l.name}</td>
                          <td>{l.linetype}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {tab === "review" && (
              <ReviewPanel review={review} loading={reviewLoading} onRefresh={loadReview} onOpen={(target) => navigate(() => setTab(target))} />
            )}

            {tab === "ignored" && (
              <table className="list-table">
                <thead>
                  <tr>
                    <th>Element</th>
                    <th>Grund</th>
                    <th className="num-col">Anzahl</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.ignored.map((g) => (
                    <tr key={g.source_key}>
                      <td>{g.name}</td>
                      <td className="hint">{g.manual ? "von Hand ignoriert (gilt für die ganze Firma)" : g.reason}</td>
                      <td className="num-col">{g.total}</td>
                      <td style={{ textAlign: "right" }}>
                        {g.manual && (
                          <button
                            className="btn small"
                            onClick={async () => {
                              await run(() => api.setMapping(g.source_key, null), "Wird wieder berücksichtigt");
                              load();
                            }}
                          >
                            Wieder berücksichtigen
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function LayerSelect({
  value,
  layers,
  disabled,
  label,
  onChange,
}: {
  value: string;
  layers: ProjectDetail["layers"];
  disabled?: boolean;
  label: string;
  onChange: (layer: string | null) => void;
}) {
  return (
    <select
      className="select"
      style={{ maxWidth: 280 }}
      value={value}
      disabled={disabled}
      aria-label={label}
      title={value ? `Manuell: ${value}. «automatisch» sucht wieder nach dem Namen.` : "automatisch: passender Ebenenname"}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">automatisch</option>
      {layers.map((l) => (
        <option key={l.name} value={l.name}>
          {l.name}
          {l.color ? "" : " (ohne Farbangabe)"}
        </option>
      ))}
    </select>
  );
}

function GroupRows({
  title,
  color,
  layer,
  state,
  colSpan,
  picker,
  children,
}: {
  title: string;
  color?: string;
  layer: string;
  state: string;
  colSpan: number;
  picker?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <>
      <tr className="group-row">
        <td colSpan={colSpan}>
          <div className="row" style={{ position: "sticky", left: 8, display: "inline-flex" }}>
            <span className={`swatch ${color ? "" : "none"}`} style={color ? { background: color } : undefined} title={`${layer} ${color ?? ""}`} />
            <span>{title}</span>
            {state && <span className="hint">· {state}</span>}
            {picker}
          </div>
        </td>
      </tr>
      {children}
    </>
  );
}

function UnknownList({
  projectId,
  plans,
  items,
  notify,
  onChanged,
}: {
  projectId: string;
  plans: ProjectDetail["plans"];
  items: UnknownElement[];
  notify: (text: string, error?: boolean) => void;
  onChanged: () => void;
}) {
  if (!items.length) return <div className="empty">Alle Elemente sind erkannt.</div>;
  return (
    <div className="unknown-list">
      <p className="desc">
        Wähle für jedes Element das passende Symbol. Die Entscheidung gilt für die ganze Firma und bei jedem weiteren
        Import automatisch.
      </p>
      {items.map((u) => (
        <UnknownCard key={u.source_key} projectId={projectId} plans={plans} item={u} notify={notify} onChanged={onChanged} />
      ))}
    </div>
  );
}

function UnknownCard({
  projectId,
  plans,
  item,
  notify,
  onChanged,
}: {
  projectId: string;
  plans: ProjectDetail["plans"];
  item: UnknownElement;
  notify: (text: string, error?: boolean) => void;
  onChanged: () => void;
}) {
  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<FamilyItem[]>([]);

  useEffect(() => {
    api
      .suggestions(projectId, item.source_key)
      .then((r) => setSuggestions(r.items))
      .catch((e) => notify((e as Error).message, true));
  }, [projectId, item.source_key, notify]);

  useEffect(() => {
    if (search.trim().length < 2) {
      setResults([]);
      return;
    }
    const h = window.setTimeout(() => {
      api
        .families({ q: search, category: "", dataset: "", mounting: "", all_variants: true })
        .then((r) => setResults(r.items.slice(0, 12)))
        .catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(h);
  }, [search]);

  async function choose(symbolKey: string, label: string) {
    try {
      await api.setMapping(item.source_key, symbolKey, item.name);
      notify(symbolKey === "__ignore__" ? `«${item.name}» wird ignoriert` : `«${item.name}» = ${label}`);
      onChanged();
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  return (
    <div className="unknown-card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <b>{item.name || "(ohne Namen)"}</b>
          <div className="hint">
            {item.item && `Code ${item.item} · `}
            {item.graphic_name && `Grafik «${item.graphic_name}» · `}
            {plans
              .filter((p) => item.counts[p.id])
              .map((p) => `${p.name}: ${item.counts[p.id]}`)
              .join(", ")}{" "}
            · Ebenen: {Object.keys(item.layers).join(", ")}
          </div>
        </div>
        <button className="btn small" onClick={() => choose("__ignore__", "")}>
          Kein Apparat (ignorieren)
        </button>
      </div>
      <div className="suggestions">
        {suggestions === null && <span className="hint">Vorschläge werden berechnet …</span>}
        {suggestions?.map((s) => (
          <button
            key={s.symbol_key}
            className="suggestion"
            onClick={() => choose(s.symbol_key, s.name)}
            title={Object.entries(s.parts).map(([k, v]) => `${k} ${v} %`).join(" · ")}
          >
            <div className="pic">
              {s.svg ? <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: s.svg }} /> : "–"}
            </div>
            <div className="name">{s.name}</div>
            <div className="hint">
              {s.item} · {DATASET_LABEL(s.dataset)}
            </div>
            <div className="score">{s.score} %</div>
          </button>
        ))}
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <input
          className="input"
          style={{ flex: 1 }}
          placeholder="Anderes Symbol suchen (Name oder Code)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {results.length > 0 && (
        <div className="suggestions">
          {results.map((r) => (
            <button key={r.id} className="suggestion" onClick={() => choose(r.representative.key, r.representative.name)}>
              <div className="pic">
                {r.representative.svg ? (
                  <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: r.representative.svg }} />
                ) : (
                  "–"
                )}
              </div>
              <div className="name">{r.representative.name}</div>
              <div className="hint">
                {r.representative.item} · {DATASET_LABEL(r.representative.dataset)}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
