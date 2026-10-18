"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { useIsFetching } from "@tanstack/react-query";
import { usePageMotion } from "@/hooks/use-page-motion";
import { usePreferences } from "@/hooks/use-preferences";
import { pageScene, sceneCardSelector } from "@/lib/page-scene.mjs";

/** Animate rendered content without changing queries, values or interactive state. */
export function SiteExperience({ children }: { children: ReactNode }) {
  const path = usePathname();
  const scene = pageScene(path);
  const surface = useRef<HTMLDivElement>(null);
  const { enabled } = usePageMotion();
  const { t } = usePreferences();
  const fetching = useIsFetching();

  useEffect(() => {
    const root = surface.current;
    if (!root || !enabled || !("IntersectionObserver" in window)) return;
    let scanFrame = 0,
      pointerFrame = 0;
    let pointer: { card: HTMLElement; x: number; y: number } | null = null;
    const seen = new WeakSet<Element>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const card = entry.target as HTMLElement;
          card.dataset.inView = String(entry.isIntersecting);
          if (entry.isIntersecting) card.dataset.entered = "true";
        }
      },
      { threshold: 0.06, rootMargin: "0px 0px -12px 0px" },
    );
    function scan() {
      scanFrame = 0;
      root!
        .querySelectorAll<HTMLElement>(sceneCardSelector)
        .forEach((card, i) => {
          if (seen.has(card)) return;
          seen.add(card);
          card.classList.add("scene-card");
          card.style.setProperty(
            "--entry-delay",
            `${Math.min((i % 5) * 45, 180)}ms`,
          );
          // Content is always visible; an observer only adds a brief entrance effect.
          observer.observe(card);
        });
    }
    const mutations = new MutationObserver((records) => {
      if (
        !scanFrame &&
        records.some((r) =>
          [...r.addedNodes].some((n) => n.nodeType === Node.ELEMENT_NODE),
        )
      )
        scanFrame = requestAnimationFrame(scan);
    });
    mutations.observe(root, { childList: true, subtree: true });
    scan();
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    function move(event: PointerEvent) {
      if (
        !fine.matches ||
        event.pointerType !== "mouse" ||
        !(event.target instanceof Element)
      )
        return;
      const card = event.target.closest<HTMLElement>(".scene-card");
      if (!card) return;
      pointer = { card, x: event.clientX, y: event.clientY };
      if (pointerFrame) return;
      pointerFrame = requestAnimationFrame(() => {
        pointerFrame = 0;
        if (!pointer) return;
        const rect = pointer.card.getBoundingClientRect();
        pointer.card.style.setProperty(
          "--glow-x",
          `${pointer.x - rect.left}px`,
        );
        pointer.card.style.setProperty("--glow-y", `${pointer.y - rect.top}px`);
      });
    }
    root.addEventListener("pointermove", move, { passive: true });
    return () => {
      observer.disconnect();
      mutations.disconnect();
      root.removeEventListener("pointermove", move);
      cancelAnimationFrame(scanFrame);
      cancelAnimationFrame(pointerFrame);
    };
  }, [path, enabled]);

  return (
    <div className="site-experience" data-scene={scene} data-route={path}>
      <div className="scene-atmosphere" aria-hidden="true">
        <div className="scene-aurora scene-aurora-one" />
        <div className="scene-aurora scene-aurora-two" />
        <svg
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          focusable="false"
        >
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <path
              key={i}
              className="geological-contour"
              d={`M${-240 + i * 30} ${260 + i * 60}C${260 + i * 20} ${-170 + i * 65} ${350 + i * 30} ${690 + i * 22} ${820 + i * 30} ${310 + i * 65}S${1380 + i * 80} ${460 + i * 20} 1720 ${80 + i * 85}`}
            />
          ))}
        </svg>
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <span
            className="scene-particle"
            key={i}
            style={{
              left: `${8 + i * 12}%`,
              top: `${20 + ((i * 17) % 70)}%`,
              animationDelay: `${-i * 2}s`,
            }}
          />
        ))}
      </div>
      <div
        className={`request-trace ${fetching ? "is-fetching" : ""}`}
        aria-hidden="true"
      >
        <span />
      </div>
      <span className="sr-only" role="status" aria-live="polite">
        {fetching ? t("正在读取页面数据", "Loading page data") : ""}
      </span>
      <div className="scene-content" ref={surface}>
        {children}
      </div>
    </div>
  );
}
