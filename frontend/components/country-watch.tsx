"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Globe2,
  Search,
  RefreshCw,
  Radio,
  Clock3,
} from "lucide-react";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "./section-heading";
import { WorldCoverage } from "./world-coverage";
import { SkeletonCards, ErrorState } from "./ui/states";
import type { CountryMonitor, CountryItem } from "@/types";

function CountryCard({
  item,
  days,
  labels,
}: {
  item: CountryItem;
  days: number;
  labels: Record<string, string>;
}) {
  const { t, language } = usePreferences();
  const recent = item.coverage_status === "recent";
  return (
    <article className={`country-card ${recent ? "country-active" : ""}`}>
      <div className="country-card-top">
        <span className="country-code">{item.iso2}</span>
        <span className={`country-state ${recent ? "is-recent" : ""}`}>
          {recent
            ? t("近期有动向", "Recent coverage")
            : item.article_count
              ? t("历史资料", "Historical")
              : t("资料待补充", "No coverage yet")}
        </span>
      </div>
      <Link
        href={`/regions/${encodeURIComponent(item.name)}`}
        prefetch={false}
        className="country-title"
      >
        <h2>{language === "zh" ? item.name : item.english_name}</h2>
        <ArrowUpRight size={17} />
      </Link>
      <p className="text-xs text-muted">
        {item.continent} · {item.subregion}
        {item.kind === "organization" ? " · 区域组织" : ""}
      </p>
      <div className="country-numbers">
        <div>
          <strong>{item.recent_count}</strong>
          <span>{t(`近 ${days} 天动向`, `Past ${days} days`)}</span>
        </div>
        <div>
          <strong>{item.article_count}</strong>
          <span>{t("累计资料", "Articles")}</span>
        </div>
        <div>
          <strong>{item.source_count}</strong>
          <span>{t("报道信源", "Publishers")}</span>
        </div>
      </div>
      <div className="country-topic-list">
        {Object.entries(item.topics)
          .filter(([, count]) => count > 0)
          .slice(0, 3)
          .map(([key, count]) => (
            <Link
              key={key}
              href={`/regions/${encodeURIComponent(item.name)}?topic=${key}`}
              prefetch={false}
            >
              {labels[key]} <b>{count}</b>
            </Link>
          ))}
      </div>
      {item.latest_article ? (
        <Link
          className="country-latest"
          href={`/articles/${item.latest_article.id}`}
          prefetch={false}
        >
          <span>
            {item.latest_article.title_zh || item.latest_article.title}
          </span>
          <small>
            {item.latest_article.source_name} ·{" "}
            {item.last_published_at?.slice(0, 10) || "日期未知"}
          </small>
        </Link>
      ) : (
        <p className="country-empty">
          {t(
            "尚无可追溯的矿产报道，持续补充公开信源。",
            "Public mining coverage is being expanded.",
          )}
        </p>
      )}
    </article>
  );
}

