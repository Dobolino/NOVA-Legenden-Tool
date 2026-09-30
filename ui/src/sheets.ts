/** Parse the text of the number range field: "230, 240" -> ["230", "240"].
 *  Empty entries and duplicates are dropped (same rule as the backend). */
export function parseSheets(text: string): string[] {
  const out: string[] = [];
  for (const part of text.split(",")) {
    const p = part.trim();
    if (p && !out.includes(p)) out.push(p);
  }
  return out;
}
