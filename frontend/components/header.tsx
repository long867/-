"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Mountain,
  Search,
  Sun,
  Moon,
  Menu,
  X,
  ArrowUpRight,
  Bookmark,
  Bell,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
export function Header() {
  const path = usePathname();
  const auth = useAuth();
  const { t, theme, toggleTheme, toggleLanguage, language } = usePreferences();
  const [open, setOpen] = useState(false);
  const links = [
    ["/", "情报中心", "Intelligence"],
    ["/minerals", "矿种", "Minerals"],
    ["/regions", "地区", "Regions"],
    ["/policies", "政策", "Policy"],
    ["/trends", "趋势", "Trends"],
    ["/digest", "简报", "Briefs"],
    ["/chat", "AI 咨询", "Ask AI"],
    ...(auth.user?.is_admin ? [["/admin", "管理", "Admin"]] : []),
  ];
  return (
    <header className="header">
      <Link
        href="/"
        prefetch={false}
        className="brand"
        aria-label="MiningIntel 首页 / Home"
      >
        <span className="brand-emblem">
          <Mountain size={25} strokeWidth={1.4} />
        </span>
        <span>
          Mining<span className="text-primary">Intel</span>
          <small>THE RESOURCE OBSERVATORY</small>
        </span>
      </Link>
      <nav className="main-nav" aria-label={t("主导航", "Main navigation")}>
        {links.map(([href, zh, en]) => (
          <Link
            key={href}
            href={href}
            prefetch={false}
            className={
              path === href || (href !== "/" && path.startsWith(href))
                ? "active"
                : ""
            }
            aria-current={path === href ? "page" : undefined}
          >
            {t(zh, en)}
          </Link>
        ))}
      </nav>
      <div className="header-actions">
        <Link
          className="icon-button"
          href="/search"
          prefetch={false}
          aria-label={t("全局搜索", "Global search")}
        >
          <Search size={16} />
        </Link>
        <Link
          className="icon-button hidden xl:inline-flex"
          href="/bookmarks"
          prefetch={false}
          aria-label={t("我的收藏", "Saved articles")}
        >
          <Bookmark size={15} />
        </Link>
        <button
          className="icon-button language-toggle"
          onClick={toggleLanguage}
          aria-label={language === "zh" ? "Switch to English" : "切换中文"}
        >
          {language === "zh" ? "EN" : "中"}
        </button>
        <button
          className="icon-button"
          onClick={toggleTheme}
          aria-label={
            theme === "dark"
              ? t("切换亮色模式", "Switch to light mode")
              : t("切换暗色模式", "Switch to dark mode")
          }
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        {auth.user ? (
          <>
            <Link
              className="icon-button hidden md:inline-flex"
              href="/notifications"
              prefetch={false}
              aria-label={t("消息中心", "Notifications")}
            >
              <Bell size={16} />
            </Link>
            <button className="login-link" onClick={auth.logout}>
              {t("退出", "Sign out")}
            </button>
          </>
        ) : (
          <Link className="login-link" href="/login" prefetch={false}>
            {t("登录", "Sign in")}
            <ArrowUpRight size={12} />
          </Link>
        )}
        <button
          className="icon-button mobile-menu"
          aria-label={t("打开导航", "Open navigation")}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>
      <nav
        className={`mobile-nav ${open ? "open" : ""}`}
        aria-label={t("移动导航", "Mobile navigation")}
      >
        {links.map(([href, zh, en]) => (
          <Link key={href} href={href} onClick={() => setOpen(false)}>
            {t(zh, en)}
          </Link>
        ))}
        <Link href="/subscriptions" onClick={() => setOpen(false)}>
          {t("我的订阅", "Subscriptions")}
        </Link>
        <Link href="/notifications" onClick={() => setOpen(false)}>
          {t("消息中心", "Notifications")}
        </Link>
      </nav>
    </header>
  );
}
