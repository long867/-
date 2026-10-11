"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Archive, ArrowUpRight } from "lucide-react";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import type { Digest, ReportPage } from "@/types";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";

export function ReportArchive({
  kind,
  select,
}: {
  kind?: Digest["kind"];
  select?: (report: Digest) => void;
}) {
  const { t } = usePreferences();
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["report-archive", kind, page],
    queryFn: () =>
      publicApi<ReportPage>(
        `/digest/reports?page=${page}&page_size=6${kind ? `&kind=${kind}` : ""}`,
      ),
    staleTime: 60000,
  });
  return (
    <section className="mt-10" aria-label={t("报告归档", "Report archive")}>
      <div className="section-bar">
        <h2 className="flex items-center gap-2">
          <Archive size={17} />
          {t("报告归档", "Report archive")}
        </h2>
        <span className="text-xs text-muted">
          {t("已完成的统计周期", "Completed calendar periods")}
        </span>
      </div>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : query.isPending ? (
        <SkeletonCards count={2} />
      ) : !query.data.items.length ? (
        <EmptyState
          title={t("尚无归档报告", "No archived reports yet")}
          detail={t(
            "日报每天 08:00、周报每周一 08:00、月报每月 1 日 08:00 生成。",
            "Daily at 08:00, weekly on Monday at 08:00, monthly on the first at 08:00.",
          )}
        />
      ) : (
        <>
          <div className="policy-grid">
            {query.data.items.map((report) => {
              const label =
                report.kind === "daily"
                  ? t("日报", "Daily")
                  : report.kind === "weekly"
                    ? t("周报", "Weekly")
                    : t("月报", "Monthly");
              return (
                <article key={report.id} className="policy-card">
                  <div className="article-meta">
                    <span className="tag">{label}</span>
                    <span>{report.period_start}</span>
                  </div>
                  <h3 className="text-base leading-7 my-3">
                    {select ? (
                      <button
                        className="report-link"
                        onClick={() => select(report)}
                      >
                        {report.title}
                      </button>
                    ) : (
                      <Link
                        href={`/digest?kind=${report.kind}&report=${report.id}`}
                        prefetch={false}
                      >
                        {report.title}
                      </Link>
                    )}
                  </h3>
                  <p>
                    {report.stats.article_count} {t("篇文章", "articles")} ·{" "}
                    {report.stats.source_count} {t("个信源", "sources")}
                  </p>
                  <span className="source-link">
                    {t("查看完整报告", "Read report")}
                    <ArrowUpRight size={12} />
                  </span>
                </article>
              );
            })}
          </div>
          <div className="flex justify-end items-center gap-4 mt-5">
            <button
              className="btn btn-outline"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              {t("上一页", "Previous")}
            </button>
            <span className="text-xs text-muted">
              {page} / {Math.max(1, Math.ceil(query.data.total / 6))}
            </span>
            <button
              className="btn btn-outline"
              disabled={page * 6 >= query.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("下一页", "Next")}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
