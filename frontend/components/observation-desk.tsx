"use client";

import Link from "next/link";
import { useId, useRef, useState, type KeyboardEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  FlaskConical,
  Layers3,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Star,
  Pause,
  Play,
} from "lucide-react";
import { publicApi } from "@/lib/api";
import { formatDate } from "@/lib/format-date";
import { latestQuotation, observationItems } from "@/lib/observation.mjs";
import { useMineralWatchlist } from "@/hooks/use-mineral-watchlist";
import { usePreferences } from "@/hooks/use-preferences";
import { useAmbientCycle } from "@/hooks/use-ambient-cycle";
import type {
  Article,
  ArticlePage,
  MineralMarket,
  MineralMarketItem,
  Policy,
} from "@/types";
import { Dialog } from "./ui/dialog";
import { MineralWatchButton } from "./mineral-watch-button";
import { ErrorState, SkeletonCards } from "./ui/states";

type DeskTab = "industry" | "policy" | "research";
interface Story {
  id: string;
  title: string;
  summary: string | null;
  source: string | null;
  date: string | null;
  minerals: string[];
  href: string;
  original: string;
}

function articleStory(article: Article, language: string): Story {
  return {
    id: article.id,
    title:
      language === "zh" ? article.title_zh || article.title : article.title,
    summary:
      language === "zh"
        ? article.summary_zh || article.summary
        : article.summary || article.summary_zh,
    source: article.source_name || null,
    date: article.published_at,
    minerals: article.minerals,
    href: `/articles/${article.id}`,
    original: article.url,
  };
}

/** Show actual quotes, including their individual units and observation dates. */
function WatchQuote({ item }: { item: MineralMarketItem }) {
  const { t, language } = usePreferences();
  const quote = latestQuotation(item.prices);
  const change = quote?.change_pct == null ? null : Number(quote.change_pct);
  return (
    <article className="desk-quote">
      <div className="desk-quote-top">
        <Link
          href={`/minerals/${encodeURIComponent(item.name)}`}
          prefetch={false}
        >
          <span className="desk-element">{item.symbol}</span>
          <span>{language === "zh" ? item.name : item.english_name}</span>
        </Link>
        <MineralWatchButton name={item.name} />
      </div>
      {quote ? (
        <>
          <div className="desk-quote-value">
            <strong>
              {Number(quote.price).toLocaleString("en-US", {
                maximumFractionDigits: 2,
              })}
            </strong>
            <small>
              {quote.currency}/{quote.unit}
            </small>
          </div>
          <div className="desk-quote-bottom">
            <span
              className={
                change !== null && change > 0
                  ? "up"
                  : change !== null && change < 0
                    ? "down"
                    : "text-muted"
              }
            >
              {change !== null && Number.isFinite(change)
                ? `${change > 0 ? "+" : ""}${change.toFixed(2)}%`
                : t("暂无对比", "No comparison")}
            </span>
            <time dateTime={quote.date}>{quote.date}</time>
          </div>
          <p className="desk-product">
            {quote.product || item.name} ·{" "}
            {quote.price_type === "futures"
              ? t("期货", "Futures")
              : quote.price_type === "benchmark"
                ? t("参考价", "Benchmark")
                : t("现货", "Spot")}
          </p>
          {item.price_status === "stale" && (
            <p className="desk-stale">
              {t(
                "报价超过 7 天，请核对原始来源",
                "Quote older than 7 days; check source",
              )}
            </p>
          )}
          <a
            className="desk-quote-source"
            href={quote.source_url || quote.source}
            target="_blank"
            rel="noopener noreferrer"
          >
            {quote.source_name || t("查看报价来源", "Quotation source")}{" "}
            <ArrowUpRight size={11} />
          </a>
        </>
      ) : (
        <div className="desk-no-quote">
          <strong>
            {item.article_count} <small>{t("篇情报", "stories")}</small>
          </strong>
          <span>{t("暂无可靠公开报价", "No verified public quote")}</span>
        </div>
      )}
    </article>
  );
}

