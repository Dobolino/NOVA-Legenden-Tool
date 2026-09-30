import { useEffect, useState } from "react";
import { api, Category, DATASET_LABEL, FamilyItem, SymbolDetail } from "../api";
import SymbolPic from "./SymbolPic";

interface Props {
  id: string;
  categories: Category[];
  notify: (text: string, error?: boolean) => void;
  onClose: () => void;
  onAssigned: (fam: FamilyItem) => void;
}

const LABELS: Record<string, string> = {
  line: "Linien",
  arc: "Bögen",
  polygon: "Flächen",
  polyline: "Polylinien",
  ellipse_arc: "Ellipsenbögen",
  spline: "Splines",
  hatch: "Schraffuren",
  text: "Texte",
};

export default function FamilyDetail({ id, categories, notify, onClose, onAssigned }: Props) {
  const [fam, setFam] = useState<FamilyItem | null>(null);
  const [symKey, setSymKey] = useState<string>("");
  const [detail, setDetail] = useState<SymbolDetail | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    setFam(null);
    api
      .family(id)
      .then((f) => {
        if (!alive) return;
        setFam(f);
        const variantKey = id.includes("#") ? id.split("#")[1] : f.representative.key;
        setSymKey(variantKey);
      })
      .catch((e) => notify((e as Error).message, true));
    return () => {
      alive = false;
    };
  }, [id, notify]);

  useEffect(() => {
    if (!symKey) return;
    let alive = true;
    api
      .symbol(symKey)
      .then((d) => alive && setDetail(d))
      .catch((e) => notify((e as Error).message, true));
    return () => {
      alive = false;
    };
  }, [symKey, notify]);

  async function save(next: string[] | null) {
    if (!fam) return;
    setSaving(true);
    try {
      const updated = await api.assign(fam.id, next);
      setFam({ ...fam, categories: updated.categories, category_source: updated.category_source });
      onAssigned(updated);
      notify(next ? "Zuordnung gespeichert (gilt für die ganze Firma)" : "Automatische Zuordnung wiederhergestellt");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setSaving(false);
    }
  }

  function toggle(catId: string) {
    if (!fam) return;
    const has = fam.categories.includes(catId);
    const next = has ? fam.categories.filter((c) => c !== catId) : [...fam.categories, catId];
    if (next.length === 0) {
      notify("Mindestens eine Kategorie muss gewählt sein", true);
      return;
    }
    save(next);
  }

  if (!fam) {
    return (
      <aside className="drawer">
        <div className="hint">lädt …</div>
      </aside>
    );
  }

  const current = fam.members?.find((m) => m.key === symKey) ?? fam.representative;
  const ordered = [
    ...categories.filter((c) => !c.parent).flatMap((c) => [c, ...categories.filter((x) => x.parent === c.id)]),
  ];

  return (
    <aside className="drawer">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2>{fam.title}</h2>
          <div className="sub">
            {DATASET_LABEL(fam.dataset)} · {fam.variant_count} Variante{fam.variant_count === 1 ? "" : "n"}
          </div>
        </div>
        <button className="btn small" onClick={onClose} title="Schliessen">
          ✕
        </button>
      </div>

      <div className="big-pic">
        <SymbolPic sym={current} svg={detail?.key === current.key ? detail.svg_points || undefined : undefined} />
      </div>
      <div className="hint">Punkte: orange = Anschlusspunkte (NP), blau = Einfüge-/Hilfspunkte.</div>

      {fam.members && fam.members.length > 1 && (
        <>
          <div className="section">Varianten</div>
          <div className="variants">
            {fam.members.map((m) => (
              <div
                key={m.key}
                className={`variant ${m.key === symKey ? "active" : ""}`}
                onClick={() => setSymKey(m.key)}
                title={m.name}
              >
                <div className="pic">
                  <SymbolPic sym={m} />
                </div>
                <div>
                  <b>{m.mounting ?? "–"}</b> {m.is_representative ? "★" : ""}
                </div>
                <div>{m.label_variant || m.orientation || m.item}</div>
              </div>
            ))}
          </div>
          <div className="hint" style={{ marginTop: 4 }}>
            ★ = UP-Vertreter. Er erscheint in der Liste und in der Legende.
          </div>
        </>
      )}

      {fam.conflicts.length > 0 && (
        <>
          <div className="section">Hinweise</div>
          {fam.conflicts.map((c) => (
            <div key={c} className="warn-text">
              {c}
            </div>
          ))}
        </>
      )}

      <div className="section">
        Kategorien{" "}
        <span className={`badge ${fam.category_source === "manuell" ? "manual" : ""}`}>
          {fam.category_source === "manuell" ? "manuell zugeordnet" : `automatisch: ${fam.category_source}`}
        </span>
      </div>
      <div className="cat-checks">
        {ordered.map((c) => (
          <label key={c.id} className={c.parent ? "child" : ""}>
            <input
              type="checkbox"
              disabled={saving}
              checked={fam.categories.includes(c.id)}
              onChange={() => toggle(c.id)}
            />
            {c.title}
            {c.hidden ? " (ausgeblendet)" : ""}
          </label>
        ))}
      </div>
      {fam.category_source === "manuell" && (
        <button className="btn small" style={{ marginTop: 6 }} disabled={saving} onClick={() => save(null)}>
          Automatisch zuordnen
        </button>
      )}

      {detail && detail.key === current.key && (
        <>
          <div className="section">Angaben zum Symbol</div>
          <dl className="kv">
            <dt>Name</dt>
            <dd>{detail.name}</dd>
            <dt>Katalogcode</dt>
            <dd>
              {detail.item} ({detail.graphic_id})
            </dd>
            <dt>Montageart</dt>
            <dd>{detail.mounting ?? "ohne Angabe"}</dd>
            <dt>Nummernkreis</dt>
            <dd>
              {detail.sheet} · {detail.sheet_name}
            </dd>
            <dt>Ordner</dt>
            <dd>{(detail.folder_path ?? []).join(" › ") || "–"}</dd>
            {detail.stencils && detail.stencils.length > 0 && (
              <>
                <dt>Schablonen</dt>
                <dd>{detail.stencils.join(", ")}</dd>
              </>
            )}
            <dt>Grafik</dt>
            <dd>
              {Object.entries(detail.stats)
                .map(([k, v]) => `${v} ${LABELS[k] ?? k}`)
                .join(", ") || detail.kind}
            </dd>
            <dt>Anschlusspunkte</dt>
            <dd>{Object.keys(detail.points ?? {}).join(", ") || "–"}</dd>
            {detail.engine && (
              <>
                <dt>Parameter</dt>
                <dd>{detail.engine}</dd>
              </>
            )}
            {detail.files_3d && detail.files_3d.length > 0 && (
              <>
                <dt>3D</dt>
                <dd>{detail.files_3d.join(", ")}</dd>
              </>
            )}
            {detail.attributes?.Kennbuchstabe && (
              <>
                <dt>Kennbuchstabe</dt>
                <dd>{detail.attributes.Kennbuchstabe}</dd>
              </>
            )}
          </dl>
        </>
      )}
    </aside>
  );
}
