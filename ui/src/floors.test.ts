// Run: npm test  (Node 22, no extra packages)
import { test } from "node:test";
import assert from "node:assert/strict";
import { floorNameFor, floorNameFromFilename, matchPlan, planFiles } from "./floors.ts";

test("floor names from file names, a numbered floor wins over a bare EG", () => {
  assert.equal(floorNameFromFilename("3_1.OG.dxf"), "1. OG");
  assert.equal(floorNameFromFilename("EG_2.OG.n4d"), "2. OG");
  assert.equal(floorNameFromFilename("Projekt_EG.dwg"), "EG");
  assert.equal(floorNameFromFilename("Haus UG.dxf"), "UG");
  assert.equal(floorNameFor("Dachstock.dxf"), "Dachstock");
});

test("only plan files, and a matching floor gets a new plan version", () => {
  const files = [{ name: "a.dxf" }, { name: "b.PDF" }, { name: "c.N4D" }, { name: "d.dwg" }, { name: "gro04p.n4m" }];
  assert.deepEqual(planFiles(files).map((f) => f.name), ["a.dxf", "c.N4D", "d.dwg", "gro04p.n4m"]);
  assert.equal(floorNameFor("1371_E-G-1OG.n4d"), "1. OG");
  assert.equal(floorNameFor("gro04p.n4m"), "gro04p");
  const plans = [{ id: 1, name: "1. OG" }, { id: 2, name: "EG" }];
  assert.equal(matchPlan("1.OG", plans)?.id, 1);
  assert.equal(matchPlan("eg", plans)?.id, 2);
  assert.equal(matchPlan("UG", plans), undefined);
  assert.equal(matchPlan("", plans), undefined);
});
