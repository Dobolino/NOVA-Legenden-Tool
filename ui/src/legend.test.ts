// Run: npm test  (Node 22, no extra packages)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  addBlock,
  addItem,
  beginSave,
  blockForCategory,
  commit,
  describe,
  historyOf,
  isCurrentSave,
  missingRows,
  moveBlockInOrder,
  moveItemInOrder,
  moveItemToBlock,
  push,
  redo,
  removeItem,
  replace,
  sectionStyle,
  staleItems,
  undo,
  updateItem,
} from "./legend.ts";
import type { LegendDoc } from "./legend.ts";

const style = {
  font: "Arial", text_size: 2.5, symbol_scale: 1, grid: "standard", row: 4.55, text_offset: 9.75,
  columns: 2, width: 200, margin: 5, plan_scale: 50,
};

function item(id: string, family: string | null) {
  return { id, kind: "symbol" as const, family_key: family, symbol_key: family ? `s:${family}` : null, text: id,
    length_mm: null, width_mm: null, line_style: "solid" as const, line_length: 8 };
}

function doc(): LegendDoc {
  return {
    version: 2,
    style,
    title: { text: "Legende" },
    blocks: [
      { id: "a", category_id: "licht", title: "Licht", layer: "E_Licht", collapsed: false, style: sectionStyle("#1971c2"),
        items: [item("i1", "lampe"), item("i2", "spot")] },
      { id: "b", category_id: "bma", title: "BMA", layer: "", collapsed: false, style: sectionStyle(null), items: [item("i3", "melder")] },
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
  assert.equal(s.symbol, "#e03131");
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
