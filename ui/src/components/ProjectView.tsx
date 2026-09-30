import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Category, DATASET_LABEL, FamilyItem, ProjectDetail, ProjectSummary, Suggestion, UnknownElement } from "../api";

interface Props {
  projectId: string;
  projects: ProjectSummary[];
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
  onBack: () => void;
  onOpenProject: (id: string) => void;
}

type Tab = "list" | "unknown" | "layers" | "ignored";

const MOUNT_ORDER = ["UP", "NUP", "AP", "NAP", "EB", "-"];

export default function ProjectView({ projectId, projects, categories, notify, onBack, onOpenProject }: Props) {
  const [data, setData] = useState<ProjectDetail | null>(null);
  const [tab, setTab] = useState<Tab>("list");
  const [busy, setBusy] = useState(false);
  const [planName, setPlanName] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const reimportRef = useRef<HTMLInputElement>(null);
  const [reimportPlan, setReimportPlan] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.project(projectId));
    } catch (e) {
      notify((e as Error).message, true);
    }
  }, [projectId, notify]);

  useEffect(() => {
    load();
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

  async function importFile(file: File, planId?: number) {
    const name = planId ? "" : planName.trim() || file.name.replace(/\.[^.]+$/, "");
    const result = await run(() => api.importPlan(projectId, name, file, planId), `«${file.name}» importiert`);
    if (result) {
      setData(result);
      setPlanName("");
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const catById = useMemo(() => Object.fromEntries(categories.map((c) => [c.id, c])), [categories]);
  const layerColor = useMemo(
    () => Object.fromEntries((data?.layers ?? []).map((l) => [l.name, l.color])),
    [data],
  );

  if (!data) {
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

  // Group the overall list by the first category of each row
  const groups: { cat: Category | null; rows: typeof data.rows }[] = [];
  for (const row of data.rows) {
    const cat = catById[row.categories[0]] ?? null;
    const last = groups[groups.length - 1];
    if (last && last.cat?.id === cat?.id) last.rows.push(row);
    else groups.push({ cat, rows: [row] });
  }

  return (
    <div className="page">
      <div className="page-inner wide">
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <button className="btn small" onClick={onBack}>
                ← Alle Projekte
              </button>
              <h2 style={{ margin: "10px 0 2px" }}>{data.meta.name}</h2>
              <div className="hint">
                {data.folder} · angelegt {data.meta.created_at?.slice(0, 10)} von {data.meta.created_by}
                {data.meta.template_from ? ` · Vorlage: ${data.meta.template_from}` : ""}
              </div>
            </div>
            <div className="row">
              <select
                className="select"
                value={data.meta.nova_version}
                title="Nova-Version des Projekts"
                onChange={async (e) => {
                  const r = await run(() => api.updateProject(projectId, { nova_version: e.target.value }), "Nova-Version gespeichert");
                  if (r) setData(r);
                }}
              >
                <option value="19.2">Nova 19.2</option>
                <option value="20">Nova 20</option>
              </select>
              <select
                className="select"
                value={projectId}
                title="Anderes Projekt öffnen"
                onChange={(e) => onOpenProject(e.target.value)}
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                className="btn"
                disabled={busy}
                onClick={async () => {
                  const name = window.prompt("Neuer Projektname", data.meta.name);
                  if (!name || name === data.meta.name) return;
                  const r = await run(() => api.updateProject(projectId, { name }), "Projekt umbenannt");
                  if (r) onOpenProject(r.id);
                }}
              >
                Umbenennen
              </button>
              <button
                className="btn"
                disabled={busy}
                onClick={async () => {
                  const name = window.prompt("Name der Kopie", `${data.meta.name} Kopie`);
                  if (!name) return;
                  const r = await run(() => api.copyProject(projectId, name), "Projekt kopiert");
                  if (r) onOpenProject(r.id);
                }}
              >
                Kopieren
              </button>
              <a className="btn" href={api.exportUrl(projectId)} download title="Projekt als eine ZIP-Datei sichern">
                Exportieren
              </a>
              <button
                className="btn danger"
                disabled={busy}
                onClick={async () => {
                  if (!window.confirm(`Projekt «${data.meta.name}» löschen? Es wird in den Ordner _Geloescht verschoben.`)) return;
                  const r = await run(() => api.deleteProject(projectId), "Projekt nach _Geloescht verschoben");
                  if (r) onBack();
                }}
              >
                Löschen
              </button>
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Pläne</h3>
          <p className="desc">Ein Plan pro Geschoss. Formate: DXF und N4D, DWG mit ODA File Converter.</p>
          {plans.length > 0 && (
            <table className="list-table">
              <thead>
                <tr>
                  <th>Geschoss</th>
                  <th>Datei</th>
                  <th>Importiert</th>
                  <th>Apparate</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {plans.map((p, i) => (
                  <tr key={p.id}>
                    <td>
                      <b>{p.name}</b>
                    </td>
                    <td>
                      {p.file_name} <span className="badge">{p.format?.toUpperCase()}</span>
                      {p.versions > 1 && <span className="hint"> · {p.versions} Versionen</span>}
                    </td>
                    <td>
                      {p.imported_at?.replace("T", " ").slice(0, 16)} · {p.imported_by}
                    </td>
                    <td>{planTotals[p.id]}</td>
                    <td style={{ whiteSpace: "nowrap", textAlign: "right" }}>
                      <button
                        className="btn small"
                        disabled={busy || i === 0}
                        title="nach oben"
                        onClick={async () => {
                          const ids = plans.map((x) => x.id);
                          [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
                          const r = await run(() => api.reorderPlans(projectId, ids));
                          if (r) setData(r);
                        }}
                      >
                        ↑
                      </button>{" "}
                      <button
                        className="btn small"
                        disabled={busy}
                        title="Geänderten Plan erneut importieren"
                        onClick={() => {
                          setReimportPlan(p.id);
                          reimportRef.current?.click();
                        }}
                      >
                        Neu importieren
                      </button>{" "}
                      <button
                        className="btn small"
                        disabled={busy}
                        onClick={async () => {
                          const name = window.prompt("Name des Geschosses", p.name);
                          if (!name || name === p.name) return;
                          const r = await run(() => api.renamePlan(projectId, p.id, name));
                          if (r) setData(r);
                        }}
                      >
                        Umbenennen
                      </button>{" "}
                      <button
                        className="btn small danger"
                        disabled={busy}
                        onClick={async () => {
                          if (!window.confirm(`Plan «${p.name}» aus dem Projekt entfernen?`)) return;
                          const r = await run(() => api.deletePlan(projectId, p.id), "Plan entfernt");
                          if (r) setData(r);
                        }}
                      >
                        Entfernen
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <input
            ref={reimportRef}
            type="file"
            accept=".dxf,.dwg,.n4d"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f && reimportPlan) importFile(f, reimportPlan);
              e.target.value = "";
            }}
          />
          <div className="row" style={{ marginTop: 12 }}>
            <input
              className="input"
              placeholder="Geschoss, z. B. EG"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              style={{ width: 200 }}
            />
            <input ref={fileRef} type="file" accept=".dxf,.dwg,.n4d" disabled={busy} />
            <button
              className="btn primary"
              disabled={busy}
              onClick={() => {
                const f = fileRef.current?.files?.[0];
                if (!f) notify("Bitte zuerst eine Datei wählen", true);
                else importFile(f);
              }}
            >
              {busy ? "importiert …" : "Plan importieren"}
            </button>
          </div>
        </div>

        {plans.length > 0 && (
          <div className="card">
            <div className="subtabs">
              <button className={`tab ${tab === "list" ? "active" : ""}`} onClick={() => setTab("list")}>
                Gesamtliste ({data.rows.length})
              </button>
              <button className={`tab ${tab === "unknown" ? "active" : ""}`} onClick={() => setTab("unknown")}>
                Unbekannt ({data.unknown.length})
              </button>
              <button className={`tab ${tab === "layers" ? "active" : ""}`} onClick={() => setTab("layers")}>
                Ebenen und Farben ({data.layers.length})
              </button>
              <button className={`tab ${tab === "ignored" ? "active" : ""}`} onClick={() => setTab("ignored")}>
                Nicht berücksichtigt ({data.ignored.length})
              </button>
            </div>

            {tab === "list" && (
              <div className="table-scroll">
                <table className="list-table summary">
                  <thead>
                    <tr>
                      <th style={{ width: 52 }} />
                      <th>Symbol</th>
                      <th>Code</th>
                      <th>Montage</th>
                      {plans.map((p) => (
                        <th key={p.id} className="num-col">
                          {p.name}
                        </th>
                      ))}
                      <th className="num-col">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groups.map((g) => (
                      <GroupRows
                        key={g.cat?.id ?? "none"}
                        title={g.cat?.title ?? "Ohne Kategorie"}
                        color={g.cat?.layer ? layerColor[g.cat.layer] : undefined}
                        layer={g.cat?.layer ?? ""}
                        colSpan={5 + plans.length}
                      >
                        {g.rows.map((r) => (
                          <tr key={r.family_key}>
                            <td>
                              <div className="mini-pic">
                                {r.svg ? <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: r.svg }} /> : "–"}
                              </div>
                            </td>
                            <td>
                              <b>{r.title}</b>
                              {r.names.length > 0 && <div className="hint">im Plan: {r.names.join(", ")}</div>}
                            </td>
                            <td>
                              {r.item}
                              <div className="hint">{r.datasets.map(DATASET_LABEL).join(", ")}</div>
                            </td>
                            <td>
                              {Object.entries(r.mountings)
                                .sort((a, b) => MOUNT_ORDER.indexOf(a[0]) - MOUNT_ORDER.indexOf(b[0]))
                                .map(([m, n]) => (
                                  <span key={m} className={`badge ${m === "UP" ? "up" : ""}`}>
                                    {m === "-" ? "–" : m} {n}
                                  </span>
                                ))}
                            </td>
                            {plans.map((p) => (
                              <td key={p.id} className="num-col">
                                {r.counts[p.id] ?? ""}
                              </td>
                            ))}
                            <td className="num-col">
                              <b>{r.total}</b>
                            </td>
                          </tr>
                        ))}
                      </GroupRows>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {tab === "unknown" && (
              <UnknownList
                projectId={projectId}
                plans={plans}
                items={data.unknown}
                notify={notify}
                onChanged={load}
              />
            )}

            {tab === "layers" && (
              <table className="list-table">
                <thead>
                  <tr>
                    <th>Farbe</th>
                    <th>Ebene</th>
                    <th>Linienart</th>
                    <th>Kategorien mit dieser Ebene</th>
                  </tr>
                </thead>
                <tbody>
                  {data.layers.map((l) => (
                    <tr key={l.name}>
                      <td>
                        <span className="swatch" style={{ background: l.color || "transparent" }} title={l.color} />
                      </td>
                      <td>{l.name}</td>
                      <td>{l.linetype}</td>
                      <td className="hint">
                        {categories
                          .filter((c) => c.layer === l.name)
                          .map((c) => c.title)
                          .join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
                      <td className="hint">{g.manual ? "von Hand ignoriert" : g.reason}</td>
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

function GroupRows({
  title,
  color,
  layer,
  colSpan,
  children,
}: {
  title: string;
  color?: string;
  layer: string;
  colSpan: number;
  children: React.ReactNode;
}) {
  return (
    <>
      <tr className="group-row">
        <td colSpan={colSpan}>
          {color && <span className="swatch" style={{ background: color }} title={`${layer} ${color}`} />} {title}
          {layer && <span className="hint"> · {layer}</span>}
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
