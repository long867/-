"use client";
import type { ReactNode } from "react";
import { usePreferences } from "@/hooks/use-preferences";
import { SceneGlyph } from "./scene-glyph";
import { usePathname } from "next/navigation";
import { workspaceLocation } from "@/lib/workspace-navigation.mjs";
import { WorkspaceIcon } from "./workspace-tools";
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
  const location = workspaceLocation(usePathname());
  return (
    <div className="page-heading scene-heading">
      <div className="heading-orbit-frame" aria-hidden="true">
        <span />
        <span />
      </div>
      <SceneGlyph />
      <div className="heading-copy">
        <div className="heading-kicker">
          <span className="heading-symbol">
            <WorkspaceIcon name={location.key} size={18} />
          </span>
          <div className="eyebrow">{eyebrow}</div>
        </div>
        <h1>{t(zh, en)}</h1>
        <p className="subtitle">
          {t(description, descriptionEn || description)}
        </p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </div>
  );
}
