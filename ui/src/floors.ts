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

const PLAN_FILE = /\.(dxf|dwg|n4d)$/i;

/** Only plan files (DXF, DWG, N4D) of a drop or a file dialog. */
export function planFiles<T extends { name: string }>(files: T[]): T[] {
  return files.filter((f) => PLAN_FILE.test(f.name));
}

/** Floor name for a file: floor from the file name, else the file name without extension. */
export function floorNameFor(filename: string): string {
  return floorNameFromFilename(filename) ?? filename.replace(/\.[^.]+$/, "");
}

/** Existing floor with the same name (case and spaces ignored): the import becomes its new plan version. */
export function matchPlan<T extends { id: number; name: string }>(name: string, plans: T[]): T | undefined {
  const key = name.replace(/\s+/g, "").toLowerCase();
  return key ? plans.find((p) => p.name.replace(/\s+/g, "").toLowerCase() === key) : undefined;
}
