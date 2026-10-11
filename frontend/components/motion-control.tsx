"use client";
import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";

/** Let readers pause visual effects while preserving the static data display. */
export function MotionControl() {
  const { t } = usePreferences();
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    try {
      setPaused(localStorage.getItem("mi-motion") === "paused");
    } catch {
      /* Storage is optional. */
    }
  }, []);
  function toggle() {
    const next = !paused;
    setPaused(next);
    document.documentElement.dataset.motion = next ? "paused" : "running";
    try {
      localStorage.setItem("mi-motion", next ? "paused" : "running");
    } catch {
      /* Keep the current session preference. */
    }
  }
  return (
    <button
      className="atlas-motion-control"
      onClick={toggle}
      aria-pressed={paused}
      aria-label={
        paused
          ? t("播放视觉动画", "Play visual animations")
          : t("暂停视觉动画", "Pause visual animations")
      }
    >
      {paused ? <Play size={11} /> : <Pause size={11} />}
      <span>{paused ? t("播放", "Play") : t("暂停", "Pause")}</span>
    </button>
  );
}
