import { ReactNode, useEffect, useRef, useState } from "react";

/** Small drop-down menu for rarer actions. Closes after a choice, on Escape and on a click outside. */
export default function Menu({ label, disabled, children }: { label: string; disabled?: boolean; children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; right: number; maxHeight: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) {
        if (ref.current) ref.current.open = false;
      }
    };
    // Fixed position, so a scrolling table does not cut the menu off. Scrolling closes it.
    const rect = ref.current?.querySelector("summary")?.getBoundingClientRect();
    if (rect) {
      const below = window.innerHeight - rect.bottom - 12;
      setPos({ top: rect.bottom + 4, right: Math.max(8, window.innerWidth - rect.right), maxHeight: Math.max(160, below) });
    }
    const shut = () => {
      if (ref.current) ref.current.open = false;
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    window.addEventListener("scroll", shut, true);
    window.addEventListener("resize", shut);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
      window.removeEventListener("scroll", shut, true);
      window.removeEventListener("resize", shut);
    };
  }, [open]);

  return (
    <details ref={ref} className="menu" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary
        className="btn small"
        aria-disabled={disabled}
        onClick={(e) => disabled && e.preventDefault()}
        style={disabled ? { opacity: 0.5, cursor: "default" } : undefined}
      >
        {label} ▾
      </summary>
      {open && (
        <div
          className="menu-pop"
          role="menu"
          style={pos ? { position: "fixed", top: pos.top, right: pos.right, maxHeight: pos.maxHeight, overflowY: "auto" } : undefined}
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("button") && ref.current) ref.current.open = false;
          }}
        >
          {children}
        </div>
      )}
    </details>
  );
}
