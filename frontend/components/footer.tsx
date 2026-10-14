"use client";
import Link from "next/link";
import { Mountain, ArrowUpRight } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { SubscriptionDialog } from "./subscription-dialog";
export function Footer() {
  const { t } = usePreferences();
  return (
    <footer className="site-footer">
      <div className="footer-top">
        <div>
          <Link href="/" className="brand">
            <Mountain size={23} />
            MiningIntel
          </Link>
          <p className="subtitle">
            {t(
              "看见资源的流向，看清世界的动向。",
              "Know where resources flow. See where the world goes.",
            )}
          </p>
        </div>
        <div className="footer-links">
          <Link href="/frontier">{t("前沿成果", "Research frontiers")}</Link>
          <Link href="/about">{t("关于平台", "About")}</Link>
          <a href="/api-docs">
            {t("开放 API", "Open API")}
            <ArrowUpRight size={12} />
          </a>
          <Link href="/bookmarks">{t("我的收藏", "Saved")}</Link>
          <SubscriptionDialog compact />
        </div>
      </div>
      <div className="footer-bottom">
        <span>© {new Date().getFullYear()} MiningIntel</span>
        <span>
          {t(
            "原文可追溯 · 数据有口径 · 洞察有依据",
            "Original sources. Clear methodology. Grounded insights.",
          )}
        </span>
      </div>
    </footer>
  );
}
