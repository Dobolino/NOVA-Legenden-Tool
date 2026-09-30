import { useEffect, useState } from "react";
import { api, CountChange, PlanChanges, VersionInfo } from "../api";

const KIND: Record<CountChange["kind"], string> = {
  neu: "Neu",
  weg: "Weg",
  geaendert: "Anzahl geändert",
};

interface Props {
  projectId: string;
  stamp: string;
  notify: (text: string, error?: boolean) => void;
}

function versionLabel(version: VersionInfo, current: boolean): string {
  const when = version.imported_at?.replace("T", " ").slice(0, 16) ?? "";
  return [when, version.file_name || "ohne Datei", version.imported_by, current ? "aktuell" : ""]
    .filter(Boolean)
    .join(" · ");
}

export function changeHint(summary: { neu: number; weg: number; geaendert: number }): string {
  const parts: string[] = [];
  if (summary.neu) parts.push(`${summary.neu} neu`);
  if (summary.weg) parts.push(`${summary.weg} weg`);
  if (summary.geaendert) parts.push(`${summary.geaendert} geändert`);
  return parts.length ? `zum vorigen Import: ${parts.join(", ")}` : "keine Änderung zum vorigen Import";
}

function summaryText(plan: PlanChanges): string {
  const { neu, weg, geaendert } = plan.summary;
  const same = plan.unchanged ? ` ${plan.unchanged} unverändert.` : "";
  if (neu + weg + geaendert === 0) return `Keine Änderung bei den Apparaten.${same}`;
  const parts: string[] = [];
  if (neu) parts.push(`${neu} neu`);
  if (weg) parts.push(`${weg} weg`);
  if (geaendert) parts.push(`${geaendert} Anzahl geändert`);
  return `${parts.join(", ")}.${same}`;
}

export default function ChangesTab({ projectId, stamp, notify }: Props) {
  const [plans, setPlans] = useState<PlanChanges[] | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .changes(projectId)
      .then((res) => alive && setPlans(res.plans))
      .catch((e) => alive && notify((e as Error).message, true));
    return () => {
      alive = false;
    };
  }, [projectId, stamp, notify]);

  async function pick(planId: number, older: number, newer: number) {
    try {
      const res = await api.planChanges(projectId, planId, older, newer);
      setPlans((prev) => prev?.map((plan) => (plan.plan_id === planId ? res.plan : plan)) ?? [res.plan]);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  if (!plans) return <div className="hint">lädt …</div>;

  return (
    <div>
      <p className="desc">
        Vergleich zweier Importe desselben Geschosses. Standard ist der vorige Import gegen den aktuellen.
        Gezählt werden Apparate. Leitungen und Beschriftungen stehen darunter.
      </p>
      {plans.map((plan) => (
        <section key={plan.plan_id} style={{ marginBottom: 18 }}>
          <h3 style={{ marginBottom: 8 }}>{plan.name}</h3>
          {!plan.comparable || plan.older == null || plan.newer == null ? (
            <p className="hint">Erst ein Import. Ein erneuter Import zeigt danach, was sich geändert hat.</p>
          ) : (
            <>
              <div className="row" style={{ marginBottom: 8 }}>
                <label className="hint">
                  Von{" "}
                  <select
                    className="select"
                    value={plan.older}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      if (next === plan.newer) pick(plan.plan_id, plan.newer, plan.older as number);
                      else pick(plan.plan_id, next, plan.newer as number);
                    }}
                  >
                    {plan.versions.map((version, index) => (
                      <option key={version.id} value={version.id}>
                        {versionLabel(version, index === 0)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="hint">
                  Nach{" "}
                  <select
                    className="select"
                    value={plan.newer}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      if (next === plan.older) pick(plan.plan_id, plan.newer as number, plan.older as number);
                      else pick(plan.plan_id, plan.older as number, next);
                    }}
                  >
                    {plan.versions.map((version, index) => (
                      <option key={version.id} value={version.id}>
                        {versionLabel(version, index === 0)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <p className="hint">{summaryText(plan)}</p>
              {plan.changes.length === 0 ? (
                <p className="hint">Die Apparate und Anzahlen sind gleich.</p>
              ) : (
                <ChangeTable rows={plan.changes} />
              )}
              {plan.ignored_changes.length > 0 && (
                <>
                  <h4 style={{ margin: "14px 0 6px" }}>Leitungen, Masse und Beschriftungen</h4>
                  <table className="list-table">
                    <thead>
                      <tr>
                        <th>Element</th>
                        <th>Grund</th>
                        <th />
                        <th className="num-col">Vorher</th>
                        <th className="num-col">Nachher</th>
                        <th className="num-col">Differenz</th>
                      </tr>
                    </thead>
                    <tbody>
                      {plan.ignored_changes.map((row) => (
                        <tr key={row.name}>
                          <td>{row.name}</td>
                          <td className="hint">{row.reason}</td>
                          <td>
                            <span className={`badge ${row.kind}`}>{KIND[row.kind]}</span>
                          </td>
                          <td className="num-col">{row.before}</td>
                          <td className="num-col">{row.after}</td>
                          <td className="num-col">
                            <Delta value={row.delta} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}
        </section>
      ))}
    </div>
  );
}

function ChangeTable({ rows }: { rows: CountChange[] }) {
  return (
    <table className="list-table">
      <thead>
        <tr>
          <th style={{ width: 52 }} />
          <th>Symbol</th>
          <th>Code</th>
          <th />
          <th className="num-col">Vorher</th>
          <th className="num-col">Nachher</th>
          <th className="num-col">Differenz</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.source_key || row.name}>
            <td>
              <div className="mini-pic">
                {row.svg ? <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: row.svg }} /> : "–"}
              </div>
            </td>
            <td>
              <b>{row.title || row.name}</b>
              {row.name && row.title && row.name.toLowerCase() !== row.title.toLowerCase() && (
                <div className="hint">im Plan: {row.name}</div>
              )}
              {row.status === "unbekannt" && <div className="hint">unbekannt</div>}
            </td>
            <td>{row.item}</td>
            <td>
              <span className={`badge ${row.kind}`}>{KIND[row.kind]}</span>
            </td>
            <td className="num-col">{row.before}</td>
            <td className="num-col">{row.after}</td>
            <td className="num-col">
              <Delta value={row.delta} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Delta({ value }: { value: number }) {
  const cls = value > 0 ? "delta pos" : value < 0 ? "delta neg" : "delta";
  return <span className={cls}>{value > 0 ? `+${value}` : value}</span>;
}
