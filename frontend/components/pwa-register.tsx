"use client";
import { useEffect } from "react";
export function PwaRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      const register = () =>
        navigator.serviceWorker.register("/sw.js").catch(() => undefined);
      if (document.readyState === "complete") register();
      else {
        window.addEventListener("load", register, { once: true });
        return () => window.removeEventListener("load", register);
      }
    }
  }, []);
  return null;
}
