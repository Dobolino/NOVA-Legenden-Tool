import { useLayoutEffect, useRef } from "react";
import type { RefObject } from "react";

/** Keep keyboard navigation inside a dialog and return focus to its trigger. */
export function useDialogFocus(ref: RefObject<HTMLElement | null>, close: () => void | Promise<void>, busy = false) {
  const previous = useRef(document.activeElement as HTMLElement | null);
  const latest = useRef({ close, busy });
  latest.current = { close, busy };

  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]',
    )).filter((node) => node.getClientRects().length > 0);
    if (!dialog.contains(document.activeElement)) (controls()[0] ?? dialog).focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !latest.current.busy) {
        event.preventDefault();
        void latest.current.close();
      }
      if (event.key !== "Tab") return;
      const nodes = controls();
      const first = nodes[0] ?? dialog;
      const last = nodes[nodes.length - 1] ?? dialog;
      if (!dialog.contains(document.activeElement) || (event.shiftKey ? document.activeElement === first : document.activeElement === last)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      if (previous.current?.isConnected) previous.current.focus();
    };
  }, [ref]);
}
