import { useEffect, useState } from "react";
import { api, CompanyLegend, GeneralInfo } from "../api";

/** Company legend settings: general part on the server, admins, standard text size and symbol scale. */
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
      notify(ok);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  const num = (v: string) => Number(v.replace(",", "."));

  return (
    <div className="card">
      <h3>Legende der Firma</h3>
      <p className="desc">
        Gilt für die ganze Firma. Ändern dürfen nur die Admins unten (Windows-Benutzer). Du bist angemeldet als <b>{info.user}</b>
        {info.is_admin ? " und darfst ändern." : ", ohne Admin-Recht."}
        {info.bootstrap && " Noch kein Admin eingetragen: trage dich zuerst selbst ein."}
      </p>

      <label className="field">
        <span>Allgemeinteil auf dem Server (DXF, DWG oder Ordner eines Vorlagen-Projekts)</span>
        <div className="row">
          <input className="input" style={{ flex: 1, minWidth: 260 }} value={path} disabled={locked} title={path} onChange={(e) => setPath(e.target.value)} placeholder="T:\_CAD\NovaDat\NovaFirma12\Makro\Legenden\Allgemein.dxf" />
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
          <button className="btn primary" disabled={locked || busy || path === info.general_path} onClick={() => save({ general_path: path }, "Allgemeinteil gespeichert")}>
            Speichern
          </button>
        </div>
      </label>
      {info.general.kind ? (
        <p className="hint">
          Gelesen: {info.general.kind === "dxf" ? "DXF/DWG" : "Vorlagen-Projekt"}, {info.general.w} × {info.general.h} mm.
          <br />Steht in jeder Legende zuoberst.
          <br />Nur die Blattbreite skaliert die Datei. Kachelgrösse, Schrift und Abstand gelten für die erzeugte Legende.
          <br />Einträge darin lassen sich nicht ziehen.
        </p>
      ) : info.general.error ? (
        <p className="warn-text">{info.general.error}</p>
      ) : (
        <p className="hint">
          Kein Allgemeinteil eingetragen.
          <br />Pfad einfügen oder im Programmfenster die Datei wählen.
          <br />Erlaubt sind DXF, DWG und der Ordner eines Vorlagen-Projekts.
          <br />N4D wird nicht gelesen.
        </p>
      )}

      <label className="field" style={{ marginTop: 10 }}>
        <span>Admins (Windows-Benutzernamen, durch Komma getrennt)</span>
        <div className="row">
          <input className="input" style={{ flex: 1, minWidth: 260 }} value={admins} disabled={locked} onChange={(e) => setAdmins(e.target.value)} placeholder={info.user} />
          <button
            className="btn primary"
            disabled={locked || busy || admins === info.admins.join(", ")}
            onClick={() => save({ admins: admins.split(",").map((a) => a.trim()).filter(Boolean) }, "Admin-Liste gespeichert")}
          >
            Speichern
          </button>
        </div>
      </label>

      <div className="head-fields" style={{ marginTop: 10 }}>
        <label className="field">
          <span>Schriftgrösse neuer Projekte (mm)</span>
          <input className="input" style={{ width: 120 }} inputMode="decimal" value={textSize} disabled={locked} onChange={(e) => setTextSize(e.target.value)} />
        </label>
        <label className="field">
          <span>Symbolmassstab neuer Projekte</span>
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
        Weiche Schraffur in Symbolen aus (neue Projekte)
      </label>
      <label className="toggle">
        <input type="checkbox" checked={info.fill_off} disabled={locked || busy}
          onChange={(e) => save({ fill_off: e.target.checked }, "Firmen-Standard gespeichert. Bestehende Projekte bleiben unverändert.")} />
        Volle Flächen in Symbolen aus (neue Projekte)
      </label>
      <p className="hint">Jedes neue Projekt startet mit diesen Werten, ausser es wird aus einer Vorlage erstellt. Dann gelten die Werte der Vorlage.</p>
    </div>
  );
}
