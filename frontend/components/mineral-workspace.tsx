"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  Minus,
  Building2,
} from "lucide-react";
import { ArticleFeed } from "./article-feed";
import { PolicyCard } from "./policy-card";
import { SectionHeading } from "./section-heading";
import { SubscriptionDialog } from "./subscription-dialog";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import { EmptyState, SkeletonCards } from "./ui/states";
import type { ArticlePage, MineralFacet, Price, PolicyPage } from "@/types";
const PriceChart = dynamic(
  () => import("./price-chart").then((module) => module.PriceChart),
  { ssr: false, loading: () => <SkeletonCards count={1} /> },
);
export function MineralWorkspace({
  name,
  initial,
}: {
  name: string;
  initial?: ArticlePage;
}) {
  const { t } = usePreferences();
  const prices = useQuery({
    queryKey: ["mineral-prices", name],
    queryFn: () =>
      publicApi<Price[]>(`/minerals/${encodeURIComponent(name)}/prices`),
  });
  const facets = useQuery({
    queryKey: ["mineral-catalog"],
    queryFn: () => publicApi<MineralFacet[]>("/minerals"),
  });
  const policies = useQuery({
    queryKey: ["mineral-policies", name],
    queryFn: () =>
      publicApi<PolicyPage>(`/minerals/${encodeURIComponent(name)}/policies`),
  });
  const related = useQuery({
    queryKey: ["mineral-companies", name],
    queryFn: () =>
      publicApi<ArticlePage>(
        `/articles?mineral=${encodeURIComponent(name)}&page_size=100`,
      ),
  });
  const item = facets.data?.find((item) => item.name === name);
  const companies = Array.from(
    new Set(related.data?.items.flatMap((item) => item.companies) || []),
  );
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="COMMODITY INTELLIGENCE"
        zh={`${name} · 矿种情报`}
        en={`${name} · Commodity intelligence`}
        description="从真实报价、产业报道到政策变化，追踪这条资源链。"
        descriptionEn="Follow the resource chain through spot prices, industry reporting and policy."
        actions={<SubscriptionDialog mineral={name} />}
      />
      <div className="stat-inline mb-7">
        <span>
          {item?.article_count ?? initial?.total ?? "—"}{" "}
          {t("篇公开资料", "published articles")}
        </span>
        <span
          className={
            item?.trend === "up"
              ? "up"
              : item?.trend === "down"
                ? "down"
                : "muted"
          }
        >
          {item?.trend === "up" ? (
            <TrendingUp size={14} className="inline mr-1" />
          ) : item?.trend === "down" ? (
            <TrendingDown size={14} className="inline mr-1" />
          ) : (
            <Minus size={14} className="inline mr-1" />
          )}
          {t("近 7 天", "Past week")} · {item?.recent_count ?? "—"}{" "}
          {t("篇报道", "stories")}
        </span>
      </div>
      {prices.isPending ? (
        <SkeletonCards count={1} />
      ) : prices.data ? (
        <PriceChart prices={prices.data} />
      ) : (
        <EmptyState title={prices.error?.message} />
      )}
      <div className="dashboard">
        <ArticleFeed initial={initial} mineral={name} />
        <aside>
          <section className="panel">
            <h2 className="panel-title">{t("相关政策", "Related policy")}</h2>
            {policies.data?.items.length ? (
              policies.data.items.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} />
              ))
            ) : (
              <p className="subtitle text-xs">
                {t("暂无已发布政策资料。", "No published policy evidence yet.")}
              </p>
            )}
            <Link
              className="source-link mt-3"
              href={`/policies?mineral=${encodeURIComponent(name)}`}
            >
              {t("政策库", "Policy library")}
              <ArrowUpRight size={12} />
            </Link>
          </section>
          <section className="panel">
            <h2 className="panel-title">
              {t("报道中的相关公司", "Companies in coverage")}
              <Building2 size={13} className="text-muted" />
            </h2>
            {companies.slice(0, 15).map((company) => (
              <Link
                href={`/?company=${encodeURIComponent(company)}`}
                className="insight-row"
                key={company}
              >
                {company}
                <ArrowUpRight size={12} />
              </Link>
            ))}
            {!companies.length && (
              <p className="subtitle text-xs">
                {t("尚未提取到相关公司。", "No companies extracted yet.")}
              </p>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
