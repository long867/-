"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, MessagesSquare } from "lucide-react";
import { publicApi } from "@/lib/api";
import { useUrlFilters } from "@/hooks/use-url-filters";
import { ErrorState, SkeletonCards } from "./ui/states";
import type { CountryIntelligence } from "@/types";

export function CountryBrief({ name }: { name: string }) {
  const { filters, update } = useUrlFilters();
  const query = useQuery({
    queryKey: ["country-intelligence", name],
    queryFn: () =>
      publicApi<CountryIntelligence>(
        `/regions/${encodeURIComponent(name)}/intelligence`,
      ),
    staleTime: 300000,
  });
  if (query.isPending) return <SkeletonCards count={2} />;
  if (query.isError)
    return <ErrorState error={query.error} retry={() => query.refetch()} />;
  const item = query.data.country;
  return (
    <section className="country-brief">
      <div className="country-brief-header">
        <div>
          <span className="country-kicker">
            {item.iso3} / {item.continent} / {item.subregion}
          </span>
          <h2>{name}资源动向观察</h2>
        </div>
        <Link
          className="btn btn-outline"
          href={`/chat?q=${encodeURIComponent(`请分析${name}近期矿产政策、出口与供应链、矿山项目动态，区分已知事实和推论，说明可能影响与需要继续跟踪的事项。`)}`}
        >
          <MessagesSquare size={15} />
          矿眸智探分析
        </Link>
      </div>
      <div className="country-stats">
        <div>
          <strong>{item.recent_count}</strong>
          <span>近 7 天报道</span>
        </div>
        <div>
          <strong>{item.source_count}</strong>
          <span>报道信源</span>
        </div>
        <div>
          <strong>{item.policy_count}</strong>
          <span>已收录政策文件</span>
        </div>
      </div>
      <div className="country-topic-tabs">
        <button
          aria-pressed={!filters.topic}
          onClick={() => update({ topic: "" })}
        >
          全部动向
        </button>
        {Object.entries(query.data.topic_labels).map(([key, label]) => (
          <button
            key={key}
            aria-pressed={filters.topic === key}
            onClick={() => update({ topic: key })}
          >
            {label}
            <span>{item.topics[key] || 0}</span>
          </button>
        ))}
      </div>
      <p className="text-xs text-muted mt-3 leading-relaxed">
        主题数字为近 7
        天报道线索，可点击筛选下方全部历史资料。政策文件数量单独核验；提及出口限制不代表措施已生效。
      </p>
      <div className="country-brief-stories">
        {query.data.articles.slice(0, 3).map((article) => (
          <Link
            href={`/articles/${article.id}`}
            key={article.id}
            prefetch={false}
          >
            <span>{article.title_zh || article.title}</span>
            <small>
              {article.source_name} ·{" "}
              {article.published_at?.slice(0, 10) || "日期未知"}
            </small>
            <ArrowUpRight size={13} />
          </Link>
        ))}
      </div>
      {!item.article_count && (
        <p className="country-empty">
          当前尚无该国家的可追溯资料；已保留观察入口，后续随公开信源更新补充。
        </p>
      )}
    </section>
  );
}
