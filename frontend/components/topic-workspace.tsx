"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Bookmark,
  Check,
  Download,
  FlaskConical,
  Layers3,
  LockKeyhole,
  RefreshCw,
  Scale,
  ShieldCheck,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { api } from "@/lib/api";
import { topicMarkdown } from "@/lib/topic-export.mjs";
import type { Topic, TopicPage, TopicType, TopicWindow } from "@/types";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";

export function TopicWorkspace() {
  const auth = useAuth();
  const { t } = usePreferences();
  const client = useQueryClient();
  const [type, setType] = useState<TopicType | "">("");
  const [windowDays, setWindowDays] = useState<TopicWindow>("30d");
  const [saved, setSaved] = useState(false);
  const [sort, setSort] = useState<"heat" | "recent">("heat");
  const [selected, setSelected] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    function sync() {
      const p = new URLSearchParams(location.search);
      const kind = p.get("type"),
        period = p.get("window");
      setType(kind === "achievement" || kind === "social_science" ? kind : "");
      setWindowDays(period === "7d" || period === "90d" ? period : "30d");
      setSaved(p.get("saved") === "true");
      setSelected(p.get("topic"));
    }
    sync();
    setReady(true);
    addEventListener("popstate", sync);
    return () => removeEventListener("popstate", sync);
  }, []);
  useEffect(() => {
    if (!auth.token) {
      setSelected(null);
      setFeedback("");
    }
  }, [auth.token]);

  function update(values: {
    type?: TopicType | "";
    window?: TopicWindow;
    saved?: boolean;
    topic?: string | null;
  }) {
    const p = new URLSearchParams(location.search);
    for (const [key, value] of Object.entries(values)) {
      if (value === null || value === "" || value === false) p.delete(key);
      else p.set(key, String(value));
    }
    history.replaceState(null, "", `${location.pathname}?${p}`);
    if (values.type !== undefined) setType(values.type);
    if (values.window) setWindowDays(values.window);
    if (values.saved !== undefined) setSaved(values.saved);
    if ("topic" in values) setSelected(values.topic ?? null);
    setFeedback("");
  }
  const params = new URLSearchParams({ window: windowDays, limit: "50" });
  if (type) params.set("type", type);
  if (saved) params.set("bookmarked", "true");
  const query = useQuery({
    queryKey: ["topics", auth.user?.id, type, windowDays, saved],
    queryFn: () =>
      api<TopicPage>(`/topics/recommendations?${params}`, {}, auth.token),
    enabled: ready && !!auth.token,
    staleTime: 30000,
    retry: false,
  });
  const detail = useQuery({
    queryKey: ["topic-detail", auth.user?.id, selected],
    queryFn: () =>
      api<Topic>(`/topics/${encodeURIComponent(selected!)}`, {}, auth.token),
    enabled: ready && !!auth.token && !!selected,
    staleTime: 0,
    retry: false,
  });
  const refresh = useMutation({
    mutationFn: () =>
      api<TopicPage>(
        "/topics/recommendations/refresh",
        {
          method: "POST",
          body: JSON.stringify({ type: type || null, window: windowDays }),
        },
        auth.token,
      ),
    onSuccess: async (data) => {
      setFeedback(
        data.mode === "llm" || data.mode === "mixed"
          ? t(
              "选题已更新，AI 建议附可核验原文。",
              "Updated with verified evidence.",
            )
          : data.mode === "insufficient"
            ? data.message
            : t(
                "选题已更新，本次采用有原文依据的规则推荐。",
                "Updated using evidence-backed rules.",
              ),
      );
      await client.invalidateQueries({ queryKey: ["topics", auth.user?.id] });
      await client.invalidateQueries({
        queryKey: ["topic-detail", auth.user?.id],
      });
    },
  });
  const bookmark = useMutation({
    mutationFn: (topic: Topic) =>
      api<void>(
        `/topics/${topic.id}/bookmark`,
        {
          method: topic.bookmarked ? "DELETE" : "PUT",
        },
        auth.token,
      ),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["topics", auth.user?.id] });
      await client.invalidateQueries({
        queryKey: ["topic-detail", auth.user?.id],
      });
    },
  });
  function exportTopic(topic: Topic) {
    const url = URL.createObjectURL(
      new Blob([topicMarkdown(topic)], { type: "text/markdown;charset=utf-8" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `MiningIntel-topic-${topic.id}.md`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const data = query.data;
  const items = [...(data?.items || [])].sort((a, b) =>
    sort === "heat"
      ? b.heat_score - a.heat_score
      : Date.parse(b.generated_at) - Date.parse(a.generated_at),
  );
  const label = (kind: TopicType) =>
    kind === "achievement"
      ? t("成果选题", "Applied research")
      : t("社科选题", "Social science");
  function citationText(value: string) {
    return value.split(/(\[\d+\])/).map((part, i) => {
      const match = /^\[(\d+)\]$/.exec(part);
      return match ? (
        <a
          key={i}
          className="citation-link"
          href={`#topic-evidence-${match[1]}`}
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById(`topic-evidence-${match[1]}`)
              ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }}
        >
          {part}
        </a>
      ) : (
        <span key={i}>{part}</span>
      );
    });
  }
  return (
    <main className="workspace topic-workspace">
      <section className="topic-hero">
        <div className="topic-orbit" aria-hidden="true">
          <FlaskConical size={64} strokeWidth={1} />
        </div>
        <div className="eyebrow">RESEARCH OPPORTUNITY INTELLIGENCE</div>
        <div className="topic-private">
          <LockKeyhole size={13} />
          {t("账号专属工作台", "Private workspace")}
        </div>
        <h1>
          {t(
            "让研究选题，\n从真实依据出发。",
            "Research ideas,\ngrounded in evidence.",
          )}
        </h1>
        <p>
          {t(
            "从前沿成果、政策文件与产业事件中梳理值得进一步研究的问题。每一条推荐都带原文依据，让设想有迹可循。",
            "Discover research questions from scholarly papers, policies and industry coverage, with original evidence for every proposal.",
          )}
        </p>
        <div className="topic-promises">
          <span>
            <ShieldCheck size={15} />
            {t("原文可追溯", "Traceable evidence")}
          </span>
          <span>
            <Layers3 size={15} />
            {t("成果 / 社科双口径", "Two research tracks")}
          </span>
          <span>
            <Bookmark size={15} />
            {t("收藏与导出", "Save & export")}
          </span>
        </div>
      </section>
      {!auth.token ? (
        <section className="panel topic-login">
          <LockKeyhole size={28} className="text-accent" />
          <h2>
            {t(
              "登录，开启你的研究选题库",
              "Sign in to your research workspace",
            )}
          </h2>
          <p>
            {t(
              "推荐记录与收藏仅本人可见。前沿成果栏目仍可公开浏览。",
              "Your proposals and favorites are private. Scholarly frontiers remain public.",
            )}
          </p>
          <div className="flex flex-wrap gap-3 mt-5">
            <Button asChild>
              <Link href="/login?next=%2Ftopics">
                {t("登录 / 注册", "Sign in / Register")}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/frontier">
                {t("浏览前沿成果", "Explore frontiers")}
              </Link>
            </Button>
          </div>
        </section>
      ) : (
        <>
          <div className="topic-controls">
            <div className="tabs" aria-label={t("选题类型", "Research track")}>
              {(["", "achievement", "social_science"] as const).map((kind) => (
                <button
                  key={kind}
                  className={type === kind ? "active" : ""}
                  aria-pressed={type === kind}
                  onClick={() => update({ type: kind })}
                >
                  {kind ? label(kind) : t("全部选题", "All tracks")}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <select
                aria-label={t("热度时间窗", "Coverage window")}
                value={windowDays}
                onChange={(e) =>
                  update({ window: e.target.value as TopicWindow })
                }
              >
                <option value="7d">{t("近 7 天", "Past 7 days")}</option>
                <option value="30d">{t("近 30 天", "Past 30 days")}</option>
                <option value="90d">{t("近 90 天", "Past 90 days")}</option>
              </select>
              <select
                aria-label={t("选题排序", "Sort proposals")}
                value={sort}
                onChange={(e) => setSort(e.target.value as "heat" | "recent")}
              >
                <option value="heat">
                  {t("关注度优先", "Attention first")}
                </option>
                <option value="recent">{t("最近生成", "Most recent")}</option>
              </select>
              <Button
                variant="outline"
                onClick={() => update({ saved: !saved })}
                aria-pressed={saved}
              >
                <Bookmark size={15} />
                {t("我的收藏", "Saved")}
              </Button>
              <Button
                disabled={refresh.isPending || query.isFetching}
                onClick={() => {
                  refresh.reset();
                  refresh.mutate();
                }}
              >
                <RefreshCw
                  size={15}
                  className={refresh.isPending ? "animate-spin" : ""}
                />
                {refresh.isPending
                  ? t("正在分析…", "Analyzing…")
                  : t("更新推荐", "Refresh ideas")}
              </Button>
            </div>
          </div>
          <div className="topic-status" role="status">
            <span>
              {data
                ? t(
                    `当前 ${data.total} 个可核验选题`,
                    `${data.total} verified proposals`,
                  )
                : t("正在读取研究资料", "Loading research coverage")}
            </span>
            <span>
              {t(
                "关注度评分反映资料覆盖，不代表研究价值或市场预测。",
                "Attention reflects coverage, not forecasts or research merit.",
              )}
            </span>
          </div>
          {feedback && (
            <p className="topic-feedback" role="status">
              <Check size={16} />
              {feedback}
            </p>
          )}
          {refresh.isError && <ErrorState error={refresh.error} />}
          {bookmark.isError && <ErrorState error={bookmark.error} />}
          {query.isError ? (
            <ErrorState error={query.error} retry={() => query.refetch()} />
          ) : query.isPending ? (
            <SkeletonCards />
          ) : !items.length ? (
            <EmptyState
              title={
                saved
                  ? t("还没有收藏选题", "No saved proposals")
                  : t("依据不足，暂无法推荐", "Insufficient evidence")
              }
              detail={
                saved
                  ? t(
                      "从推荐卡片中收藏感兴趣的选题。",
                      "Save proposals from the recommendation cards.",
                    )
                  : t(
                      "所选时间窗暂无可核验资料，可扩大到近 90 天。",
                      "Broaden the coverage window to 90 days.",
                    )
              }
            />
          ) : (
            <div className="topic-grid">
              {items.map((topic) => (
                <article className="topic-card" key={topic.id}>
                  <div className="topic-card-top">
                    <span className="tag">
                      {topic.type === "achievement" ? (
                        <FlaskConical size={13} />
                      ) : (
                        <Scale size={13} />
                      )}
                      {label(topic.type)}
                    </span>
                    <button
                      className="icon-button"
                      aria-label={
                        topic.bookmarked
                          ? t("取消收藏", "Unsave")
                          : t("收藏选题", "Save proposal")
                      }
                      aria-pressed={topic.bookmarked}
                      disabled={bookmark.isPending}
                      onClick={() => bookmark.mutate(topic)}
                    >
                      <Bookmark
                        size={17}
                        fill={topic.bookmarked ? "currentColor" : "none"}
                      />
                    </button>
                  </div>
                  <button
                    className="topic-open"
                    onClick={() => update({ topic: topic.id })}
                  >
                    <h2>{topic.title_zh || topic.title}</h2>
                    <p>{topic.summary}</p>
                  </button>
                  <div className="topic-tags">
                    {[
                      ...new Set([
                        ...topic.minerals.slice(0, 3),
                        ...topic.keywords.slice(0, 3),
                      ]),
                    ].map((word) => (
                      <span className="tag" key={word}>
                        {word}
                      </span>
                    ))}
                  </div>
                  <div className="topic-card-bottom">
                    <span>
                      <b>{topic.heat_score.toFixed(0)}</b> / 100{" "}
                      <small>{t("关注度", "Attention")}</small>
                    </span>
                    <button onClick={() => update({ topic: topic.id })}>
                      {topic.evidence_count} {t("条证据", "sources")}
                      <ArrowUpRight size={15} />
                    </button>
                  </div>
                  <div className="topic-score" aria-hidden="true">
                    <span style={{ width: `${topic.heat_score}%` }} />
                  </div>
                  <span className="topic-mode">
                    {topic.mode === "llm"
                      ? t(
                          "AI 辅助 · 依据已核验",
                          "AI assisted · evidence verified",
                        )
                      : t("规则推荐 · 真实资料", "Rule based · real coverage")}
                  </span>
                </article>
              ))}
            </div>
          )}
          <div className="topic-boundary panel">
            <ShieldCheck size={20} />
            <p>
              {t(
                "选题是研究设想，不是已证实的结论。创新性、研究空白、实施效果与申报条件仍需文献检索、专家评估及实地验证。",
                "Proposals are research hypotheses. Novelty, gaps, effects and application requirements need literature review, expert assessment and validation.",
              )}
            </p>
          </div>
        </>
      )}
      <Dialog
        open={!!selected && !!auth.token}
        onOpenChange={(open) => {
          if (!open) update({ topic: null });
        }}
        title={t("选题与原文依据", "Proposal & original evidence")}
        description={t(
          "推荐理由逐条关联库内语料，研究建议须进一步验证。",
          "Reasons are linked to original evidence. Proposed research requires validation.",
        )}
      >
        {detail.isError ? (
          <ErrorState error={detail.error} retry={() => detail.refetch()} />
        ) : detail.isPending ? (
          <SkeletonCards count={1} />
        ) : (
          detail.data && (
            <div className="topic-detail">
              <div className="flex flex-wrap gap-2 mb-4">
                <span className="tag">{label(detail.data.type)}</span>
                <span className="tag">
                  {detail.data.heat_score.toFixed(0)} / 100
                </span>
              </div>
              <h2>{detail.data.title_zh}</h2>
              <p>{detail.data.summary}</p>
              <div className="flex flex-wrap gap-3 my-5">
                <Button
                  variant="outline"
                  disabled={bookmark.isPending}
                  onClick={() => bookmark.mutate(detail.data!)}
                >
                  <Bookmark size={15} />
                  {detail.data.bookmarked
                    ? t("取消收藏", "Unsave")
                    : t("收藏选题", "Save proposal")}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => exportTopic(detail.data!)}
                >
                  <Download size={15} />
                  {t("导出 Markdown", "Export Markdown")}
                </Button>
              </div>
              {bookmark.isError && <ErrorState error={bookmark.error} />}
              <h3>{t("推荐理由", "Research rationale")}</h3>
              <div className="topic-rationale">
                {citationText(detail.data.rationale)}
              </div>
              <h3>{t("可追溯原文证据", "Traceable original evidence")}</h3>
              {detail.data.evidence.map((e) => (
                <article
                  id={`topic-evidence-${e.position}`}
                  key={e.id}
                  className="topic-evidence"
                >
                  <div className="article-meta">
                    <span className="text-accent">[{e.position}]</span>
                    <span>{e.source_name}</span>
                    <span>
                      {e.published_at
                        ? new Date(e.published_at).toLocaleDateString("zh-CN", {
                            timeZone: "Asia/Shanghai",
                          })
                        : t("日期未知", "Unknown date")}
                    </span>
                  </div>
                  <h4>{e.title}</h4>
                  <blockquote lang="und">{e.quote}</blockquote>
                  <p>
                    {t(
                      "研究建议（待验证）：",
                      "Proposed research (unverified): ",
                    )}
                    {e.support}
                  </p>
                  <small>
                    {e.quote_field === "title"
                      ? t("原文标题", "Original title")
                      : t("原文正文", "Original text")}{" "}
                    · {t("字符位置", "Character span")} [{e.start_char},{" "}
                    {e.end_char})
                  </small>
                  <div className="flex flex-wrap gap-4 mt-3">
                    <Link
                      className="source-link"
                      href={`/articles/${e.article_id}`}
                    >
                      {t("查看库内资料", "Library record")}
                    </Link>
                    <a
                      className="source-link"
                      href={e.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {t("访问原文", "Original source")}
                      <ArrowUpRight size={13} />
                    </a>
                  </div>
                </article>
              ))}
              <p className="topic-detail-limit">{detail.data.limitation}</p>
            </div>
          )
        )}
      </Dialog>
    </main>
  );
}
