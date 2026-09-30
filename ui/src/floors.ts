/** Floor label from a plan file name. «3_1.OG.dxf» becomes «1. OG». */

const NUMBERED = /(\d+)\s*\.\s*(OG|UG|DG|STOCK)/i;
const BARE = /(?:^|[_\s.-])(EG|UG|DG|OG)(?:$|[_\s.-])/i;

export function floorNameFromFilename(filename: string): string | null {
  const stem = filename.replace(/\.[^.]+$/, "");
  const numbered = NUMBERED.exec(stem);
  if (numbered) {
    const kind = numbered[2].toLowerCase() === "stock" ? "Stock" : numbered[2].toUpperCase();
    return `${Number(numbered[1])}. ${kind}`;
  }
  const bare = BARE.exec(stem);
  return bare ? bare[1].toUpperCase() : null;
}
