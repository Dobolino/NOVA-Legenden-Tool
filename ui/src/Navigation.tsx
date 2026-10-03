import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

interface PendingSave {
  flush: () => Promise<void>;
  dirty: () => boolean;
}

interface Navigation {
  register: (save: PendingSave) => () => void;
  navigate: (action: () => void | Promise<void>) => Promise<boolean>;
  pending: boolean;
}

const Context = createContext<Navigation | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const saves = useRef(new Set<PendingSave>());
  const switching = useRef(false);
  const [pending, setPending] = useState(false);
  const register = useCallback((save: PendingSave) => {
    saves.current.add(save);
    return () => { saves.current.delete(save); };
  }, []);
  const navigate = useCallback(async (action: () => void | Promise<void>) => {
    if (switching.current) return false;
    switching.current = true;
    setPending(true);
    try {
      for (const save of saves.current) await save.flush();
      await action();
      return true;
    } catch {
      // The editor displays the save error and retains the document for a retry.
      return false;
    } finally {
      switching.current = false;
      setPending(false);
    }
  }, []);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (![...saves.current].some(save => save.dirty())) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  const value = useMemo(() => ({ register, navigate, pending }), [register, navigate, pending]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useNavigation() {
  const value = useContext(Context);
  if (!value) throw new Error("NavigationProvider fehlt");
  return value;
}
