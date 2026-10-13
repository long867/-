"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Search,
  RefreshCw,
  Clock3,
  ChevronDown,
} from "lucide-react";
import { publicApi } from "@/lib/api";
import { SectionHeading } from "./section-heading";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { MineralMarket, MineralMarketItem, Price } from "@/types";

export function priceNumber(price: string | number): string {
  return Number(price).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}
export function quotationKind(price: Price): string {
  return price.price_type === "futures"
    ? "期货"
    : price.price_type === "benchmark"
      ? "参考价"
      : "现货";
}
export function MarketChange({ value }: { value: string | number | null }) {
  if (value === null) return <span className="text-muted">暂无对比</span>;
  const number = Number(value);
  return (
    <span className={number > 0 ? "up" : number < 0 ? "down" : "text-muted"}>
      {number > 0 ? "+" : ""}
      {number.toFixed(2)}%
    </span>
  );
}
function PriceRow({ price }: { price: Price }) {
  return (
    <div className="market-product">
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 break-words text-sm leading-relaxed">
          {price.product || price.mineral}
        </span>
        <span className="market-kind">{quotationKind(price)}</span>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-2 mt-3">
        <div className="market-price">
          {priceNumber(price.price)}
          <small>
            {price.currency === "CNY" ? "元" : price.currency}/{price.unit}
          </small>
        </div>
        <span className="text-sm font-semibold">
          <MarketChange value={price.change_pct} />
        </span>
      </div>
      <div className="mt-3 flex flex-wrap justify-between gap-2 text-xs text-muted">
        <span>报价 {price.date}</span>
        <a
          href={price.source_url || price.source}
          target="_blank"
          rel="noopener noreferrer"
          className="source-link"
        >
          {price.source_name || "原始来源"} ↗
        </a>
      </div>
      {price.fetched_at && (
        <p className="mt-1 text-xs text-muted">
          采集{" "}
          {new Date(price.fetched_at).toLocaleString("zh-CN", {
            timeZone: "Asia/Shanghai",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      )}
    </div>
  );
}
function MineralCard({ item }: { item: MineralMarketItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article
      className={`market-card ${item.prices.length ? "market-card-quoted" : ""}`}
    >
      <Link
        className="flex items-start justify-between gap-3"
        href={`/minerals/${encodeURIComponent(item.name)}`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="market-symbol">{item.symbol}</span>
          <div className="min-w-0">
            <h2 className="text-xl font-semibold">{item.name}</h2>
            <p className="text-xs text-muted mt-1 capitalize">
              {item.english_name}
            </p>
          </div>
        </div>
        <ArrowUpRight size={18} className="text-muted shrink-0" />
      </Link>
      <div className="flex flex-wrap justify-between gap-2 text-xs text-muted mt-4">
        <span>{item.group}</span>
        <span>{item.article_count} 篇情报</span>
      </div>
      {item.prices.length ? (
        <>
          {(expanded ? item.prices : item.prices.slice(0, 1)).map((price) => (
            <PriceRow key={price.id} price={price} />
          ))}
          {item.price_status === "stale" && (
            <p className="text-xs text-amber-400 mt-3">
              报价已超过 7 天，请核对来源更新情况
            </p>
          )}
          {item.prices.length > 1 && (
            <button
              className="market-expand"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
            >
              {expanded
                ? "收起产品报价"
                : `查看全部 ${item.prices.length} 个产品报价`}
              <ChevronDown size={14} className={expanded ? "rotate-180" : ""} />
            </button>
          )}
        </>
      ) : (
        <div className="market-no-price">
          <span>暂无公开报价</span>
          <p>待接入可靠价格源，不同产地与品级需分别报价。</p>
          <Link href={`/minerals/${encodeURIComponent(item.name)}`}>
            查看矿种情报 ↗
          </Link>
        </div>
      )}
    </article>
  );
}

export function MineralMarketPage({ initial }: { initial?: MineralMarket }) {
  const params = useSearchParams();
  const search = params.get("q") || "";
  const group = params.get("group") || "全部";
  const onlyQuoted = params.get("quoted") === "1";
  const [draft, setDraft] = useState(search);
  useEffect(() => setDraft(search), [search]);
  const query = useQuery({
    queryKey: ["mineral-market"],
    queryFn: () => publicApi<MineralMarket>("/minerals/market"),
    initialData: initial,
    staleTime: 300000,
    refetchInterval: 300000,
  });
  function update(values: Record<string, string>) {
    const next = new URLSearchParams(window.location.search);
    Object.entries(values).forEach(([key, value]) =>
      value ? next.set(key, value) : next.delete(key),
    );
    // Next.js integrates native history with useSearchParams without an RSC request.
    window.history.replaceState(
      null,
      "",
      `/minerals${next.size ? `?${next}` : ""}`,
    );
  }
  const data = query.data;
  const groups = [
    "全部",
    ...Array.from(new Set(data?.items.map((item) => item.group) || [])),
  ];
  const filtered = (data?.items || [])
    .filter(
      (item) =>
        (group === "全部" || item.group === group) &&
        (!onlyQuoted || item.prices.length) &&
        (!search ||
          [
            item.name,
            item.english_name,
            item.symbol,
            ...item.prices.map((price) => price.product || ""),
          ]
            .join(" ")
            .toLowerCase()
            .includes(search.toLowerCase())),
    )
    .sort(
      (a, b) =>
        Number(Boolean(b.prices.length)) - Number(Boolean(a.prices.length)),
    );
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="THE MINERAL MARKET ATLAS"
        zh="全球矿种 · 每日行情"
        en="Mineral market atlas"
        description="从贵金属到新能源、稀土和非金属矿产，一个持续更新的资源观察窗口。"
        descriptionEn="Daily public quotations, original dates and traceable sources."
      />
      <section className="market-summary" aria-label="行情覆盖情况">
        <div>
          <span>资源目录</span>
          <strong>
            {data?.total ?? "—"}
            <small>项</small>
          </strong>
        </div>
        <div>
          <span>有公开报价</span>
          <strong>
            {data?.quoted_minerals ?? "—"}
            <small>矿种</small>
          </strong>
        </div>
        <div>
          <span>产品报价序列</span>
          <strong>
            {data?.quoted_products ?? "—"}
            <small>个</small>
          </strong>
        </div>
        <div className="market-schedule">
          <span>
            <Clock3 size={14} /> 每日自动采集
          </span>
          <b>08:30 / 17:30 / 20:30</b>
          <small>北京时间 · 页面每 5 分钟检查更新</small>
        </div>
      </section>
      <div className="market-toolbar">
        <form
          className="market-search"
          onSubmit={(event) => {
            event.preventDefault();
            update({ q: draft.trim() });
          }}
        >
          <Search size={18} />
          <input
            aria-label="搜索矿种或产品"
            placeholder="搜索矿种、元素符号或报价产品…"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              update({ q: event.target.value.trim() });
            }}
          />
        </form>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={onlyQuoted}
            onChange={(event) =>
              update({ quoted: event.target.checked ? "1" : "" })
            }
          />
          仅看有报价
        </label>
        <button
          className="btn"
          onClick={() => query.refetch()}
          disabled={query.isFetching}
        >
          <RefreshCw
            size={14}
            className={query.isFetching ? "animate-spin" : ""}
          />
          检查更新
        </button>
      </div>
      <div className="market-groups" role="group" aria-label="矿种类别筛选">
        {groups.map((name) => (
          <button
            key={name}
            className={`chip ${name === group ? "active" : ""}`}
            aria-pressed={name === group}
            onClick={() => update({ group: name === "全部" ? "" : name })}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="market-caption">
        <span>{filtered.length} 项资源 · 涨跌幅对比同序列前一报价</span>
        <span>
          {data?.latest_checked_at
            ? `最近采集 ${new Date(data.latest_checked_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" })}`
            : "等待价格源首次采集"}
        </span>
      </div>
      {query.isPending ? (
        <SkeletonCards />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : !filtered.length ? (
        <EmptyState
          title="没有匹配的矿种"
          detail="请调整搜索关键词或筛选条件。"
        />
      ) : (
        <div className="market-grid">
          {filtered.map((item) => (
            <MineralCard key={item.name} item={item} />
          ))}
        </div>
      )}
      <p className="market-note">
        {data?.quotation_note ||
          "公开每日报价；休市保留最近报价，非分钟级行情。"}{" "}
        元素目录不代表统一原矿报价；参考价、精矿、金属与加工产品分别标注，暂未取得可靠报价的矿种显示数据状态。
      </p>
    </main>
  );
}

export function MineralMarketStrip({ initial }: { initial?: MineralMarket }) {
  const query = useQuery({
    queryKey: ["mineral-market"],
    queryFn: () => publicApi<MineralMarket>("/minerals/market"),
    initialData: initial,
    staleTime: 300000,
    refetchInterval: 300000,
  });
  const items = (query.data?.items || [])
    .filter((item) => item.prices.length)
    .slice(0, 8);
  if (!items.length) return null;
  return (
    <section className="panel market-strip">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-5">
        <div>
          <p className="eyebrow">DAILY MARKET PULSE</p>
          <h2 className="text-xl mt-2">矿产每日行情</h2>
        </div>
        <Link href="/minerals?quoted=1" className="source-link text-sm">
          全部 {query.data?.quoted_minerals} 个矿种行情 ↗
        </Link>
      </div>
      <div className="market-strip-grid">
        {items.map((item) => {
          const price = item.prices[0];
          return (
            <Link
              key={item.name}
              href={`/minerals/${encodeURIComponent(item.name)}`}
              className="market-strip-item"
            >
              <div className="flex justify-between">
                <b>{item.name}</b>
                <span className="text-sm">
                  <MarketChange value={price.change_pct} />
                </span>
              </div>
              <strong>
                {priceNumber(price.price)}
                <small>
                  {price.currency === "CNY" ? "元" : price.currency}/
                  {price.unit}
                </small>
              </strong>
              <p>
                {price.product?.split("（")[0]} · {quotationKind(price)}
              </p>
              <p>报价 {price.date}</p>
            </Link>
          );
        })}
      </div>
      <p className="text-xs text-muted mt-4">
        公开每日报价 · 以来源报价日期为准 · 点击矿种查看产品、来源与历史走势
      </p>
    </section>
  );
}
