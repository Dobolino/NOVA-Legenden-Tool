import { SymbolBrief } from "../api";

/** Why a symbol has no preview. The symbol itself is known; only the drawing is missing. */
export function missingPreviewReason(sym: SymbolBrief): string {
  if (sym.kind === "Engine")
    return "Parametrische Leuchte: Nova zeichnet sie aus Länge, Breite und Typ. Für diesen Typ gibt es noch keine Vorschau.";
  if (sym.kind === "Symbol")
    return "Die Grafik liegt in einer Nova-Symboldatei (.nsb). Dieses Format kann das Programm noch nicht lesen.";
  return "Der Datensatz enthält für diese Grafik keine lesbare Zeichnung.";
}

// The SVG comes from our own backend (rendered from the Nova dataset, text escaped).
export default function SymbolPic({ sym, svg }: { sym: SymbolBrief; svg?: string }) {
  const content = svg ?? sym.svg;
  if (content) return <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: content }} />;
  return (
    <div className="placeholder" title={`${missingPreviewReason(sym)} Das Symbol ist trotzdem erkannt.`}>
      Keine Symbolvorschau verfügbar
    </div>
  );
}
