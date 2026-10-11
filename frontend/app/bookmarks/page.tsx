"use client";
import { useQueries } from "@tanstack/react-query";
import { publicApi } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "@/components/section-heading";
import { ArticleCard } from "@/components/article-card";
import { EmptyState, SkeletonCards } from "@/components/ui/states";
import type { Article } from "@/types";
export default function Bookmarks() {
  const { saved, t, toggleSaved } = usePreferences();
  const queries = useQueries({
    queries: saved.map((id) => ({
      queryKey: ["article", id],
      queryFn: () => publicApi<Article>(`/articles/${id}`),
      retry: false,
    })),
  });
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="YOUR READING LIST"
        zh="值得留下的情报。"
        en="Intelligence worth keeping."
        description="收藏保存在当前设备，文章内容始终从真实接口读取。"
        descriptionEn="Bookmarks stay on this device; article content comes from the live API."
      />
      {saved.length ? (
        queries.map((q, i) =>
          q.isPending ? (
            <SkeletonCards key={saved[i]} count={1} />
          ) : q.isError ? (
            <div className="panel mb-3" key={saved[i]}>
              <p className="text-muted">
                {t(
                  "这篇文章暂时无法访问或已撤回。",
                  "This article is unavailable or has been withdrawn.",
                )}
              </p>
              <button
                className="source-link mt-3"
                onClick={() => toggleSaved(saved[i])}
              >
                {t("移除收藏", "Remove bookmark")}
              </button>
            </div>
          ) : q.data ? (
            <ArticleCard article={q.data} key={saved[i]} />
          ) : null,
        )
      ) : (
        <EmptyState
          title={t("还没有收藏", "No bookmarks yet")}
          detail={t(
            "点击资讯卡片上的书签图标，创建你的阅读清单。",
            "Use the bookmark icon on a card to build your reading list.",
          )}
        />
      )}
    </main>
  );
}
