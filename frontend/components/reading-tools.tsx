"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { ArrowUp } from "lucide-react";
import { usePageMotion } from "@/hooks/use-page-motion";
import { usePreferences } from "@/hooks/use-preferences";

/** Track actual page progress with one passive listener and no per-frame renders. */
export function ReadingTools() {
  const path = usePathname();
  const progress = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const { enabled } = usePageMotion();
  const { t } = usePreferences();
  useEffect(() => {
    let frame = 0;
    function update() {
      frame = 0;
      const distance = document.documentElement.scrollHeight - innerHeight;
      const ratio =
        distance > 0 ? Math.min(1, Math.max(0, scrollY / distance)) : 0;
      if (progress.current)
        progress.current.style.transform = `scaleX(${ratio})`;
      if (button.current) {
        button.current.hidden = scrollY < 640;
        button.current.style.setProperty("--reading-progress", String(ratio));
      }
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update);
    }
    const resize = new ResizeObserver(schedule);
    resize.observe(document.body);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule, { passive: true });
    update();
    return () => {
      resize.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      cancelAnimationFrame(frame);
    };
  }, [path]);
  return (
    <>
      <div className="reading-progress" aria-hidden="true">
        <span ref={progress} />
      </div>
      <button
        type="button"
        className="reading-top"
        ref={button}
        hidden
        aria-label={t("返回页面顶部", "Back to top")}
        onClick={() =>
          window.scrollTo({ top: 0, behavior: enabled ? "smooth" : "auto" })
        }
      >
        <svg viewBox="0 0 44 44" aria-hidden="true">
          <circle cx="22" cy="22" r="20" />
          <circle
            className="reading-ring"
            cx="22"
            cy="22"
            r="20"
            pathLength="1"
          />
        </svg>
        <ArrowUp size={17} />
      </button>
    </>
  );
}
