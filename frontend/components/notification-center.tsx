"use client";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, ArrowUpRight } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import type { NoticePage } from "@/types";
import { SectionHeading } from "./section-heading";
import { AnimatedPanel } from "./animated-panel";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";

export function NotificationCenter() {
  const auth = useAuth();
  const { t } = usePreferences();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["notifications", auth.user?.id, page],
    queryFn: () =>
      publicApi<NoticePage>(
        `/notifications?page=${page}&page_size=12`,
        {},
        auth.token,
      ),
    enabled: !!auth.token,
    staleTime: 30000,
    refetchInterval: 60000,
  });
  const read = useMutation({
    mutationFn: (id?: string) =>
      publicApi(
        `/notifications/${id ? `${id}/read` : "read-all"}`,
        { method: "POST" },
        auth.token,
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: ["notifications"] }),
  });
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="YOUR INTELLIGENCE INBOX"
        zh="消息中心"
        en="Intelligence inbox"
        description="归档报告、真实价格预警与个人已读状态。"
        descriptionEn="Archived reports, genuine price warnings and your private read state."
      />
      {!auth.user ? (
        <div className="panel">
          <Bell size={24} className="text-accent mb-5" />
          <p>
            {t(
              "登录后查看通知并保存已读状态。",
              "Sign in to view notifications and keep your read state.",
            )}
          </p>
          <Link className="btn btn-primary mt-5" href="/login">
            {t("登录", "Sign in")}
          </Link>
        </div>
      ) : (
        <>
          <div className="section-bar">
            <h2>
              {query.data?.unread_count ?? "—"} {t("条未读", "unread")}
            </h2>
            <button
              className="btn btn-outline"
              disabled={read.isPending || !query.data?.unread_count}
              onClick={() => read.mutate(undefined)}
            >
              <CheckCheck size={15} />
              {t("全部标为已读", "Mark all read")}
            </button>
          </div>
          {read.isError && <ErrorState error={read.error} />}
          {query.isError ? (
            <ErrorState error={query.error} retry={() => query.refetch()} />
          ) : query.isPending ? (
            <SkeletonCards />
          ) : !query.data.items.length ? (
            <EmptyState
              title={t(
                "暂无报告或价格预警",
                "No reports or price warnings yet",
              )}
            />
          ) : (
            <>
              <div className="notification-list">
                {query.data.items.map((item) => (
                  <AnimatedPanel
                    key={item.id}
                    className={`panel notification-item ${item.read ? "is-read" : ""}`}
                  >
                    <div className="flex flex-wrap justify-between gap-3">
                      <span
                        className={`tag ${item.kind === "price_alert" ? `alert-${item.severity || "green"}` : ""}`}
                      >
                        {item.kind === "report"
                          ? t("报告", "Report")
                          : t("价格预警", "Price warning")}
                      </span>
                      <span className="text-xs text-muted">
                        {new Date(item.created_at).toLocaleString("zh-CN", {
                          timeZone: "Asia/Shanghai",
                        })}
                      </span>
                    </div>
                    <h3 className="mt-4">
                      <Link
                        href={item.url}
                        prefetch={false}
                        onClick={() => {
                          if (!item.read) read.mutate(item.id);
                        }}
                      >
                        {!item.read && <span className="status-dot mr-2" />}
                        {item.title}
                      </Link>
                    </h3>
                    <p className="notification-preview text-muted text-sm leading-7 mt-3 whitespace-pre-line">
                      {item.body}
                    </p>
                    <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
                      <div className="flex gap-2 flex-wrap">
                        {[...item.minerals, ...item.regions].map((x, i) => (
                          <span className="tag" key={`${x}-${i}`}>
                            {x}
                          </span>
                        ))}
                      </div>
                      <div className="flex items-center gap-4">
                        {!item.read && (
                          <button
                            className="source-link"
                            disabled={read.isPending}
                            onClick={() => read.mutate(item.id)}
                          >
                            {t("标为已读", "Mark read")}
                          </button>
                        )}
                        <Link
                          className="source-link"
                          href={item.url}
                          prefetch={false}
                        >
                          {t("查看详情", "Details")}
                          <ArrowUpRight size={12} />
                        </Link>
                      </div>
                    </div>
                  </AnimatedPanel>
                ))}
              </div>
              <div className="flex justify-end items-center gap-4 mt-6">
                <button
                  className="btn btn-outline"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  {t("上一页", "Previous")}
                </button>
                <span>
                  {page} / {Math.max(1, Math.ceil(query.data.total / 12))}
                </span>
                <button
                  className="btn btn-outline"
                  disabled={page * 12 >= query.data.total}
                  onClick={() => setPage(page + 1)}
                >
                  {t("下一页", "Next")}
                </button>
              </div>
            </>
          )}
        </>
      )}
    </main>
  );
}
