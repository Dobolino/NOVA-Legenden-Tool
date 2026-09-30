// Run: npm test  (Node 22, no extra packages)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  countChange,
  draftOf,
  draftPatch,
  importVersionLabel,
  isDirty,
  layerStateText,
  plansOpen,
  rememberPlansOpen,
} from "./uiState.ts";

function memory() {
  const data = new Map<string, string>();
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
}

test("plans section: open without plans, remembered per project otherwise", () => {
  const store = memory();
  assert.equal(plansOpen("a", 0, store), true);
  assert.equal(plansOpen("a", 3, store), true);
  rememberPlansOpen("a", false, store);
  assert.equal(plansOpen("a", 3, store), false);
  assert.equal(plansOpen("a", 0, store), true, "no plans: always open");
  assert.equal(plansOpen("b", 2, store), true, "other project keeps its own state");
  assert.equal(plansOpen("a", 2, null), true, "no storage: open");
});

test("count change reads before → after · delta", () => {
  assert.equal(countChange(3, 5), "3 → 5 · +2");
  assert.equal(countChange(5, 3), "5 → 3 · -2");
  assert.equal(countChange(0, 4), "0 → 4 · +4");
});

test("import versions are numbered from the oldest, newest is current", () => {
  const versions = [
    { id: 9, file_name: "3_1.OG.dxf", format: "dxf", imported_at: "2026-09-30T10:12:44", imported_by: "mueller" },
    { id: 4, file_name: "", format: "n4d", imported_at: "2026-09-01T08:05:00", imported_by: "meier" },
  ];
  assert.equal(importVersionLabel(versions, 0), "Importversion 2 · 30.09.2026 10:12 · 3_1.OG.dxf (DXF) · mueller · aktuell");
  assert.equal(importVersionLabel(versions, 1), "Importversion 1 · 01.09.2026 08:05 · Plandatei entfernt · meier");
});

const cat = { id: "licht", title: "Licht", parent: null, layer: "E_Licht", columns: 2, spacing: 4.55, hidden: false, sheets: ["110", "120"] };

test("category draft: unchanged draft is clean and gives an empty patch", () => {
  const d = draftOf(cat);
  assert.equal(isDirty(d, cat), false);
  assert.deepEqual(draftPatch(d, cat), { patch: {}, error: "" });
});

test("category draft: only changed fields are sent, number ranges parsed", () => {
  const d = { ...draftOf(cat), layer: " E_232.5_Licht ", sheets: "110, 120, 130,", spacing: "5,1" };
  assert.equal(isDirty(d, cat), true);
  assert.deepEqual(draftPatch(d, cat).patch, { layer: "E_232.5_Licht", sheets: ["110", "120", "130"], spacing: 5.1 });
  assert.deepEqual(draftPatch({ ...draftOf(cat), parent: "kraft" }, cat).patch, { parent: "kraft" });
});

test("category draft: invalid values give an error and count as unsaved", () => {
  assert.match(draftPatch({ ...draftOf(cat), title: "  " }, cat).error, /Titel/);
  assert.match(draftPatch({ ...draftOf(cat), columns: "9" }, cat).error, /Spalten/);
  assert.equal(isDirty({ ...draftOf(cat), columns: "0" }, cat), true);
});

test("layer state texts name the layer and tell missing from uncoloured", () => {
  const base = { layer: "", color: "", reason: "", used: 3, layer_missing: false, no_color: false };
  assert.equal(layerStateText({ ...base, state: "automatisch", layer: "E_232.5_Licht", color: "#f00" }).text, "Automatisch → E_232.5_Licht");
  assert.equal(layerStateText({ ...base, state: "manuell", layer: "E_Licht", color: "#f00" }).text, "Manuell → E_Licht");
  const choose = layerStateText({ ...base, state: "waehlen", reason: "keine passende Ebene, E_BMA ist im Plan nicht vorhanden" });
  assert.equal(choose.text, "Ebene wählen");
  assert.match(choose.detail, /E_BMA/);
  assert.equal(layerStateText({ ...base, state: "unbenutzt", used: 0 }).text, "Im Projekt nicht verwendet");
  assert.match(layerStateText({ ...base, state: "manuell", layer: "E_X", layer_missing: true }).detail, /nicht vorhanden/);
  assert.match(layerStateText({ ...base, state: "manuell", layer: "E_X", no_color: true }).detail, /keine Farbangabe/);
});
