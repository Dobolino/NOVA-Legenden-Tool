import { useEffect, useState } from "react";
import { api, CompanyLegend, GeneralInfo } from "../api";
import GeneralPartEditor from "./GeneralPartEditor";

/** Legende Allgemein (the drawing) and, separate from it, everything an admin sets. */
export default function CompanyLegendCard({
  canPick,
  choose,
  notify,
}: {
  canPick: boolean;
  choose: (kind: "legend" | "folder", start: string) => Promise<string | null>;
  notify: (text: string, error?: boolean) => void;
}) {
  const [info, setInfo] = useState<(CompanyLegend & { general: GeneralInfo }) | null>(null);
  const [path, setPath] = useState("");
  const [admins, setAdmins] = useState("");
  const [textSize, setTextSize] = useState("");
  const [scale, setScale] = useState("");
  const [busy, setBusy] = useState(false);
  const [generalRev, setGeneralRev] = useState(0);

  function apply(r: CompanyLegend & { general: GeneralInfo }) {
    setInfo(r);
    setPath(r.general_path);
    setAdmins(r.admins.join(", "));
    setTextSize(String(r.text_size));
    setScale(String(r.symbol_scale));
  }

  useEffect(() => {
    api.companyLegend().then(apply).catch((e) => notify((e as Error).message, true));
  }, [notify]);

  if (!info) return null;
  const locked = !info.is_admin;

  async function save(values: Parameters<typeof api.saveCompanyLegend>[0], ok: string) {
    setBusy(true);
    try {
      apply(await api.saveCompanyLegend(values));
      if ("general_path" in values) setGeneralRev((n) => n + 1);
      notify(ok);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const num = (v: string) => Number(v.replace(",", "."));

  const me = info.user.toLocaleLowerCase("de-CH");
  return (
    <>
      <div className="card">
        <h3>Legende Allgemein</h3>
        <p className="desc">
          Die Zeichnung steht in jeder Legende zuoberst. Den Pfad trägt die Firma selbst ein, er ist nicht fest im Programm.
          Nur Admins ändern Pfad und Zeilen.
        </p>

        <label className="field">
          <span>Datei oder Ordner (DXF, DWG oder Ordner eines Vorlagen-Projekts)</span>
          <div className="row">
            <input className="input" style={{ flex: 1, minWidth: 260 }} value={path} disabled={locked} title={path} onChange={(e) => setPath(e.target.value)} placeholder="\\\\Server\\CAD\\Legenden\\Legende Allgemein" aria-label="Legende Allgemein" />
            <button
              className="btn"
              disabled={locked || busy || !canPick}
              onClick={async () => {
                const p = await choose("legend", path);
                if (p) setPath(p);
              }}
            >
              Datei wählen …
            </button>
            <button
              className="btn"
              disabled={locked || busy || !canPick}
              title="Ordner eines Vorlagen-Projekts mit Legende"
              onClick={async () => {
                const p = await choose("folder", path);
                if (p) setPath(p);
              }}
            >
              Ordner wählen …
            </button>
            <button className="btn primary" disabled={locked || busy || path === info.general_path} onClick={() => save({ general_path: path }, "Legende Allgemein gespeichert")}>
              Speichern
            </button>
          </div>
        </label>
        <p className="hint">
          Empfehlung: die einspaltige Legende einmal als DXF direkt aus Nova speichern und hier eintragen. Eine DXF braucht keinen
          ODA File Converter, eine DWG schon (auf jedem Arbeitsplatz). Das Programm ordnet sie selbst in 2 oder 3 Spalten. Änderst du
          die Datei auf dem Server, liest das Programm sie beim nächsten Öffnen der Legende neu. Liegt die Zeichnung im
          Ordner oder heisst sie wie der Ordner mit Endung .dxf oder .dwg, reicht der Ordnerpfad.
        </p>
        {info.general.kind ? (
          <p className="hint">
            Gelesen: {info.general.kind === "dxf" ? "DXF/DWG" : "Vorlagen-Projekt"}, {info.general.w} × {info.general.h} mm.
            {info.general.file ? <><br />Datei: {info.general.file}</> : null}
            <br />Steht in jeder Legende zuoberst.
            <br />Nur die Blattbreite skaliert die Datei. Kachelgrösse, Schrift und Abstand gelten für die erzeugte Legende.
            <br />Einträge darin lassen sich nicht ziehen.
          </p>
        ) : info.general.error ? (
          <p className="warn-text">{info.general.error}</p>
        ) : (
          <p className="hint">
            Keine Legende Allgemein eingetragen.
            <br />Pfad einfügen oder im Programmfenster die Datei wählen.
            <br />Erlaubt sind DXF, DWG und der Ordner eines Vorlagen-Projekts.
            <br />N4D wird nicht gelesen.
          </p>
        )}

        <GeneralPartEditor notify={notify} reloadKey={generalRev} />
      </div>

      <section className="card admin-box" aria-label="Admin">
        <div className="admin-title">
          <h3>Admin</h3>
          <span className={`admin-badge ${info.is_admin && !info.bootstrap ? "on" : ""}`}>
            {info.bootstrap ? "Offen für alle" : info.is_admin ? "Du bist Admin" : "Nicht Admin"}
          </span>
        </div>
        <p className="desc">
          Angemeldet als <b>{info.user}</b>. Das ist der Windows-Name dieses Computers. Er steht nicht fest im Programm
          und ist im Feld nur ein Vorschlag.
          {info.bootstrap && " Noch kein Admin eingetragen: trage dich zuerst selbst ein."}
        </p>
        <p className="hint">
          {info.bootstrap
            ? "Noch niemand eingetragen: jeder darf ändern und sich selbst eintragen. Steht ein Name drin, sehen das alle. Weitere Namen trägt nur ein Admin ein."
            : info.is_admin
              ? "Du stehst in der Liste. Nur Admins können weitere Namen eintragen oder entfernen."
              : "Die Liste ist gesperrt. Nur die markierten Admins können sie ändern."}
        </p>
        <ul className="admin-list">
          {info.admins.length ? info.admins.map((name) => {
            const mine = name.toLocaleLowerCase("de-CH") === me;
            return (
              <li key={name} className={mine ? "me" : ""}>
                <span className="star" aria-hidden="true">★</span>
                <span>{name}</span>
                {mine && <span className="you">du</span>}
              </li>
            );
          }) : <li className="empty">Noch keine Admins</li>}
        </ul>
        <label className="field">
          <span>Windows-Benutzernamen, durch Komma getrennt</span>
          <div className="row">
            <input className="input" style={{ flex: 1, minWidth: 260 }} value={admins} disabled={locked} onChange={(e) => setAdmins(e.target.value)} placeholder={info.user} aria-label="Admin-Liste" />
            <button
              className="btn primary"
              disabled={locked || busy || admins === info.admins.join(", ")}
              onClick={() => save({ admins: admins.split(",").map((a) => a.trim()).filter(Boolean) }, "Admin-Liste gespeichert")}
            >
              Speichern
            </button>
          </div>
        </label>

        <h4>Standard für neue Projekte</h4>
        <div className="head-fields" style={{ marginTop: 10 }}>
          <label className="field">
            <span>Schriftgrösse (mm)</span>
            <input className="input" style={{ width: 120 }} inputMode="decimal" value={textSize} disabled={locked} onChange={(e) => setTextSize(e.target.value)} />
          </label>
          <label className="field">
            <span>Symbolmassstab</span>
            <input className="input" style={{ width: 120 }} inputMode="decimal" value={scale} disabled={locked} onChange={(e) => setScale(e.target.value)} />
          </label>
          <button
            className="btn primary"
            disabled={locked || busy || (num(textSize) === info.text_size && num(scale) === info.symbol_scale) || !Number.isFinite(num(textSize)) || !Number.isFinite(num(scale))}
            onClick={() => save({ text_size: num(textSize), symbol_scale: num(scale) }, "Firmen-Standard gespeichert. Bestehende Projekte bleiben unverändert.")}
          >
            Speichern
          </button>
        </div>
        <label className="toggle" style={{ marginTop: 8 }}>
          <input type="checkbox" checked={info.hatch_off} disabled={locked || busy}
            onChange={(e) => save({ hatch_off: e.target.checked }, "Firmen-Standard gespeichert. Bestehende Projekte bleiben unverändert.")} />
          Weiche Schraffur in Symbolen aus
        </label>
        <label className="toggle">
          <input type="checkbox" checked={info.fill_off} disabled={locked || busy}
            onChange={(e) => save({ fill_off: e.target.checked }, "Firmen-Standard gespeichert. Bestehende Projekte bleiben unverändert.")} />
          Volle Flächen in Symbolen aus
        </label>
        <p className="hint">Jedes neue Projekt startet mit diesen Werten, ausser es wird aus einer Vorlage erstellt. Dann gelten die Werte der Vorlage.</p>
      </section>
    </>
  );
}
