"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type KeyboardEvent,
} from "react";
import {
  ArrowUpRight,
  Bookmark,
  BookOpen,
  ChevronRight,
  Compass,
  FileText,
  FlaskConical,
  Globe2,
  House,
  Layers3,
  LayoutGrid,
  MessagesSquare,
  Mountain,
  Search,
  Settings2,
  SlidersHorizontal,
  TrendingUp,
  Type,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import {
  findDestinations,
  relatedDestinations,
  workspaceLocation,
} from "@/lib/workspace-navigation.mjs";
import { Dialog } from "./ui/dialog";
import { MotionControl } from "./motion-control";

type ToolView = "navigate" | "reading";
const ToolsContext = createContext<{ open: (view?: ToolView) => void } | null>(
  null,
);
const icons = {
  home: House,
  minerals: Mountain,
  regions: Globe2,
  policies: FileText,
  trends: TrendingUp,
  digest: BookOpen,
  frontier: FlaskConical,
  topics: Layers3,
  research: Compass,
  chat: MessagesSquare,
  search: Search,
  bookmarks: Bookmark,
};

export function WorkspaceIcon({
  name,
  size = 18,
}: {
  name: string;
  size?: number;
}) {
  const Icon = icons[name as keyof typeof icons] || Compass;
  return <Icon size={size} strokeWidth={1.65} aria-hidden="true" />;
}

export function useWorkspaceTools() {
  const tools = useContext(ToolsContext);
  if (!tools) throw new Error("WorkspaceToolsProvider missing");
  return tools;
}

/** A keyboard-accessible destination switcher with browser-local reading settings. */
export function WorkspaceToolsProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const auth = useAuth();
  const {
    t,
    theme,
    toggleTheme,
    readingSize,
    density,
    setReadingSize,
    setDensity,
  } = usePreferences();
  const [isOpen, setIsOpen] = useState(false);
  const [view, setView] = useState<ToolView>("navigate");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const destinations = findDestinations(query, !!auth.user?.is_admin);

  const open = useCallback((next: ToolView = "navigate") => {
    previousFocus.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setView(next);
    setQuery("");
    setSelected(-1);
    setIsOpen(true);
  }, []);
  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);
  useEffect(() => {
    function shortcut(event: globalThis.KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (isOpen) setIsOpen(false);
        else open();
      }
    }
    addEventListener("keydown", shortcut);
    return () => removeEventListener("keydown", shortcut);
  }, [isOpen, open]);
  useEffect(() => {
    if (isOpen && view === "navigate") input.current?.focus();
  }, [isOpen, view]);
  useEffect(() => {
    if (isOpen && selected >= 0)
      document
        .getElementById(`workspace-option-${selected}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [selected, isOpen]);
  function go(href: string) {
    setIsOpen(false);
    router.push(href);
  }
  function choose(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!destinations.length) return;
      setSelected((current) =>
        event.key === "ArrowDown"
          ? (current + 1) % destinations.length
          : current <= 0
            ? destinations.length - 1
            : current - 1,
      );
    }
    if (event.key === "Enter") {
      event.preventDefault();
      if (selected >= 0 && destinations[selected])
        go(destinations[selected].href);
      else if (query.trim())
        go(`/search?q=${encodeURIComponent(query.trim())}`);
      else if (destinations[0]) go(destinations[0].href);
    }
  }
  return (
    <ToolsContext.Provider value={{ open }}>
      {children}
      <Dialog
        open={isOpen}
        onOpenChange={setIsOpen}
        className="workspace-command"
        title={t("你的情报工作台", "Your intelligence workspace")}
        description={t(
          "快速找到栏目，或按自己的习惯阅读。",
          "Find a destination or make reading more comfortable.",
        )}
        onOpenAutoFocus={(event) => {
          if (view === "navigate") {
            event.preventDefault();
            input.current?.focus();
          }
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (
            previousFocus.current?.isConnected &&
            previousFocus.current.getClientRects().length
          )
            previousFocus.current.focus({ preventScroll: true });
          else {
            const buttons = document.querySelectorAll<HTMLElement>(
              ".header .workspace-command-trigger, .header .mobile-menu",
            );
            Array.from(buttons)
              .find((button) => button.getClientRects().length)
              ?.focus({ preventScroll: true });
          }
        }}
      >
        <div
          className="command-tabs"
          aria-label={t("工作台工具", "Workspace tools")}
        >
          <button
            type="button"
            aria-pressed={view === "navigate"}
            onClick={() => {
              setView("navigate");
              setSelected(-1);
            }}
          >
            <Compass size={16} />
            {t("快捷导航", "Navigate")}
          </button>
          <button
            type="button"
            aria-pressed={view === "reading"}
            onClick={() => setView("reading")}
          >
            <Type size={16} />
            {t("阅读与外观", "Reading & appearance")}
          </button>
        </div>
        {view === "navigate" ? (
          <>
            <div className="command-search">
              <Search size={19} aria-hidden="true" />
              <input
                ref={input}
                value={query}
                maxLength={200}
                role="combobox"
                aria-expanded={true}
                aria-autocomplete="list"
                aria-controls="workspace-options"
                aria-activedescendant={
                  selected >= 0 ? `workspace-option-${selected}` : undefined
                }
                aria-label={t(
                  "搜索栏目或关键词",
                  "Find a destination or search intelligence",
                )}
                placeholder={t(
                  "想去哪里，或想了解什么？",
                  "Where would you like to go?",
                )}
                onKeyDown={choose}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setSelected(-1);
                }}
              />
              <kbd>↵</kbd>
            </div>
            {query.trim() && (
              <button
                className="command-knowledge"
                onClick={() =>
                  go(`/search?q=${encodeURIComponent(query.trim())}`)
                }
              >
                <Search size={16} />
                <span>
                  {t("在资料库中搜索", "Search the evidence library")}{" "}
                  <strong>“{query.trim()}”</strong>
                </span>
                <ArrowUpRight size={15} />
              </button>
            )}
            <div
              className="command-destinations"
              id="workspace-options"
              role="listbox"
              aria-label={t("栏目列表", "Destinations")}
            >
              {destinations.map((item, index) => (
                <button
                  type="button"
                  role="option"
                  aria-selected={selected === index}
                  id={`workspace-option-${index}`}
                  key={item.key}
                  onClick={() => go(item.href)}
                >
                  <span className="command-icon">
                    <WorkspaceIcon name={item.key} />
                  </span>
                  <span>
                    <strong>{t(item.zh, item.en)}</strong>
                    <small>{t(item.note, item.noteEn)}</small>
                  </span>
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              ))}
              {!destinations.length && (
                <p className="command-no-destination">
                  {t(
                    "没有同名栏目，可使用上方入口搜索资料。",
                    "No matching destination. Search the evidence library above.",
                  )}
                </p>
              )}
            </div>
            <div className="command-foot">
              <span>
                <kbd>↑</kbd>
                <kbd>↓</kbd> {t("选择栏目", "Choose")}
              </span>
              <span>
                <kbd>Esc</kbd> {t("关闭", "Close")}
              </span>
              <span>
                <kbd>Ctrl / ⌘ K</kbd> {t("随时打开", "Open anywhere")}
              </span>
            </div>
          </>
        ) : (
          <div className="reading-settings">
            <div className="reading-preview">
              <span>READING ROOM</span>
              <h3>
                {t(
                  "让重要的信息，读起来更从容。",
                  "Make room for what matters.",
                )}
              </h3>
              <p>
                {t(
                  "先看摘要，理解脉络，再沿着引用回到原文。按你的阅读习惯调整字号和页面密度。",
                  "Read the summary, follow the context, then return to the original source. Choose the text size and spacing that suit you.",
                )}
              </p>
            </div>
            <div className="reading-setting-row">
              <div>
                <Type size={17} />
                <span>
                  <strong>{t("正文字号", "Text size")}</strong>
                  <small>
                    {t(
                      "同时应用于摘要与长文阅读",
                      "For summaries and long-form reading",
                    )}
                  </small>
                </span>
              </div>
              <div
                className="setting-segment"
                role="group"
                aria-label={t("正文字号", "Text size")}
              >
                <button
                  aria-pressed={readingSize === "standard"}
                  onClick={() => setReadingSize("standard")}
                >
                  {t("标准", "Standard")}
                </button>
                <button
                  aria-pressed={readingSize === "large"}
                  onClick={() => setReadingSize("large")}
                >
                  {t("大字", "Large")}
                </button>
              </div>
            </div>
            <div className="reading-setting-row">
              <div>
                <SlidersHorizontal size={17} />
                <span>
                  <strong>{t("页面排版", "Layout spacing")}</strong>
                  <small>
                    {t(
                      "舒展阅读，或更集中地浏览资料",
                      "A spacious read or a compact overview",
                    )}
                  </small>
                </span>
              </div>
              <div
                className="setting-segment"
                role="group"
                aria-label={t("页面排版", "Layout spacing")}
              >
                <button
                  aria-pressed={density === "comfortable"}
                  onClick={() => setDensity("comfortable")}
                >
                  {t("舒展", "Spacious")}
                </button>
                <button
                  aria-pressed={density === "compact"}
                  onClick={() => setDensity("compact")}
                >
                  {t("紧凑", "Compact")}
                </button>
              </div>
            </div>
            <div className="reading-setting-row">
              <div>
                <Settings2 size={17} />
                <span>
                  <strong>{t("页面主题", "Theme")}</strong>
                  <small>
                    {t("夜间深蓝与日间暖白", "Midnight blue or warm daylight")}
                  </small>
                </span>
              </div>
              <div
                className="setting-segment"
                role="group"
                aria-label={t("页面主题", "Theme")}
              >
                <button
                  aria-pressed={theme === "dark"}
                  onClick={() => {
                    if (theme !== "dark") toggleTheme();
                  }}
                >
                  {t("深色", "Dark")}
                </button>
                <button
                  aria-pressed={theme === "light"}
                  onClick={() => {
                    if (theme !== "light") toggleTheme();
                  }}
                >
                  {t("浅色", "Light")}
                </button>
              </div>
            </div>
            <div className="reading-setting-row">
              <div>
                <Compass size={17} />
                <span>
                  <strong>{t("动态效果", "Motion")}</strong>
                  <small>
                    {t(
                      "可随时暂停，专注于内容",
                      "Pause whenever you prefer to focus",
                    )}
                  </small>
                </span>
              </div>
              <MotionControl />
            </div>
            <div className="reading-settings-foot">
              <p>
                {t(
                  "设置会保留在当前浏览器，下次打开时继续使用。",
                  "Your settings are remembered in this browser.",
                )}
              </p>
              <button
                onClick={() => {
                  setReadingSize("standard");
                  setDensity("comfortable");
                }}
              >
                {t("恢复默认排版", "Reset layout")}
              </button>
            </div>
          </div>
        )}
      </Dialog>
    </ToolsContext.Provider>
  );
}

/** Breadcrumbs and useful next destinations, without additional API requests. */
export function WorkspaceRibbon() {
  const path = usePathname();
  const { t } = usePreferences();
  const tools = useWorkspaceTools();
  const item = workspaceLocation(path);
  if (path === "/") return null;
  const related = relatedDestinations(item.key);
  return (
    <div className="workspace-ribbon">
      <nav
        className="workspace-breadcrumbs"
        aria-label={t("当前位置", "Breadcrumb")}
      >
        <Link
          href="/"
          prefetch={false}
          aria-label={t("情报中心", "Intelligence home")}
        >
          <House size={15} />
          <span className="ribbon-home-label">{t("情报中心", "Home")}</span>
        </Link>
        <ChevronRight size={13} aria-hidden="true" />
        {item.detailZh ? (
          <>
            {item.href !== "/" && (
              <>
                <Link href={item.href} prefetch={false}>
                  {t(item.zh, item.en)}
                </Link>
                <ChevronRight size={13} aria-hidden="true" />
              </>
            )}
            <span aria-current="page">{t(item.detailZh, item.detailEn)}</span>
          </>
        ) : (
          <span aria-current="page">{t(item.zh, item.en)}</span>
        )}
      </nav>
      <div
        className="ribbon-related"
        aria-label={t("相关栏目", "Related destinations")}
      >
        {related.slice(0, 2).map(
          (destination) =>
            destination && (
              <Link
                href={destination.href}
                prefetch={false}
                key={destination.key}
              >
                {t(destination.zh, destination.en)}
                <ArrowUpRight size={12} />
              </Link>
            ),
        )}
      </div>
      <div className="ribbon-tools">
        <button
          onClick={() => tools.open("reading")}
          aria-label={t("阅读与外观设置", "Reading and appearance settings")}
        >
          <Type size={16} />
          <span>{t("阅读设置", "Reading")}</span>
        </button>
        <button
          onClick={() => tools.open()}
          aria-label={t("打开快捷导航", "Open quick navigation")}
        >
          <LayoutGrid size={16} />
          <span>{t("快捷导航", "Navigate")}</span>
          <kbd>⌘ K</kbd>
        </button>
      </div>
    </div>
  );
}
