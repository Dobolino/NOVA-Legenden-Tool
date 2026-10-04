import { useEffect, useState } from "react";
import { api, ProjectSummary } from "../api";
import { exportDiagnostic } from "../diagnostics";

/** Guides, requirements and the diagnostic report. The legend sheet itself is not themed here. */
export default function HelpPage({ notify }: { notify: (text: string, error?: boolean) => void }) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    api.projects().then((r) => setProjects(r.items)).catch(() => setProjects([]));
  }, []);

  return (
    <div className="page">
      <div className="page-inner help-page">
        <div className="page-heading">
          <div>
            <div className="eyebrow">Hilfe</div>
            <h1>So arbeitest du mit der Legende</h1>
            <p>Die Schritte, was das Programm braucht, und was eine Meldung bedeutet.</p>
          </div>
        </div>

        <div className="card">
          <h3>Ablauf</h3>
          <ol className="help-steps">
            <li>In den Einstellungen den Firmenordner und die Nova-Datensätze eintragen. «Automatisch suchen» findet die Elektro-Datensätze im Trimble-Warehouse.</li>
            <li>Unter Projekte «Legende erstellen». Nummer, Name und Nova-Version angeben.</li>
            <li>Geschosse importieren (DXF, DWG oder N4D). DWG braucht den ODA File Converter.</li>
            <li>Unbekannte Symbole in der Bibliothek zuordnen. Kategorien ziehst du in der Kategorienliste an die gewünschte Stelle.</li>
            <li>Im Projekt den Reiter Legende öffnen. Vorschlag erzeugen, Texte und Reihenfolge anpassen, DXF oder DWG exportieren.</li>
          </ol>
        </div>

        <div className="card">
          <h3>Was benötigt wird</h3>
          <ul className="help-list">
            <li>Nova-Elektro-Datensätze (.nzp) mit Symbolen, üblicherweise unter C:\Users\Public\Documents\Trimble\Warehouse.</li>
            <li>Ein Firmenordner, den alle Mitarbeitenden erreichen. Dort liegt edeco ag-Legenden-firma.sqlite.</li>
            <li>DXF oder N4D für den Import ohne Zusatzprogramm. DWG zusätzlich der kostenlose ODA File Converter.</li>
            <li>Für den DWG-Export derselbe Converter. Ohne ihn bleibt der DXF-Export nutzbar.</li>
          </ul>
          <p className="hint">
            <a href="https://www.opendesign.com/guestfiles/oda_file_converter" target="_blank" rel="noreferrer">ODA File Converter herunterladen</a>
            . Das Programm startet keine fremden Installationsdateien von selbst.
          </p>
        </div>

        <div className="card">
          <h3>Meldungen</h3>
          <ul className="help-list">
            <li><b>Datensätze fehlen.</b> Pfad prüfen oder «Automatisch suchen». Eine Datei ohne Symbole wird nicht übernommen.</li>
            <li><b>Firmenordner fehlt.</b> In den Einstellungen einen Ordner wählen, den das Programm beschreiben darf.</li>
            <li><b>DWG konnte nicht erzeugt werden.</b> ODA File Converter installieren und das Programm neu öffnen. Bis dahin DXF verwenden.</li>
            <li><b>Unbekannt.</b> Das Symbol steht in keinem geladenen Datensatz oder die Zuordnung fehlt. In der Bibliothek zuordnen.</li>
            <li>
              <b>Allgemeinteil.</b>
              <br />Eine DXF- oder DWG-Datei, verknüpft in den Firmeneinstellungen.
              <br />Sie bleibt eine gesperrte Zeichnung.
              <br />Kachelgrösse und Abstand gelten für die erzeugte Legende, nicht für diese Datei.
            </li>
          </ul>
        </div>

        <div className="card">
          <h3>Prüfbericht</h3>
          <p className="desc">Zum Einfügen in ein Sprachmodell.</p>
          <ul className="help-list">
            <li>Version und geladene Datensätze</li>
            <li>ODA-Converter und Firmendatei</li>
            <li>Projekt, falls gewählt: Legendenstil, Geschosse, unbekannte Einträge</li>
          </ul>
          <p className="hint">Keine Zeichnungsgeometrie.</p>
          <label className="field">
            <span>Projekt</span>
            <select className="select" value={projectId} onChange={(e) => setProjectId(e.target.value)} aria-label="Projekt für den Prüfbericht">
              <option value="">Nur das Programm</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.project_number ? `${p.project_number} · ` : ""}{p.name}</option>
              ))}
            </select>
          </label>
          <button className="btn primary" type="button" onClick={() => exportDiagnostic(projectId, notify)}>Prüfbericht exportieren</button>
        </div>

        <p className="hint copyline">© 2026 edeco ag. Alle Rechte vorbehalten.</p>
      </div>
    </div>
  );
}
