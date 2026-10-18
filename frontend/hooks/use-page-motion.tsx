"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

interface PageMotion {
  enabled: boolean;
  paused: boolean;
  reduced: boolean;
  toggle: () => void;
}
const Context = createContext<PageMotion | null>(null);

/** Share one motion preference across charts, the globe and decorative effects. */
export function PageMotionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState({
    ready: false,
    paused: false,
    reduced: false,
    visible: true,
  });
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () =>
      setState({
        ready: true,
        paused: document.documentElement.dataset.motion === "paused",
        reduced: media.matches,
        visible: !document.hidden,
      });
    const storage = (event: StorageEvent) => {
      if (event.key === "mi-motion")
        document.documentElement.dataset.motion =
          event.newValue === "paused" ? "paused" : "running";
    };
    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-motion"],
    });
    media.addEventListener("change", sync);
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("storage", storage);
    sync();
    return () => {
      observer.disconnect();
      media.removeEventListener("change", sync);
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("storage", storage);
    };
  }, []);
  const enabled =
    state.ready && !state.paused && !state.reduced && state.visible;
  useEffect(() => {
    document.documentElement.dataset.visuals = enabled ? "on" : "off";
  }, [enabled]);
  function toggle() {
    const next =
      document.documentElement.dataset.motion !== "paused"
        ? "paused"
        : "running";
    document.documentElement.dataset.motion = next;
    try {
      localStorage.setItem("mi-motion", next);
    } catch {
      /* Storage is optional. */
    }
  }
  return (
    <Context.Provider
      value={{ enabled, paused: state.paused, reduced: state.reduced, toggle }}
    >
      {children}
    </Context.Provider>
  );
}

export function usePageMotion(): PageMotion {
  const context = useContext(Context);
  if (!context) throw new Error("PageMotionProvider missing");
  return context;
}
