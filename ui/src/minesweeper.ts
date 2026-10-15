/** Beginner field. The first opened cell is never a mine. */

export const SIZE = 9;
export const MINES = 10;

export interface Cell {
  mine: boolean;
  open: boolean;
  flag: boolean;
  near: number;
}

export function emptyBoard(): Cell[] {
  return Array.from({ length: SIZE * SIZE }, () => ({ mine: false, open: false, flag: false, near: 0 }));
}

export function neighbours(index: number): number[] {
  const x = index % SIZE;
  const y = Math.floor(index / SIZE);
  const out: number[] = [];
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (!dx && !dy) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx >= 0 && ny >= 0 && nx < SIZE && ny < SIZE) out.push(ny * SIZE + nx);
    }
  }
  return out;
}

export function placeMines(board: Cell[], safe: number, random: () => number = Math.random): Cell[] {
  const next = board.map((cell) => ({ ...cell, mine: false, near: 0 }));
  const spots = next.map((_, i) => i).filter((i) => i !== safe);
  for (let n = 0; n < MINES && spots.length; n++) {
    const pick = Math.min(spots.length - 1, Math.floor(random() * spots.length));
    next[spots.splice(pick, 1)[0]].mine = true;
  }
  next.forEach((cell, i) => {
    if (!cell.mine) cell.near = neighbours(i).filter((j) => next[j].mine).length;
  });
  return next;
}

export function reveal(board: Cell[], index: number): Cell[] {
  const cell = board[index];
  if (!cell || cell.open || cell.flag) return board;
  const next = board.map((item) => ({ ...item }));
  const stack = [index];
  while (stack.length) {
    const i = stack.pop()!;
    if (next[i].open || next[i].flag) continue;
    next[i].open = true;
    if (next[i].mine || next[i].near) continue;
    for (const n of neighbours(i)) if (!next[n].open) stack.push(n);
  }
  return next;
}

export function toggleFlag(board: Cell[], index: number): Cell[] {
  const cell = board[index];
  if (!cell || cell.open) return board;
  const next = board.map((item) => ({ ...item }));
  next[index] = { ...cell, flag: !cell.flag };
  return next;
}

export function cleared(board: Cell[]): boolean {
  return board.length > 0 && board.every((cell) => cell.mine || cell.open) && board.some((cell) => cell.mine);
}

export function minesLeft(board: Cell[]): number {
  const flagged = board.filter((cell) => cell.flag).length;
  const mines = board.filter((cell) => cell.mine).length;
  return (mines || MINES) - flagged;
}
