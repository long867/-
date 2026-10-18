"use client";
import { Pause, Play } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { usePageMotion } from "@/hooks/use-page-motion";

/** Let readers pause visual effects while preserving the static data display. */
export function MotionControl({ compact = false }: { compact?: boolean }) {
  const { t } = usePreferences();
  const { paused, reduced, toggle } = usePageMotion();
  return (
    <button
      className={compact ? "icon-button motion-toggle" : "atlas-motion-control"}
      onClick={toggle}
      aria-pressed={paused || reduced}
      disabled={reduced}
      title={
        reduced
          ? t(
              "系统已设置减少动态效果",
              "Reduced motion is enabled in system settings",
            )
          : t("全站动效控制", "Site animation controls")
      }
      aria-label={
        reduced
          ? t("系统已减少动态效果", "System reduced motion enabled")
          : paused
            ? t("播放视觉动画", "Play visual animations")
            : t("暂停视觉动画", "Pause visual animations")
      }
    >
      {paused || reduced ? (
        <Play size={compact ? 16 : 11} />
      ) : (
        <Pause size={compact ? 16 : 11} />
      )}
      <span className={compact ? "sr-only" : undefined}>
        {paused ? t("播放", "Play") : t("暂停", "Pause")}
      </span>
    </button>
  );
}
