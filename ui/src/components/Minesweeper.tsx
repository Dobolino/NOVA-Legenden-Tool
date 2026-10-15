import { useEffect, useState, type CSSProperties } from "react";
import { Cell, CREDIT, SIZE, cleared, emptyBoard, minesLeft, placeMines, playClearChime, reveal, toggleFlag } from "../minesweeper";

/** Direction, spin and stagger so each mine tile leaves the blast on its own path. */
function flight(index: number, origin: number): CSSProperties {
  const ox = origin % SIZE;
  const oy = Math.floor(origin / SIZE);
  const x = index % SIZE;
  const y = Math.floor(index / SIZE);
  let dx = x - ox;
  let dy = y - oy;
  if (dx === 0 && dy === 0) {
    dx = 0.45;
    dy = -1;
  }
  const len = Math.hypot(dx, dy);
  const reach = 240 + len * 48;
  const spin = (dx >= 0 ? 1 : -1) * (180 + Math.round(len * 55));
  return {
    "--dx": `${Math.round((dx / len) * reach)}px`,
    "--dy": `${Math.round((dy / len) * reach - 56)}px`,
    "--spin": `${spin}deg`,
    "--delay": `${index === origin ? 0 : Math.round(140 + len * 85)}ms`,
  } as CSSProperties;
}

/** Hidden field. The credit line appears only after the field is cleared. */
export default function Minesweeper({ onClose }: { onClose: () => void }) {
  const [board, setBoard] = useState<Cell[]>(emptyBoard);
  const [armed, setArmed] = useState(false);
  const [lost, setLost] = useState(false);
  const [flagMode, setFlagMode] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [blast, setBlast] = useState<number | null>(null);

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
    setBlast(null);
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
      setBlast(index);
      setLost(true);
      return;
    }
    const next = reveal(current, index);
    setBoard(next);
    if (cleared(next)) playClearChime();
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
        className={`modal mine-modal ${blast !== null ? "is-blast" : ""} ${won ? "is-won" : ""}`}
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
          {blast !== null && (
            <span
              className="mine-fx"
              style={{
                left: `calc(${blast % SIZE} * ((100% - 16px) / ${SIZE} + 2px) + (100% - 16px) / ${SIZE} / 2)`,
                top: `calc(${Math.floor(blast / SIZE)} * ((100% - 16px) / ${SIZE} + 2px) + (100% - 16px) / ${SIZE} / 2)`,
              }}
            >
              <span className="mine-wave" />
              <span className="mine-wave late" />
              <span className="mine-flash" />
            </span>
          )}
          {board.map((cell, index) => {
            const flying = blast !== null && cell.mine;
            const label = cell.flag ? "Fahne" : cell.open ? (cell.mine ? "Mine" : cell.near ? String(cell.near) : "Leer") : "Zu";
            return (
              <button
                key={index}
                type="button"
                className={`mine-cell ${cell.open ? "open" : ""} ${cell.mine && cell.open ? "mine" : ""} ${flying ? "fly" : ""} ${blast === index ? "epicenter" : ""} n${cell.near}`}
                style={flying ? flight(index, blast) : undefined}
                aria-label={label}
                onClick={() => onCell(index, false)}
                onContextMenu={(e) => {
                  e.preventDefault();
                  onCell(index, true);
                }}
              >
                {flying ? (
                  <>
                    <span className="mine-core" />
                    <span className="mine-spark s1" />
                    <span className="mine-spark s2" />
                    <span className="mine-spark s3" />
                    <span className="mine-spark s4" />
                  </>
                ) : cell.flag && !cell.open ? "⚑" : cell.open && cell.near ? cell.near : ""}
              </button>
            );
          })}
        </div>
        {won && (
          <div className="mine-credit" role="status" aria-label={CREDIT}>
            <span className="mine-credit-kicker">Invented and Created by</span>
            <strong className="mine-credit-name">Nico Strauss</strong>
            <span className="mine-credit-join">und</span>
            <strong className="mine-credit-name">Alexandre Dürger</strong>
          </div>
        )}
        {lost && <p className="hint mine-status">Getroffen. Noch einmal mit Neu.</p>}
      </div>
    </div>
  );
}
