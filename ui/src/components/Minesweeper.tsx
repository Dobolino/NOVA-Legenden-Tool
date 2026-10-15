import { useEffect, useState } from "react";
import { Cell, SIZE, cleared, emptyBoard, minesLeft, placeMines, reveal, toggleFlag } from "../minesweeper";

const CREDIT = "Invented and Created by Nico Strass und Alexandre Dürger";

/** Hidden field. The credit line appears only after the field is cleared. */
export default function Minesweeper({ onClose }: { onClose: () => void }) {
  const [board, setBoard] = useState<Cell[]>(emptyBoard);
  const [armed, setArmed] = useState(false);
  const [lost, setLost] = useState(false);
  const [flagMode, setFlagMode] = useState(false);
  const [seconds, setSeconds] = useState(0);

  const won = cleared(board);
  const running = armed && !lost && !won;

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setSeconds((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function reset() {
    setBoard(emptyBoard());
    setArmed(false);
    setLost(false);
    setSeconds(0);
  }

  function open(index: number) {
    if (lost || won) return;
    let current = board;
    if (!armed) {
      current = placeMines(board, index);
      setArmed(true);
    }
    const cell = current[index];
    if (cell.flag) return;
    if (cell.mine) {
      setBoard(current.map((item) => (item.mine ? { ...item, open: true } : item)));
      setLost(true);
      return;
    }
    setBoard(reveal(current, index));
  }

  function onCell(index: number, flag: boolean) {
    if (lost || won) return;
    if ((flag || flagMode) && armed) {
      setBoard(toggleFlag(board, index));
      return;
    }
    open(index);
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div
        className="modal mine-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Minenfeld"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mine-bar">
          <span className="mine-count" aria-label="Verbleibende Minen">{String(minesLeft(board)).padStart(2, "0")}</span>
          <button type="button" className="btn small" onClick={reset}>Neu</button>
          <button
            type="button"
            className={`btn small ${flagMode ? "is-on" : ""}`}
            aria-pressed={flagMode}
            onClick={() => setFlagMode((v) => !v)}
            title="Linksklick setzt eine Fahne"
          >
            Fahne
          </button>
          <span className="mine-count" aria-label="Sekunden">{String(seconds).padStart(3, "0")}</span>
          <button type="button" className="btn small" onClick={onClose} aria-label="Schliessen">Schliessen</button>
        </div>
        <div className="mine-grid" style={{ gridTemplateColumns: `repeat(${SIZE}, 1fr)` }}>
          {board.map((cell, index) => {
            const label = cell.flag ? "Fahne" : cell.open ? (cell.mine ? "Mine" : cell.near ? String(cell.near) : "Leer") : "Zu";
            return (
              <button
                key={index}
                type="button"
                className={`mine-cell ${cell.open ? "open" : ""} ${cell.mine && cell.open ? "mine" : ""} n${cell.near}`}
                aria-label={label}
                onClick={() => onCell(index, false)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  onCell(index, true);
                }}
              >
                {cell.flag && !cell.open ? "⚑" : cell.open && cell.mine ? "●" : cell.open && cell.near ? cell.near : ""}
              </button>
            );
          })}
        </div>
        {won && <p className="mine-credit">{CREDIT}</p>}
        {lost && <p className="hint mine-status">Getroffen. Noch einmal mit Neu.</p>}
      </div>
    </div>
  );
}