export function CountryWatch({ initial }: { initial?: CountryMonitor }) {
  const { t } = usePreferences();
  const params = useSearchParams();
  const search = params.get("q") || "";
  const continent = params.get("continent") || "";
  const topic = params.get("topic") || "";
  const mineral = params.get("mineral") || "";
  const [debouncedMineral, setDebouncedMineral] = useState(mineral);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedMineral(mineral), 300);
    return () => clearTimeout(timer);
  }, [mineral]);
  const days = params.get("days") === "30" ? 30 : 7;
  const onlyCovered = params.get("covered") === "1";
  const [limit, setLimit] = useState(36);
  const request = new URLSearchParams({ days: String(days) });
  if (
    ["policy", "trade", "projects", "supply_chain", "investment"].includes(
      topic,
    )
  )
    request.set("topic", topic);
  if (debouncedMineral) request.set("mineral", debouncedMineral);
  const query = useQuery({
    queryKey: ["country-watch", request.toString()],
    queryFn: () => publicApi<CountryMonitor>(`/regions/monitor?${request}`),
    initialData: days === 7 && !topic && !mineral ? initial : undefined,
    staleTime: 300000,
    refetchInterval: 300000,
    placeholderData: (previous) => previous,
  });
  function update(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    value ? next.set(key, value) : next.delete(key);
    window.history.replaceState(
      null,
      "",
      `/regions${next.size ? "?" + next : ""}`,
    );
    setLimit(36);
  }
  const visible = useMemo(
    () =>
      (query.data?.items || []).filter(
        (item) =>
          (!continent || item.continent === continent) &&
          (!onlyCovered || item.article_count > 0) &&
          (!search ||
            `${item.name} ${item.english_name} ${item.iso2} ${item.iso3}`
              .toLowerCase()
              .includes(search.toLowerCase())),
      ),
    [query.data, continent, onlyCovered, search],
  );
  const mapRegions = useMemo(
    () =>
      (query.data?.items || [])
        .filter((i) => i.article_count > 0)
        .map((i) => ({ name: i.name, count: i.article_count })),
    [query.data],
  );
  return (
    <main className="workspace country-workspace">
      <SectionHeading
        eyebrow="GLOBAL MINERAL INTELLIGENCE / COUNTRY WATCH"
        zh="全球国家动向"
        en="Global country watch"
        description="从一条矿产资讯，看到一个国家的资源布局。连接政策、贸易、矿山项目与供应链。"
        descriptionEn="Follow mineral policy, trade, projects and supply chains across countries."
        actions={
          <button
            className="btn btn-outline"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCw
              size={14}
              className={query.isFetching ? "animate-spin" : ""}
            />
            {t("刷新动向", "Refresh")}
          </button>
        }
      />
      {query.isPending ? (
        <SkeletonCards />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : (
        <>
          <section className="country-observatory">
            <div className="country-observatory-summary">
              <div className="country-kicker">
                <Radio size={15} />{" "}
                {t("全球资源观察窗口", "GLOBAL RESOURCE OBSERVATORY")}
              </div>
              <h2>
                {t("资源动向，全球视野。", "Resources in a global context.")}
              </h2>
              <div className="country-stats">
                <div>
                  <strong>{query.data.total}</strong>
                  <span>{t("国家 / 地区与组织目录", "Directory entries")}</span>
                </div>
                <div>
                  <strong>{query.data.covered}</strong>
                  <span>{t("已有报道覆盖", "With sourced coverage")}</span>
                </div>
                <div>
                  <strong>{query.data.recent}</strong>
                  <span>
                    {t(`近 ${days} 天有动向`, `Active in ${days} days`)}
                  </span>
                </div>
              </div>
              <p className="text-sm text-muted leading-relaxed">
                {t(
                  "目录覆盖与实际采集分开展示；动向依据原始报道，不等同于国家风险排名。",
                  "Directory coverage is separate from collected evidence; activity is not a national risk score.",
                )}
              </p>
              <div className="country-check-time">
                <Clock3 size={13} />
                {t("最近成功采集", "Last successful collection")}：
                {query.data.last_successful_fetch_at
                  ? new Date(
                      query.data.last_successful_fetch_at,
                    ).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })
                  : "尚无记录"}
              </div>
            </div>
            <WorldCoverage regions={mapRegions} />
          </section>
          <section className="country-filter-panel" aria-label="国家动向筛选">
            <div className="country-search">
              <Search size={16} />
              <input
                aria-label="搜索国家或地区"
                placeholder="搜索国家、地区、英文名或 ISO 代码"
                value={search}
                onChange={(e) => update("q", e.target.value)}
              />
            </div>
            <div className="country-selects">
              <label>
                观察窗口
                <select
                  value={days}
                  onChange={(e) => update("days", e.target.value)}
                >
                  <option value="7">近 7 天</option>
                  <option value="30">近 30 天</option>
                </select>
              </label>
              <label>
                观察主题
                <select
                  value={topic}
                  onChange={(e) => update("topic", e.target.value)}
                >
                  <option value="">全部主题</option>
                  {Object.entries(query.data.topic_labels).map(
                    ([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                矿种
                <input
                  aria-label="按矿种筛选国家动向"
                  placeholder="如 铜、锂、稀土"
                  value={mineral}
                  onChange={(e) => update("mineral", e.target.value)}
                />
              </label>
            </div>
            <div className="country-continent-tabs">
              <button
                aria-pressed={!continent}
                onClick={() => update("continent", "")}
              >
                全球
              </button>
              {["亚洲", "非洲", "欧洲", "美洲", "大洋洲", "极地"].map(
                (value) => (
                  <button
                    key={value}
                    aria-pressed={continent === value}
                    onClick={() => update("continent", value)}
                  >
                    {value}
                  </button>
                ),
              )}
              <label>
                <input
                  type="checkbox"
                  checked={onlyCovered}
                  onChange={(e) =>
                    update("covered", e.target.checked ? "1" : "")
                  }
                />
                只看已有资料
              </label>
            </div>
          </section>
          <div className="section-bar">
            <h2 className="panel-title">
              <Globe2 size={16} /> {t("国家观察目录", "Country directory")}
            </h2>
            <span className="text-sm text-muted">
              {visible.length} 个结果 · 主题统计近 {days} 天
            </span>
          </div>
          <div className="country-grid">
            {visible.slice(0, limit).map((item) => (
              <CountryCard
                key={item.iso2}
                item={item}
                days={days}
                labels={query.data.topic_labels}
              />
            ))}
          </div>
          {!visible.length && (
            <p className="panel text-muted">
              未找到匹配的国家动向，请调整筛选条件。
            </p>
          )}
          {visible.length > limit && (
            <div className="text-center mt-6">
              <button
                className="btn btn-outline"
                onClick={() => setLimit(limit + 36)}
              >
                显示更多国家与地区
              </button>
            </div>
          )}
          <p className="country-method-note">
            {query.data.coverage_note} {query.data.refresh_schedule}。
          </p>
        </>
      )}
    </main>
  );
}
