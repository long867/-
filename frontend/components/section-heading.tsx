"use client";
import type { ReactNode } from "react";
import { usePreferences } from "@/hooks/use-preferences";
import { SceneGlyph } from "./scene-glyph";
export function SectionHeading({
  eyebrow,
  zh,
  en,
  description,
  descriptionEn,
  actions,
}: {
  eyebrow: string;
  zh: string;
  en: string;
  description: string;
  descriptionEn?: string;
  actions?: ReactNode;
}) {
  const { t } = usePreferences();
  return (
    <div className="page-heading scene-heading">
      <div className="heading-orbit-frame" aria-hidden="true">
        <span />
        <span />
      </div>
      <SceneGlyph />
      <div className="heading-copy">
        <div className="eyebrow">{eyebrow}</div>
        <h1>{t(zh, en)}</h1>
        <p className="subtitle">
          {t(description, descriptionEn || description)}
        </p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </div>
  );
}
