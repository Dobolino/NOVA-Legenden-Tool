import { test } from "node:test";
import assert from "node:assert/strict";
import { cleared, emptyBoard, minesLeft, placeMines, playClearChime, reveal, toggleFlag, CREDIT, MINES, SIZE } from "./minesweeper.ts";

function sequence(values: number[]) {
  let i = 0;
  return () => values[i++ % values.length];
}

test("the first cell stays clear and the field has the beginner mine count", () => {
  const board = placeMines(emptyBoard(), 0, sequence([0, 0.5, 0.9, 0.2, 0.7, 0.1, 0.4, 0.8, 0.3, 0.6]));
  assert.equal(board[0].mine, false);
  assert.equal(board.filter((cell) => cell.mine).length, MINES);
  assert.equal(board.length, SIZE * SIZE);
  assert.equal(minesLeft(board), MINES);
});

test("an empty cell opens its neighbours and a flag stays closed", () => {
  const board = placeMines(emptyBoard(), 0, () => 0.99);
  const opened = reveal(board, 0);
  assert.equal(opened[0].open, true);
  assert.ok(opened.filter((cell) => cell.open).length > 1);
  const flagged = toggleFlag(opened, opened.findIndex((cell) => !cell.open));
  const index = flagged.findIndex((cell) => cell.flag);
  assert.equal(reveal(flagged, index)[index].open, false);
});

test("the hidden credit names Nico Strauss and Alexandre Dürger", () => {
  assert.equal(CREDIT, "Invented and Created by Nico Strauss und Alexandre Dürger");
  assert.doesNotThrow(() => playClearChime());
});

test("the field is cleared only when every safe cell is open", () => {
  let board = placeMines(emptyBoard(), 0, () => 0.99);
  assert.equal(cleared(board), false);
  board.forEach((cell, index) => {
    if (!cell.mine) board = reveal(board, index);
  });
  assert.equal(cleared(board), true);
  assert.equal(board.some((cell) => cell.mine && cell.open), false);
});
