"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Flame,
  Sparkles,
  TrendingUp,
  Radio,
  FileText,
} from "lucide-react";
import { ArticleFeed } from "./article-feed";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import { formatDate } from "@/lib/format-date";
import type {
  Article,
  ArticlePage,
  Facets,
  Insights,
  Policy,
  Price,
  Source,
} from "@/types";
import { SubscriptionDialog } from "./subscription-dialog";
import { ErrorState, SkeletonCards } from "./ui/states";
export interface HomeData {
  articles?: ArticlePage;
  hot?: Article[];
  facets?: Facets;
  sources?: Source[];
  minerals?: Insights["hotspots"];
  alerts?: Price[];
  policies?: Policy[];
}
export function HomeDashboard({ initial }: { initial: HomeData }) {
  const { t, language } = usePreferences();
  const hot = useQuery({
    queryKey: ["hot-articles"],
    queryFn: () => publicApi<Article[]>("/articles/hot"),
    initialData: initial.hot,
    staleTime: 300000,
  });
  const minerals = useQuery({
    queryKey: ["hot-minerals"],
    queryFn: () => publicApi<Insights["hotspots"]>("/trends/hot-minerals"),
    initialData: initial.minerals,
    staleTime: 300000,
  });
  const policies = useQuery({
    queryKey: ["policy-updates"],
    queryFn: () => publicApi<Policy[]>("/trends/policy-updates"),
    initialData: initial.policies,
    staleTime: 300000,
  });
  const alerts = useQuery({
    queryKey: ["price-alerts"],
    queryFn: () => publicApi<Price[]>("/trends/price-alerts"),
    initialData: initial.alerts,
    staleTime: 300000,
  });
  const hotItems = hot.data || [];
  return (
    <div className="home-content">
      <div className="section-line">
        <h2>
          <Flame size={15} className="text-primary" />
          {t("值得关注", "On the radar")}
          <span className="kicker">48H HOTSPOTS</span>
        </h2>
        <Link href="/trends" className="text-link" prefetch={false}>
          {t("全部趋势", "Explore trends")}
          <ArrowUpRight size={13} />
        </Link>
      </div>
      <div className="hot-grid">
        {hotItems.slice(0, 3).map((article, index) => (
          <article className="hot-card" key={article.id}>
            <div className="hot-rank">
              {String(index + 1).padStart(2, "0")} / {t("热点追踪", "IN FOCUS")}
            </div>
            <h3>
              <Link href={`/articles/${article.id}`} prefetch={false}>
                {language === "zh"
                  ? article.title_zh || article.title
                  : article.title}
              </Link>
            </h3>
            <p>
              {language === "zh"
                ? article.summary_zh || article.summary
                : article.summary || article.summary_zh}
            </p>
            <div className="hot-meta">
              <Radio size={11} />
              {article.source_name}
              <span className="ml-auto">
                {formatDate(article.published_at)}
              </span>
            </div>
          </article>
        ))}
      </div>
      {hot.isPending && <SkeletonCards count={1} />}
      {hot.isError && (
        <ErrorState error={hot.error} retry={() => hot.refetch()} />
      )}
      {!hot.isPending && !hot.isError && !hotItems.length && (
        <div className="empty">
          {t(
            "近 48 小时暂无已发布热点，请查看下方完整资讯流。",
            "No published hotspots in the last 48 hours. Browse the full feed below.",
          )}
        </div>
      )}
      <div className="dashboard">
        <ArticleFeed
          initial={initial.articles}
          initialFacets={initial.facets}
        />
        <aside className="sticky-aside">
          <section className="panel">
            <h2 className="panel-title">
              {t("矿种热度", "Commodities in focus")}
              <small>PAST 7 DAYS</small>
            </h2>
            {minerals.data?.slice(0, 6).map((item, index) => (
              <Link
                className="insight-row"
                key={item.mineral}
                href={`/minerals/${encodeURIComponent(item.mineral)}`}
              >
                <span className="rank">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="flex-1">{item.mineral}</span>
                <span className="text-muted">
                  {item.count} {t("篇", "stories")}
                </span>
                <span
                  className={
                    item.is_new || (item.growth_pct || 0) > 0 ? "up" : "down"
                  }
                >
                  {item.is_new
                    ? t("新出现", "NEW")
                    : `${item.growth_pct ?? 0}%`}
                </span>
              </Link>
            ))}
            {!minerals.data?.length && (
              <p className="subtitle">
                {t("暂无近期热点", "No recent signals")}
              </p>
            )}
            <p className="text-[9px] text-muted mt-4">
              {t(
                "按近 7 天报道数与前 7 天比较。",
                "Coverage this week, compared with the previous week.",
              )}
            </p>
          </section>
          <section className="panel">
            <h2 className="panel-title">
              {t("政策雷达", "Policy radar")}
              <FileText size={13} className="text-muted" />
            </h2>
            {policies.data?.slice(0, 3).map((item) => (
              <a
                className="insight-row"
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.title_zh || item.title}
                <ArrowUpRight size={13} />
              </a>
            ))}
            {!policies.data?.length && (
              <p className="subtitle text-xs">
                {t(
                "近一周暂无已发布的政策更新。",
                "No published policy updates in the last week.",
                )}
              </p>
            )}
            <Link className="source-link mt-3" href="/policies">
              {t("查看政策库", "Browse policy library")} →
            </Link>
          </section>
          <section className="panel">
            <h2 className="panel-title">
              {t("价格异动", "Price alerts")}
              <TrendingUp size={14} className="text-muted" />
            </h2>
            {alerts.data?.slice(0, 3).map((item) => (
              <a
                className="insight-row"
                key={item.id}
                href={item.source_url || item.source}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span>
                  {item.product || item.mineral}
                  <small className="block text-muted">
                    {item.date} · {item.currency}/{item.unit}
                  </small>
                </span>
                <span className={Number(item.change_pct) > 0 ? "up" : "down"}>
                  {Number(item.change_pct).toFixed(2)}%
                </span>
              </a>
            ))}
            {!alerts.data?.length && (
              <p className="subtitle text-xs">
                {t(
                  "近 7 天暂无达到预警阈值的单日价格异动。",
                  "No daily price changes meeting the warning threshold in the past week.",
                )}
              </p>
            )}
            <Link className="source-link mt-3" href="/minerals/%E9%94%82">
              {t("查看真实锂价走势", "View lithium spot prices")} →
            </Link>
          </section>
          <section className="consult-panel">
            <Sparkles size={20} className="text-primary" />
            <h3>{t("把问题交给情报。", "Ask a better question.")}</h3>
            <p>
              {t(
                "价格为什么变动？政策如何影响供给？从原始资料出发，找到有据可查的回答。",
                "Explore markets and policy with answers grounded in original sources.",
              )}
            </p>
            <Link href="/chat" className="source-link">
              {t("开始 AI 咨询", "Ask MiningIntel")}
              <ArrowUpRight size={14} />
            </Link>
          </section>
          <div className="panel">
            <h2 className="panel-title">
              {t("只关注你关心的变化", "Your focus. Your feed.")}
            </h2>
            <p className="subtitle text-xs">
              {t(
                "订阅矿种和地区，持续追踪重要动向。",
                "Follow commodities and regions to stay informed.",
              )}
            </p>
            <SubscriptionDialog />
          </div>
        </aside>
      </div>
    </div>
  );
}
