"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { normalizeWatchlist } from "@/lib/observation.mjs";

const key = "mi-mineral-watchlist-v1";
const Context = createContext<{
  names: string[];
  ready: boolean;
  toggle: (name: string) => void;
} | null>(null);

/** Share optional browser-local observations across the home and market pages. */
export function MineralWatchlistProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [names, setNames] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const read = () => {
      try {
        setNames(
          normalizeWatchlist(JSON.parse(localStorage.getItem(key) || "[]")),
        );
      } catch {
        setNames([]);
      }
      setReady(true);
    };
    const sync = (event: StorageEvent) => {
      if (event.key === key || event.key === null) read();
    };
    read();
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  const toggle = useCallback((name: string) => {
    if (normalizeWatchlist([name]).length !== 1) return;
    setNames((previous) => {
      const next = previous.includes(name)
        ? previous.filter((value) => value !== name)
        : normalizeWatchlist([...previous, name]);
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        /* Optional storage. */
      }
      return next;
    });
  }, []);
  return (
    <Context.Provider value={{ names, ready, toggle }}>
      {children}
    </Context.Provider>
  );
}

export function useMineralWatchlist() {
  const context = useContext(Context);
  if (!context) throw new Error("MineralWatchlistProvider missing");
  return context;
}
