"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
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
  House,
  FileText,
  TrendingUp,
  MessagesSquare,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { AGENT_NAME } from "@/lib/branding";
export function Header() {
  const path = usePathname();
  const auth = useAuth();
  const { t, theme, toggleTheme, toggleLanguage, language } = usePreferences();
  const [open, setOpen] = useState(false);
  const header = useRef<HTMLElement>(null);
  const mobileBar = useRef<HTMLElement>(null);
  const menuTrigger = useRef<HTMLButtonElement | null>(null);
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !header.current?.contains(event.target) &&
        !mobileBar.current?.contains(event.target)
      )
        setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menuTrigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);
  function toggleMenu(button: HTMLButtonElement) {
    menuTrigger.current = button;
    setOpen((value) => !value);
  }
  const isActive = (href: string) =>
    path === href || (href !== "/" && path.startsWith(href + "/"));
  const links = [
    ["/", "情报中心", "Intelligence"],
    ["/minerals", "矿种", "Minerals"],
    ["/regions", "地区", "Regions"],
    ["/policies", "政策", "Policy"],
    ["/trends", "趋势", "Trends"],
    ["/digest", "简报", "Briefs"],
    ["/research", "研判", "Research"],
    ["/chat", AGENT_NAME, AGENT_NAME],
    ...(auth.user?.is_admin ? [["/admin", "管理", "Admin"]] : []),
  ];
  return (
    <>
      <header className="header" ref={header}>
        <Link
          href="/"
          prefetch={false}
          className="brand"
          aria-label="MiningIntel · THE RESOURCE OBSERVATORY · 首页 / Home"
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
              className={isActive(href) ? "active" : ""}
              aria-current={isActive(href) ? "page" : undefined}
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
            aria-label={
              language === "zh" ? "Switch to English (EN)" : "切换中文（中）"
            }
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
            aria-label={
              open
                ? t("关闭导航", "Close navigation")
                : t("打开导航", "Open navigation")
            }
            aria-expanded={open}
            aria-controls="mobile-primary-menu"
            onClick={(event) => toggleMenu(event.currentTarget)}
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
        <nav
          id="mobile-primary-menu"
          className={`mobile-nav ${open ? "open" : ""}`}
          aria-label={t("移动导航", "Mobile navigation")}
        >
          {links.map(([href, zh, en]) => (
            <Link
              key={href}
              href={href}
              prefetch={false}
              className={isActive(href) ? "active" : ""}
              aria-current={isActive(href) ? "page" : undefined}
              onClick={() => setOpen(false)}
            >
              {t(zh, en)}
            </Link>
          ))}
          <Link href="/search" prefetch={false} onClick={() => setOpen(false)}>
            {t("搜索情报", "Search")}
          </Link>
          <Link
            href="/bookmarks"
            prefetch={false}
            onClick={() => setOpen(false)}
          >
            {t("我的收藏", "Saved articles")}
          </Link>
          <Link href="/subscriptions" onClick={() => setOpen(false)}>
            {t("我的订阅", "Subscriptions")}
          </Link>
          <Link href="/notifications" onClick={() => setOpen(false)}>
            {t("消息中心", "Notifications")}
          </Link>
          {auth.user ? (
            <button
              className="mobile-account-link"
              onClick={() => {
                auth.logout();
                setOpen(false);
              }}
            >
              {t("退出登录", "Sign out")}
            </button>
          ) : (
            <Link href="/login" prefetch={false} onClick={() => setOpen(false)}>
              {t("登录 / 注册", "Sign in / Register")}
            </Link>
          )}
        </nav>
      </header>
      <nav
        className="mobile-primary-nav"
        ref={mobileBar}
        aria-label={t("底部快捷导航", "Quick navigation")}
      >
        {[
          { href: "/", zh: "情报", en: "Home", Icon: House },
          { href: "/policies", zh: "政策", en: "Policy", Icon: FileText },
          { href: "/trends", zh: "趋势", en: "Trends", Icon: TrendingUp },
          { href: "/chat", zh: "智探", en: "Ask", Icon: MessagesSquare },
        ].map(({ href, zh, en, Icon }) => (
          <Link
            key={href}
            href={href}
            prefetch={false}
            className={isActive(href) ? "active" : ""}
            aria-current={isActive(href) ? "page" : undefined}
            onClick={() => setOpen(false)}
          >
            <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
            <span>{t(zh, en)}</span>
          </Link>
        ))}
        <button
          type="button"
          aria-expanded={open}
          aria-controls="mobile-primary-menu"
          className={open ? "active" : ""}
          onClick={(event) => toggleMenu(event.currentTarget)}
        >
          {open ? (
            <X size={20} aria-hidden="true" />
          ) : (
            <Menu size={20} aria-hidden="true" />
          )}
          <span>{t("更多", "More")}</span>
        </button>
      </nav>
    </>
  );
}
