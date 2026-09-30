// Run: npm test  (Node 22, no extra packages)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  addBlock,
  addItem,
  blockForCategory,
  commit,
  drawingSize,
  fitScale,
  historyOf,
  missingRows,
  moveBlockInOrder,
  moveItemToBlock,
  push,
  redo,
  removeItem,
  replace,
  snap,
  staleItems,
  undo,
  updateItem,
} from "./legend.ts";
import type { LegendDoc } from "./legend.ts";

const style = {
  font: "Arial", title_size: 5, heading_size: 3.5, text_size: 2.5, row: 4.55, text_offset: 9.75,
  column_width: 103.7, page_columns: 2, page_height: 220, margin: 10, grid: 0.5, plan_scale: 50,
};

function doc(): LegendDoc {
  return {
    version: 1,
    style,
    title: { text: "Legende", x: 10, y: 10, size: 5 },
    texts: [],
    blocks: [
      { id: "a", category_id: "licht", title: "Licht", x: 10, y: 21, columns: 1, spacing: 4.55, heading_size: 3.5, collapsed: false,
        items: [{ id: "i1", kind: "symbol", family_key: "lampe", symbol_key: "s1", text: "Lampe", x: 3.4, y: 8.6, scale: 1,
          text_size: 2.5, length_mm: null, width_mm: null, line_style: "solid", line_length: 8 }] },
      { id: "b", category_id: "bma", title: "BMA", x: 10, y: 40, columns: 1, spacing: 4.55, heading_size: 3.5, collapsed: false, items: [] },
    ],
  };
}

test("snap rounds to the grid and can be switched off", () => {
  assert.equal(snap(3.26, 0.5), 3.5);
  assert.equal(snap(3.24, 0.5), 3);
  assert.equal(snap(3.2449, 0.5, false), 3.245);
  assert.equal(snap(7, 2.5), 7.5);
});

test("undo and redo, a drag is one step", () => {
  let h = historyOf(doc());
  const start = h.present;
  h = push(h, updateItem(h.present, "a", "i1", { text: "Neu" }));
  assert.equal(h.present.blocks[0].items[0].text, "Neu");
  const beforeDrag = h.present;
  h = replace(h, updateItem(h.present, "a", "i1", { x: 5 }));
  h = replace(h, updateItem(h.present, "a", "i1", { x: 9 }));
  h = commit(h, beforeDrag);
  assert.equal(h.past.length, 2, "text change + one drag");
  h = undo(h);
  assert.equal(h.present, beforeDrag);
  h = undo(h);
  assert.equal(h.present, start);
  h = redo(redo(h));
  assert.equal(h.present.blocks[0].items[0].x, 9);
  h = push(undo(h), removeItem(h.present, "a", "i1"));
  assert.equal(h.future.length, 0, "a new change clears redo");
});

test("adding entries goes to the next row, blocks below the last one", () => {
  const r = addItem(doc(), "a", { kind: "note", text: "Hinweis" });
  const items = r.doc.blocks[0].items;
  assert.equal(items.length, 2);
  assert.equal(items[1].y, 13.15);
  assert.equal(items[1].x, 3.4);
  const empty = addItem(doc(), "b", { kind: "line", text: "UP-Wandleitung" });
  assert.equal(empty.doc.blocks[1].items[0].y, 3.5 * 1.8 + 4.55 / 2);
  const nb = addBlock(doc(), "Neu");
  assert.ok(nb.doc.blocks[2].y >= 40 + 3.5 * 1.8 + 4.55);
});

test("reorder blocks and move an entry to another block keeps its place on paper", () => {
  const d = moveBlockInOrder(doc(), "b", -1);
  assert.deepEqual(d.blocks.map((b) => b.id), ["b", "a"]);
  const d0 = doc();
  assert.equal(moveBlockInOrder(d0, "a", -1), d0, "first block cannot move up");
  const m = moveItemToBlock(doc(), "a", "i1", "b");
  const it = m.blocks[1].items[0];
  assert.equal(m.blocks[0].items.length, 0);
  assert.equal(it.y + m.blocks[1].y, 8.6 + 21);
});

test("project comparison: missing and no longer used entries", () => {
  const rows = [
    { family_key: "lampe", title: "Lampe", total: 0, categories: ["licht"] },
    { family_key: "melder", title: "Melder", total: 3, categories: ["bma"] },
  ];
  assert.deepEqual(missingRows(doc(), rows).map((r) => r.family_key), ["melder"]);
  assert.deepEqual([...staleItems(doc(), rows)], ["i1"]);
  assert.equal(blockForCategory(doc(), ["bma"], null), "b");
  assert.equal(blockForCategory(doc(), ["unbekannt"], "a"), "a");
});

test("large symbols shrink to the row like the backend rule", () => {
  assert.equal(fitScale(5, 5, 4.55, 9.75), 1);
  assert.equal(fitScale(12, 12, 4.55, 9.75), 0.4);
  assert.equal(fitScale(30, 3, 4.55, 9.75), 0.55);
  const s = drawingSize([-3.1, -3.1, 6.2, 6.2]);   // 5 mm symbol with 12 % padding
  assert.ok(Math.abs(s.w - 5) < 1e-9 && Math.abs(s.h - 5) < 1e-9);
});
