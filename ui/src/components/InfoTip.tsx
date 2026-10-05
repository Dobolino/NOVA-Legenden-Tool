import { useEffect, useRef, useState } from "react";

/** Small "i". The explanation shows on hover, focus, or click, and stays out of the form. */
export default function InfoTip({ text }: { text: string }) {
  const btn = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, above: false });

  function place() {
    const r = btn.current?.getBoundingClientRect();
    if (!r) return;
    const width = 260;
    const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8));
    const above = r.bottom + 140 > window.innerHeight;
    setPos({ top: above ? r.top - 6 : r.bottom + 6, left, above });
  }

  function show() {
    place();
    setOpen(true);
  }

  useEffect(() => {
    if (!pinned) return;
    const close = (e: Event) => {
      if (btn.current?.contains(e.target as Node)) return;
      setPinned(false);
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPinned(false);
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [pinned]);

  const visible = open || pinned;
  return (
    <button
      ref={btn}
      type="button"
      className="info-tip"
      aria-label="Hinweis"
      aria-expanded={visible}
      onMouseEnter={show}
      onMouseLeave={() => { if (!pinned) setOpen(false); }}
      onFocus={show}
      onBlur={() => { if (!pinned) setOpen(false); }}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        place();
        setPinned((v) => !v);
        setOpen(true);
      }}
    >
      i
      {visible && (
        <span className={`info-tip-pop ${pos.above ? "above" : ""}`} role="tooltip" style={{ top: pos.top, left: pos.left }}>
          {text}
        </span>
      )}
    </button>
  );
}
