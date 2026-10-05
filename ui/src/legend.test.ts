// Run: npm test  (Node 22, no extra packages)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  addBlock,
  addItem,
  beginSave,
  blockForCategory,
  commit,
  coveredRows,
  describe,
  duplicateItems,
  hideCovered,
  historyOf,
  inGeneral,
  inLegend,
  insertItem,
  isCurrentSave,
  missingRows,
  moveBlockInOrder,
  moveItemInOrder,
  moveItemTo,
  moveItemToBlock,
  normText,
  placeInCell,
  push,
  redo,
  removeItem,
  replace,
  rotateItem,
  sectionStyle,
  staleItems,
  undo,
  updateItem,
} from "./legend.ts";
import type { LegendDoc } from "./legend.ts";

const style = {
  font: "Arial", text_size: 2.5, symbol_scale: 1, grid: "standard", row: 4.55, text_offset: 9.75,
  columns: 2, width: 200, margin: 5, plan_scale: 50, section_gap: 0, entry_gap: 0, text_lines: 0,
  hatch_off: false, fill_off: false, frame_on: false, frame: "#000000",
};

function item(id: string, family: string | null) {
  return { id, kind: "symbol" as const, family_key: family, symbol_key: family ? `s:${family}` : null, text: id,
    length_mm: null, width_mm: null, line_style: "solid" as const, line_length: 8, text_scale: 1, symbol_factor: 1, rotation: 0, hidden: false, keep: false };
}

function doc(): LegendDoc {
  return {
    version: 2,
    style,
    title: { text: "Legende", scale: 1, size_mm: 0, font: "Arial", color: "#000000", border_on: false, border: "#000000" },
    blocks: [
      { id: "a", category_id: "licht", title: "Licht", layer: "E_Licht", collapsed: false, title_scale: 1, style: sectionStyle("#1971c2"),
        items: [item("i1", "lampe"), item("i2", "spot")] },
      { id: "b", category_id: "bma", title: "BMA", layer: "", collapsed: false, title_scale: 1, style: sectionStyle(null), items: [item("i3", "melder")] },
    ],
  };
}

test("undo and redo, typing in a field is one step", () => {
  let h = historyOf(doc());
  const start = h.present;
  h = push(h, updateItem(h.present, "a", "i1", { text: "Neu" }));
  const before = h.present;
  h = replace(h, updateItem(h.present, "a", "i1", { text: "N" }));
  h = replace(h, updateItem(h.present, "a", "i1", { text: "Neuer Text" }));
  h = commit(h, before);
  assert.equal(h.past.length, 2, "one change + one typed field");
  h = undo(h);
  assert.equal(h.present, before);
  h = undo(h);
  assert.equal(h.present, start);
  h = redo(redo(h));
  assert.equal(h.present.blocks[0].items[0].text, "Neuer Text");
  h = push(undo(h), removeItem(h.present, "a", "i1"));
  assert.equal(h.future.length, 0, "a new change clears redo");
});

test("a slow save answer does not win over a newer one", () => {
  const gate = { generation: 0 };
  const first = beginSave(gate);
  const second = beginSave(gate);
  assert.equal(isCurrentSave(gate, first), false);
  assert.equal(isCurrentSave(gate, second), true);
});

test("entries move in their order and across sections at the edge", () => {
  let r = moveItemInOrder(doc(), "a", "i2", -1);
  assert.deepEqual(r.doc.blocks[0].items.map((i) => i.id), ["i2", "i1"]);
  r = moveItemInOrder(doc(), "a", "i2", 1);
  assert.equal(r.block, "b");
  assert.deepEqual(r.doc.blocks[1].items.map((i) => i.id), ["i2", "i3"]);
  r = moveItemInOrder(doc(), "b", "i3", 1);
  assert.equal(r.doc.blocks[1].items.length, 1, "last entry of the last section stays");
  const m = moveItemToBlock(doc(), "a", "i1", "b");
  assert.deepEqual(m.blocks[1].items.map((i) => i.id), ["i3", "i1"]);
  assert.deepEqual(moveBlockInOrder(doc(), "b", -1).blocks.map((b) => b.id), ["b", "a"]);
  const d0 = doc();
  assert.equal(moveBlockInOrder(d0, "a", -1), d0);
});

test("new entries and sections, company text wins over the library name", () => {
  const r = addItem(doc(), "b", { kind: "text", text: "Zusatz" });
  assert.equal(r.doc.blocks[1].items.at(-1)?.kind, "text");
  const nb = addBlock(doc(), "Kraft", "kraft", "#e03131", "E_Kraft");
  const s = nb.doc.blocks[2].style;
  assert.equal(s.header, "#e03131");
  assert.equal(s.header_text, "#ffffff");
  assert.equal(s.symbol, "#e03131", "parts without own colour take the layer colour");
  assert.equal(s.background_on, false);
  assert.equal(s.border_on, false);
  assert.equal(describe("lampe", "Lampe", { lampe: "Decken- / Wandlampenstelle" }), "Decken- / Wandlampenstelle");
  assert.equal(describe("spot", "Spot", {}), "Spot");
  assert.equal(sectionStyle("#ffffff").header, "#6b7280");
});

test("project comparison: missing and no longer used entries", () => {
  const rows = [
    { family_key: "lampe", title: "Lampe", total: 0, categories: ["licht"] },
    { family_key: "melder", title: "Melder", total: 3, categories: ["bma"] },
    { family_key: "neu", title: "Neu", total: 1, categories: ["bma"] },
  ];
  assert.deepEqual(missingRows(doc(), rows).map((r) => r.family_key), ["neu"]);
  assert.deepEqual([...staleItems(doc(), rows)].sort(), ["i1", "i2"]);
  assert.equal(blockForCategory(doc(), ["bma"], null), "b");
  assert.equal(blockForCategory(doc(), ["unbekannt"], "a"), "a");
});

