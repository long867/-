"use client";
import { LazyMotion, m } from "framer-motion";
import type { ReactNode } from "react";
import { usePageMotion } from "@/hooks/use-page-motion";
const loadFeatures = () => import("./motion-features").then((x) => x.default);
/** Rich interactions stay on the inbox route, away from homepage critical JS. */
export function AnimatedPanel({
  className,
  children,
}: {
  className: string;
  children: ReactNode;
}) {
  const { enabled } = usePageMotion();
  return (
    <LazyMotion features={loadFeatures} strict>
      <m.article
        className={className}
        whileHover={enabled ? { y: -2 } : undefined}
        transition={{ duration: 0.2 }}
      >
        {children}
      </m.article>
    </LazyMotion>
  );
}
