import { useEffect, useState } from "react";
import { api, CountChange, PlanChanges } from "../api";
import { changeWords, countChange, importVersionLabel } from "../uiState";

const KIND: Record<CountChange["kind"], string> = {
  neu: "Neu",
  weg: "Entfallen",
  geaendert: "Anzahl geändert",
};

interface Props {
  projectId: string;
  stamp: string;
  notify: (text: string, error?: boolean) => void;
}

/** Short form under the floor in the plans table. */
export function changeHint(summary: { neu: number; weg: number; geaendert: number }): string {
  const words = changeWords(summary);
  return words ? `zum vorigen Import: ${words}` : "keine Änderung zum vorigen Import";
}

function summaryText(plan: PlanChanges): string {
  const words = changeWords(plan.summary);
  const same = plan.unchanged ? ` ${plan.unchanged} unverändert.` : "";
  return words ? `Apparate: ${words}.${same}` : `Keine Änderung bei den Apparaten.${same}`;
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
  const anyComparable = plans.some((p) => p.comparable);

  return (
    <div>
      <h3 style={{ margin: "0 0 6px" }}>Vergleich von Importversionen</h3>
      <p className="info-line">
        Verglichen werden Anzahlen, keine Positionen im Plan. Standard ist der vorige gegen den aktuellen Import
        desselben Geschosses.
      </p>
      {!anyComparable && (
        <div className="empty" style={{ padding: 24 }}>
          Noch kein Vergleich verfügbar. Importiere eine neue Planversion eines vorhandenen Geschosses.
        </div>
      )}
      {plans.map((plan) => {
        if (!plan.comparable || plan.older == null || plan.newer == null) {
          if (!anyComparable) return null;
          return (
            <section key={plan.plan_id} style={{ marginBottom: 14 }}>
              <h4 style={{ margin: "0 0 4px" }}>{plan.name}</h4>
              <p className="hint" style={{ margin: 0 }}>
                Nur eine Importversion. Noch kein Vergleich für dieses Geschoss.
              </p>
            </section>
          );
        }
        const older = plan.older;
        const newer = plan.newer;
        const choose = (which: "older" | "newer", id: number) => {
          if (which === "older") {
            if (id === newer) pick(plan.plan_id, newer, older);
            else pick(plan.plan_id, id, newer);
          } else if (id === older) pick(plan.plan_id, newer, older);
          else pick(plan.plan_id, older, id);
        };
        return (
          <section key={plan.plan_id} style={{ marginBottom: 22 }}>
            <div className="compare-bar">
              <div className="field" style={{ flex: "0 1 160px" }}>
                <span>Geschoss</span>
                <b style={{ fontSize: 16, lineHeight: "34px" }}>{plan.name}</b>
              </div>
              <label className="field">
                <span>Von</span>
                <select className="select" value={older} onChange={(e) => choose("older", Number(e.target.value))}>
                  {plan.versions.map((version, index) => (
                    <option key={version.id} value={version.id}>
                      {importVersionLabel(plan.versions, index)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="btn"
                title="Von und Nach tauschen. Neu und Entfallen drehen sich um."
                onClick={() => pick(plan.plan_id, newer, older)}
              >
                ⇄ Tauschen
              </button>
              <label className="field">
                <span>Nach</span>
                <select className="select" value={newer} onChange={(e) => choose("newer", Number(e.target.value))}>
                  {plan.versions.map((version, index) => (
                    <option key={version.id} value={version.id}>
                      {importVersionLabel(plan.versions, index)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="hint">{summaryText(plan)}</p>
            {plan.changes.length > 0 && <ChangeTable rows={plan.changes} />}
            {plan.ignored_changes.length > 0 && (
              <>
                <h4 style={{ margin: "14px 0 6px" }}>Leitungen, Masse und Beschriftungen</h4>
                <div className="table-scroll">
                  <table className="list-table">
                    <thead>
                      <tr>
                        <th>Element</th>
                        <th>Grund</th>
                        <th>Änderung</th>
                        <th className="num-col">Anzahl vorher → nachher · Differenz</th>
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
                          <td className="num-col count-change">
                            <Count row={row} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        );
      })}
    </div>
  );
}

function ChangeTable({ rows }: { rows: CountChange[] }) {
  return (
    <div className="table-scroll">
      <table className="list-table">
        <thead>
          <tr>
            <th style={{ width: 56 }} />
            <th>Symbol</th>
            <th>Code</th>
            <th>Änderung</th>
            <th className="num-col">Anzahl vorher → nachher · Differenz</th>
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
              <td className="num-col count-change">
                <Count row={row} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Count({ row }: { row: CountChange }) {
  const cls = row.delta > 0 ? "delta pos" : row.delta < 0 ? "delta neg" : "delta";
  const [counts, delta] = countChange(row.before, row.after).split(" · ");
  return (
    <>
      {counts} · <span className={cls}>{delta}</span>
    </>
  );
}
