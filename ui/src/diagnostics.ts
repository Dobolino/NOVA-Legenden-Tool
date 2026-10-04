import { api } from "./api";

export function diagnosticMarkdown(data: Record<string, unknown>): string {
  return [
    "# Prüfbericht — edeco ag - NOVA Legenden",
    "",
    "Strukturierter Zustand für die Fehlersuche. Der Bericht enthält keine Symbolgeometrie.",
    "Er kann in ein Sprachmodell kopiert werden.",
    "",
    "```json",
    JSON.stringify(data, null, 2),
    "```",
    "",
    "© 2026 edeco ag. Alle Rechte vorbehalten.",
    "",
  ].join("\n");
}

export function downloadText(name: string, text: string, type = "text/markdown;charset=utf-8"): void {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export async function exportDiagnostic(projectId: string, notify: (text: string, error?: boolean) => void): Promise<void> {
  try {
    const data = await api.diagnostics(projectId);
    const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "");
    downloadText(`pruefbericht-${stamp}.md`, diagnosticMarkdown(data));
    notify("Prüfbericht heruntergeladen");
  } catch (e) {
    notify((e as Error).message, true);
  }
}