/** An evidence-led home desk with reader-controlled stories and local observations. */
export function ObservationDesk({
  initialArticles,
  initialPapers,
  initialMarket,
  policies,
  policyPending = false,
  policyError,
  retryPolicy,
}: {
  initialArticles?: ArticlePage;
  initialPapers?: ArticlePage;
  initialMarket?: MineralMarket;
  policies?: Policy[];
  policyPending?: boolean;
  policyError?: Error | null;
  retryPolicy?: () => void;
}) {
  const { t, language } = usePreferences();
  const { names } = useMineralWatchlist();
  const [tab, setTab] = useState<DeskTab>("industry");
  const [selected, setSelected] = useState<string | null>(null);
  const [editor, setEditor] = useState(false);
  const [expandedWatch, setExpandedWatch] = useState(false);
  const [automatic, setAutomatic] = useState(true);
  const editorial = useRef<HTMLDivElement>(null);
  const [search, setSearch] = useState("");
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const editorTrigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const articles = useQuery({
    queryKey: ["desk-articles"],
    queryFn: () =>
      publicApi<ArticlePage>("/articles?page_size=6&exclude_prices=true"),
    initialData: initialArticles,
    staleTime: 300000,
  });
  const papers = useQuery({
    queryKey: ["desk-papers"],
    queryFn: () =>
      publicApi<ArticlePage>(
        "/articles?page_size=4&category=report&exclude_prices=true",
      ),
    initialData: initialPapers,
    staleTime: 300000,
  });
  const market = useQuery({
    queryKey: ["mineral-market"],
    queryFn: () => publicApi<MineralMarket>("/minerals/market"),
    initialData: initialMarket,
    staleTime: 300000,
  });
  const definitions = [
    {
      key: "industry" as const,
      zh: "产业焦点",
      en: "Industry",
      icon: Layers3,
      href: "#intelligence-feed",
    },
    {
      key: "policy" as const,
      zh: "政策动向",
      en: "Policy",
      icon: FileText,
      href: "/policies",
    },
    {
      key: "research" as const,
      zh: "研究线索",
      en: "Research",
      icon: FlaskConical,
      href: "/frontier",
    },
  ];
  const stories: Story[] =
    tab === "policy"
      ? (policies || []).map((policy) => ({
          id: policy.id,
          title:
            language === "zh" ? policy.title_zh || policy.title : policy.title,
          summary: policy.summary_zh,
          source: policy.source_name || null,
          date: policy.published_at || null,
          minerals: policy.minerals,
          href: policy.url,
          original: policy.url,
        }))
      : (tab === "research" ? papers.data?.items : articles.data?.items)?.map(
          (article) => articleStory(article, language),
        ) || [];
  const unique = [
    ...new Map(stories.map((story) => [story.id, story])).values(),
  ].slice(0, 6);
  const story = unique.find((item) => item.id === selected) || unique[0];
  function stepStory(direction: number) {
    if (unique.length < 2) return;
    const index = unique.findIndex((item) => item.id === story?.id);
    setSelected(unique[(index + direction + unique.length) % unique.length].id);
  }
  const { running, interactionProps } = useAmbientCycle(
    editorial,
    () => stepStory(1),
    automatic && unique.length > 1,
  );
  const current = definitions.find((definition) => definition.key === tab)!;
  const busy =
    tab === "research"
      ? papers.isPending
      : tab === "industry"
        ? articles.isPending
        : policyPending;
  const failed =
    tab === "research"
      ? papers.isError
      : tab === "industry"
        ? articles.isError
        : Boolean(policyError);
  const items = observationItems(
    market.data?.items,
    names,
  ) as MineralMarketItem[];
  const catalog = (market.data?.items || []).filter((item) =>
    `${item.name} ${item.english_name} ${item.symbol}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  function changeTab(next: DeskTab) {
    setTab(next);
    setSelected(null);
    setAutomatic(false);
  }
  function navigateTab(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next: number;
    if (event.key === "ArrowRight") next = (index + 1) % definitions.length;
    else if (event.key === "ArrowLeft")
      next = (index + definitions.length - 1) % definitions.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = definitions.length - 1;
    else return;
    event.preventDefault();
    changeTab(definitions[next].key);
    tabs.current[next]?.focus();
  }
  return (
    <section
      className="observation-desk"
      id="signal-desk"
      aria-label={t("资源情报工作台", "Resource intelligence desk")}
    >
      <div className="desk-heading">
        <div>
          <p className="desk-kicker">
            <span /> INTELLIGENCE, IN PERSPECTIVE
          </p>
          <h2>
            {t("你的视角，全球资源。", "Your perspective. Global resources.")}
          </h2>
          <p>
            {t(
              "从一条线索出发，把资讯变成下一步研究。",
              "Start with a signal. Find your next line of inquiry.",
            )}
          </p>
        </div>
        <a className="desk-view-all" href="#intelligence-feed">
          {t("进入完整情报流", "Open the full stream")}{" "}
          <ArrowDownRight size={18} />
        </a>
      </div>
      <div className="desk-surface" data-cycling={running}>
        <div className="desk-tab-bar">
          <div
            role="tablist"
            aria-label={t("观察视角", "Intelligence perspectives")}
          >
            {definitions.map((definition, index) => (
              <button
                key={definition.key}
                type="button"
                role="tab"
                id={`${id}-${definition.key}`}
                aria-controls={`${id}-panel`}
                aria-selected={tab === definition.key}
                tabIndex={tab === definition.key ? 0 : -1}
                ref={(element) => {
                  tabs.current[index] = element;
                }}
                onKeyDown={(event) => navigateTab(event, index)}
                onClick={() => changeTab(definition.key)}
              >
                <definition.icon size={15} /> {t(definition.zh, definition.en)}
              </button>
            ))}
          </div>
          <span className="desk-verification">
            <ShieldCheck size={13} />{" "}
            {t("真实资料 · 来源可追溯", "Original, traceable sources")}
          </span>
          <div
            className="desk-playback"
            aria-label={t("焦点资讯播放控制", "Focus story playback")}
          >
            <button
              disabled={unique.length < 2}
              aria-label={t("上一条焦点", "Previous focus story")}
              onClick={() => {
                setAutomatic(false);
                stepStory(-1);
              }}
            >
              <ChevronLeft size={14} />
            </button>
            <button
              aria-pressed={automatic}
              disabled={unique.length < 2}
              onClick={() => setAutomatic(!automatic)}
              aria-label={
                automatic
                  ? t("暂停焦点轮播", "Pause focus slideshow")
                  : t("播放焦点轮播", "Play focus slideshow")
              }
            >
              {automatic ? <Pause size={13} /> : <Play size={13} />}
              <span>{t("巡播", "Slideshow")}</span>
            </button>
            <button
              disabled={unique.length < 2}
              aria-label={t("下一条焦点", "Next focus story")}
              onClick={() => {
                setAutomatic(false);
                stepStory(1);
              }}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
        <div className="desk-cycle-track" aria-hidden="true">
          <span key={story?.id} />
        </div>
        <div className="desk-grid">
          <div
            className="desk-editorial"
            role="tabpanel"
            id={`${id}-panel`}
            aria-labelledby={`${id}-${tab}`}
            ref={editorial}
            {...interactionProps}
          >
            {story ? (
              <>
                <div
                  className="desk-story-list"
                  aria-label={t("选择焦点资料", "Choose a source story")}
                >
                  {unique.map((item, index) => (
                    <button
                      key={item.id}
                      type="button"
                      className={item.id === story.id ? "is-selected" : ""}
                      aria-pressed={item.id === story.id}
                      onClick={() => {
                        setSelected(item.id);
                        setAutomatic(false);
                      }}
                    >
                      <span className="desk-story-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span>
                        <strong>{item.title}</strong>
                        <small>
                          {item.source ||
                            t("来源未标注", "Source not specified")}
                        </small>
                      </span>
                      <ArrowUpRight size={13} />
                    </button>
                  ))}
                </div>
                <article className="desk-lead" key={`${tab}-${story.id}`}>
                  <div className="desk-lead-top">
                    <span>{t(current.zh, current.en)}</span>
                    <span>
                      {unique.findIndex((item) => item.id === story.id) + 1} /{" "}
                      {unique.length}
                    </span>
                  </div>
                  <div className="desk-lead-copy">
                    <h3>
                      {tab === "policy" ? (
                        <a
                          href={story.href}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {story.title}
                        </a>
                      ) : (
                        <Link href={story.href} prefetch={false}>
                          {story.title}
                        </Link>
                      )}
                    </h3>
                    <p>
                      {story.summary ||
                        t(
                          "此资料尚无摘要，请查看原始来源。",
                          "No abstract is available. Read the original source.",
                        )}
                    </p>
                    <div className="desk-tags">
                      {story.minerals.slice(0, 4).map((name) => (
                        <Link
                          href={`/minerals/${encodeURIComponent(name)}`}
                          key={name}
                          prefetch={false}
                        >
                          {name}
                        </Link>
                      ))}
                    </div>
                  </div>
                  <div className="desk-research-prompts">
                    <span>
                      {t("从这条线索继续研究", "Take this signal further")}
                    </span>
                    <div>
                      {[
                        [
                          "梳理核心事实",
                          "Key facts",
                          "梳理核心事实与数据，并标注需要核实的内容",
                          "Summarize the key facts and data, noting what needs verification",
                        ],
                        [
                          "分析潜在影响",
                          "Possible impacts",
                          "分析对矿产供应链、相关企业和政策的潜在影响，区分事实与推测",
                          "Analyze possible supply-chain, company and policy impacts, separating facts from inference",
                        ],
                        [
                          "寻找研究切入点",
                          "Research angles",
                          "提出有据可查的研究切入点，说明证据不足之处",
                          "Suggest evidence-based research angles and identify evidence gaps",
                        ],
                      ].map(([zh, en, promptZh, promptEn]) => (
                        <Link
                          key={en}
                          prefetch={false}
                          href={`/chat?q=${encodeURIComponent(t(`针对《${story.title}》，请${promptZh}。`, `For “${story.title}”, ${promptEn}.`))}`}
                        >
                          {t(zh, en)} <ArrowUpRight size={11} />
                        </Link>
                      ))}
                    </div>
                  </div>
                  <div className="desk-lead-source">
                    <span>
                      {story.source || t("来源未标注", "Source not specified")}
                    </span>
                    <time dateTime={story.date || undefined}>
                      {formatDate(story.date)}
                    </time>
                  </div>
                  <div className="desk-lead-actions">
                    <a
                      href={story.original}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {t("查看原始来源", "Read original source")}{" "}
                      <ArrowUpRight size={14} />
                    </a>
                    <Link
                      href={`/chat?q=${encodeURIComponent(t(`请分析《${story.title}》中的核心事实、可能影响和需要继续核实的事项。`, `Analyze the core facts, possible impacts and open questions in “${story.title}”.`))}`}
                      prefetch={false}
                    >
                      <Sparkles size={14} />
                      {t("交给智探分析", "Explore with AI")}
                    </Link>
                  </div>
                </article>
              </>
            ) : (
              <div className="desk-story-empty">
                {busy ? (
                  <SkeletonCards count={1} />
                ) : failed ? (
                  <ErrorState
                    error={
                      (tab === "research"
                        ? papers.error
                        : tab === "policy"
                          ? policyError
                          : articles.error) ||
                      new Error(
                        t(
                          "资料暂时不可用",
                          "Source material is temporarily unavailable",
                        ),
                      )
                    }
                    retry={() => {
                      if (tab === "research") papers.refetch();
                      else if (tab === "policy") retryPolicy?.();
                      else articles.refetch();
                    }}
                  />
                ) : (
                  <>
                    <current.icon size={30} />
                    <h3>
                      {t("这个视角暂无线索", "No sources for this perspective")}
                    </h3>
                    <p>
                      {tab === "policy"
                        ? t(
                            "近一周暂无已收录政策动向，可进入政策库查看历史资料。",
                            "No policy updates were recorded this week. Browse the policy library for earlier documents.",
                          )
                        : t(
                            "资料收录后会显示在这里。",
                            "Published material will appear here when available.",
                          )}
                    </p>
                  </>
                )}
                <Link href={current.href} prefetch={false}>
                  {t("浏览完整资料", "Browse the full collection")}{" "}
                  <ArrowUpRight size={14} />
                </Link>
              </div>
            )}
          </div>
          <aside
            className="desk-watch"
            id="mineral-watchlist"
            aria-label={t("我的矿种观察", "My mineral watchlist")}
          >
            <div className="desk-watch-heading">
              <div>
                <span className="desk-kicker">YOUR RESOURCE RADAR</span>
                <h3>
                  <Star size={16} />{" "}
                  {names.length
                    ? t("我的观察", "My watchlist")
                    : t("建立你的观察", "Make it yours")}
                </h3>
              </div>
              <button
                className="desk-watch-edit"
                ref={editorTrigger}
                onClick={() => {
                  setSearch("");
                  setEditor(true);
                }}
                aria-label={t("管理矿种观察清单", "Manage mineral watchlist")}
              >
                <Settings2 size={16} />
              </button>
            </div>
            <p className="desk-watch-note">
              {names.length
                ? t(
                    `${names.length} 个关注矿种 · 保存在此浏览器`,
                    `${names.length} minerals · saved in this browser`,
                  )
                : t(
                    "点击星标关注矿种，下次打开继续追踪。",
                    "Star a mineral to keep it on your radar next time.",
                  )}
            </p>
            {market.isPending ? (
              <SkeletonCards count={1} />
            ) : market.isError && !items.length ? (
              <ErrorState error={market.error} retry={() => market.refetch()} />
            ) : !items.length ? (
              <p className="desk-watch-note">
                {t(
                  "行情数据暂未收录，稍后重试。",
                  "No market observations are available yet.",
                )}
              </p>
            ) : (
              <div className="desk-watch-grid">
                {(expandedWatch ? items : items.slice(0, 4)).map((item) => (
                  <WatchQuote key={item.name} item={item} />
                ))}
              </div>
            )}
            {names.length > 4 && (
              <button
                className="desk-watch-more"
                aria-expanded={expandedWatch}
                onClick={() => setExpandedWatch((value) => !value)}
              >
                {t(
                  expandedWatch
                    ? "收起额外观察"
                    : `展开全部 ${names.length} 个关注矿种`,
                  expandedWatch
                    ? "Show fewer observations"
                    : `Show all ${names.length} watched minerals`,
                )}{" "}
                <ArrowUpRight size={12} />
              </button>
            )}
            <Link
              href="/minerals"
              className="desk-watch-footer"
              prefetch={false}
            >
              {t("完整矿种行情", "All mineral markets")}{" "}
              <ArrowUpRight size={13} />
            </Link>
            <small className="desk-price-note">
              {t(
                "公开每日报价，以各来源日期为准；涨跌幅比较同序列前一报价。",
                "Public daily quotes by source date; changes compare the previous quote in the same series.",
              )}
            </small>
          </aside>
        </div>
        <div className="desk-bottom">
          <span>
            <span className="desk-status-dot" />
            {t("看清事实，再形成判断", "Evidence first. Perspective next.")}
          </span>
          <Link href="/research" prefetch={false}>
            {t("进入深度研判", "Open research workspace")}{" "}
            <ArrowUpRight size={13} />
          </Link>
        </div>
      </div>
      <Dialog
        open={editor}
        onOpenChange={setEditor}
        title={t("定制你的矿种观察", "Build your mineral watchlist")}
        description={t(
          "最多关注 12 个矿种，保存在当前浏览器；不会开启邮件订阅。",
          "Follow up to 12 minerals in this browser. This does not create an email subscription.",
        )}
        className="watchlist-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          editorTrigger.current?.focus();
        }}
      >
        <div className="watchlist-editor-bar">
          <label>
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("搜索矿种或元素符号", "Search mineral or symbol")}
              aria-label={t("搜索观察矿种", "Search watchlist minerals")}
              maxLength={80}
            />
          </label>
          <span>{names.length} / 12</span>
        </div>
        {names.length > 0 && (
          <div className="watchlist-selection">
            {names.map((name) => (
              <span key={name}>
                {name}
                <MineralWatchButton name={name} />
              </span>
            ))}
          </div>
        )}
        <div className="watchlist-catalog">
          {catalog.map((item) => (
            <div
              key={item.name}
              className={names.includes(item.name) ? "selected" : ""}
            >
              <span className="desk-element">{item.symbol}</span>
              <span>
                <strong>{item.name}</strong>
                <small>{item.english_name}</small>
              </span>
              <MineralWatchButton name={item.name} />
            </div>
          ))}
        </div>
        {!catalog.length && (
          <p className="desk-watch-note">
            {t(
              "没有匹配的矿种，请调整关键词。",
              "No matching minerals. Try a different search.",
            )}
          </p>
        )}
        <button className="watchlist-done" onClick={() => setEditor(false)}>
          <Check size={16} /> {t("完成观察设置", "Done")}
        </button>
      </Dialog>
    </section>
  );
}