test("drag and drop: move in front of an entry, into another section, insert new", () => {
  let d = moveItemTo(doc(), "a", "i2", "a", "i1");
  assert.deepEqual(d.blocks[0].items.map((i) => i.id), ["i2", "i1"]);
  d = moveItemTo(doc(), "a", "i1", "b", "i3");
  assert.deepEqual(d.blocks[1].items.map((i) => i.id), ["i1", "i3"]);
  d = moveItemTo(doc(), "a", "i1", "b", null);
  assert.deepEqual(d.blocks[1].items.map((i) => i.id), ["i3", "i1"]);
  const r = insertItem(doc(), "b", { kind: "symbol", family_key: "neu", symbol_key: "s:neu", text: "Neu" }, "i3");
  assert.deepEqual(r.doc.blocks[1].items.map((i) => i.id), [r.id, "i3"]);
  assert.equal(rotateItem(rotateItem(doc(), "a", "i1"), "a", "i1").blocks[0].items[0].rotation, 180);
  assert.equal(rotateItem(doc(), "a", "i1", 45).blocks[0].items[0].rotation, 45);
});

test("the same symbol in two plan colours is not a duplicate", () => {
  const blue = addItem(doc(), "b", { kind: "symbol", family_key: "dose", symbol_key: "s:dose", text: "Dose", color: "#0000ff" });
  const both = addItem(blue.doc, "b", { kind: "symbol", family_key: "dose", symbol_key: "s:dose", text: "Dose", color: "#ff0000" });
  assert.deepEqual([...duplicateItems(both.doc)], []);
});

test("duplicates in one section are marked, the first one and other sections are not", () => {
  const r = insertItem(doc(), "a", { kind: "symbol", family_key: "lampe", symbol_key: "s:lampe", text: "Lampe 2" }, null);
  assert.deepEqual([...duplicateItems(r.doc)], [r.id]);
  const other = insertItem(doc(), "b", { kind: "symbol", family_key: "lampe", symbol_key: "s:lampe", text: "Lampe BMA" }, null);
  assert.deepEqual([...duplicateItems(other.doc)], [], "same symbol in another section is intended");
  assert.equal(inLegend(doc(), "lampe", null), true);
  assert.equal(inLegend(doc(), "neu", null), false);
});

test("the general part: same text rule as the backend, hidden not deleted", () => {
  assert.equal(normText("Leitung, nach oben"), "leitung nach oben");
  assert.equal(normText("Unterscheidung UP / AP (halbausgefüllt)"), "unterscheidung up / ap halbausgefüllt");
  const g = { texts: ["decken melder"], symbol_keys: ["s:spot"], family_keys: [], covered: [] };
  const d = hideCovered(updateItem(doc(), "b", "i3", { text: "Decken-Melder" }), g);
  const hidden = d.blocks.flatMap((b) => b.items.filter((i) => i.hidden).map((i) => i.id));
  assert.deepEqual(hidden.sort(), ["i2", "i3"]);
  assert.equal(d.blocks.flatMap((b) => b.items).length, 3, "nothing deleted");
  const kept = updateItem(d, "b", "i3", { hidden: false, keep: true });
  assert.equal(hideCovered(kept, g), kept, "shown again on purpose stays");
  assert.equal(inGeneral({ ...d.blocks[0].items[0], kind: "text", text: "melder" }, g), false);
  const rows = [
    { family_key: "melder", title: "Melder", total: 1, categories: [] },
    { family_key: "neu", title: "Neu", total: 1, categories: [] },
  ];
  assert.deepEqual(missingRows(d, rows, new Set(["neu"])).map((r) => r.family_key), ["melder"]);
  assert.deepEqual(coveredRows(rows, new Set(["neu"])).map((r) => r.family_key), ["neu"]);
});


test("cells: an occupied cell makes room, an empty cell keeps the others in place", () => {
  const six = { ...doc(), blocks: [{ ...doc().blocks[0], items: ["a1", "a2", "a3", "b1", "b2", "b3", "c1"].map((id) => item(id, id)) }, doc().blocks[1]] };
  const ids = (d: LegendDoc, b = 0) => d.blocks[b].items.map((it) => (it.kind === "gap" ? "_" : it.id));
  // 3 columns of 3: c1 to the bottom of the third column (cell 8), cells 6 and 7 stay empty
  const bottom = placeInCell(six, "a", 8, { block: "a", item: "c1" });
  assert.deepEqual(ids(bottom), ["a1", "a2", "a3", "b1", "b2", "b3", "_", "_", "c1"]);
  // phone-like: a1 onto b2 (cell 4), the entries in between move up by one
  assert.deepEqual(ids(placeInCell(six, "a", 4, { block: "a", item: "a1" })), ["a2", "a3", "b1", "b2", "a1", "b3", "c1"]);
  // a new entry onto an occupied cell pushes the others on, up to the next empty cell
  const added = placeInCell(bottom, "a", 1, { item: item("n", "n") });
  assert.deepEqual(ids(added), ["a1", "n", "a2", "a3", "b1", "b2", "b3", "_", "c1"]);
  // from another section: the source closes up, the empty cells at its end go
  const moved = placeInCell(bottom, "b", 0, { block: "a", item: "c1" });
  assert.deepEqual(ids(moved), ["a1", "a2", "a3", "b1", "b2", "b3"]);
  assert.deepEqual(ids(moved, 1), ["c1", "i3"]);
  // onto its own cell: nothing changes
  assert.equal(placeInCell(six, "a", 6, { block: "a", item: "c1" }), six);
});
