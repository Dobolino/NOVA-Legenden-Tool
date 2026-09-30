import { SymbolBrief } from "../api";

// The SVG comes from our own backend (rendered from the Nova dataset, text escaped).
export default function SymbolPic({ sym, svg }: { sym: SymbolBrief; svg?: string }) {
  const content = svg ?? sym.svg;
  if (content) return <span style={{ display: "contents" }} dangerouslySetInnerHTML={{ __html: content }} />;
  const label =
    sym.kind === "Engine"
      ? "parametrische Leuchte (Vorschau folgt)"
      : sym.kind === "Symbol"
        ? "Grafik in Nova-Bibliothek (.nsb), noch nicht lesbar"
        : "keine Grafik";
  return <div className="placeholder">{label}</div>;
}
