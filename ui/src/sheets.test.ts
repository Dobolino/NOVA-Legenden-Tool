// Run: npm test  (Node 22, no extra packages)
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseSheets } from "./sheets.ts";

test("two ranges separated by comma", () => {
  assert.deepEqual(parseSheets("230, 240"), ["230", "240"]);
});

test("trailing comma while typing is not a range", () => {
  assert.deepEqual(parseSheets("230,"), ["230"]);
});

test("empty and duplicate entries are dropped", () => {
  assert.deepEqual(parseSheets(" 230 ,, 240, 230 ,"), ["230", "240"]);
});
