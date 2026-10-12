"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Radar,
  ListChecks,
  GitBranch,
  BookOpen,
  RefreshCw,
} from "lucide-react";
import { publicApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "./section-heading";
import { EmptyState, ErrorState, SkeletonCards } from "./ui/states";
import type { Facets } from "@/types";
import type { ResearchInput, ResearchResult } from "@/types/research";

export function ResearchWorkspace({
  initial,
  initialScope,
}: {
  initial?: ResearchResult;
  initialScope?: { mineral?: string; region?: string };
}) {
  const { t } = usePreferences();
  const auth = useAuth();
  const client = useQueryClient();
  const [mineral, setMineral] = useState(
    initialScope?.mineral || initial?.scope.mineral || "",
  );
  const [region, setRegion] = useState(
    initialScope?.region || initial?.scope.region || "",
  );
  const [days, setDays] = useState(30);
  const [role, setRole] = useState<ResearchInput["role"]>("general");
  const [focus, setFocus] = useState("矿产资源供需、政策影响与应对措施");
  const [generated, setGenerated] = useState<ResearchResult>();
  const facets = useQuery({
    queryKey: ["facets"],
    queryFn: () => publicApi<Facets>("/facets"),
    staleTime: 300000,
  });
  const params = new URLSearchParams({ days: String(days) });
  if (mineral) params.set("mineral", mineral);
  if (region) params.set("region", region);
  const overview = useQuery({
    queryKey: ["research-overview", params.toString()],
    queryFn: () => publicApi<ResearchResult>(`/research/overview?${params}`),
    initialData:
      days === 30 &&
      mineral === (initial?.scope.mineral || "") &&
      region === (initial?.scope.region || "")
        ? initial
        : undefined,
    staleTime: 300000,
  });
  const archives = useQuery({
    queryKey: ["research-history", auth.user?.id],
    queryFn: () =>
      publicApi<
        { id: string; focus: string; created_at: string; mode: string }[]
      >("/research/history", {}, auth.token),
    enabled: !!auth.token,
  });
  const generation = useMutation({
    mutationFn: () =>
      publicApi<ResearchResult>(
        "/research",
        {
          method: "POST",
          body: JSON.stringify({
            mineral: mineral || null,
            region: region || null,
            days,
            role,
            focus,
          }),
        },
        auth.token,
      ),
    onSuccess: (result) => {
      setGenerated(result);
      client.invalidateQueries({
        queryKey: ["research-history", auth.user?.id],
      });
    },
  });
  const restore = useMutation({
    mutationFn: (id: string) =>
      publicApi<ResearchResult>(`/research/reports/${id}`, {}, auth.token),
    onSuccess: (result) => setGenerated(result),
  });
  const data = generated || overview.data;
  function reveal(index: number) {
    const element = document.getElementById(`research-source-${index}`);
    if (element instanceof HTMLDetailsElement) {
      element.open = true;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
  function refs(indices: number[]) {
    return (
      <span className="inline-flex flex-wrap gap-2 ml-2">
        {indices.map((index) => (
          <button
            className="text-primary underline"
            type="button"
            key={index}
            onClick={() => reveal(index)}
            aria-label={`查看研判来源 ${index}`}
          >
            [{index}]
          </button>
        ))}
      </span>
    );
  }
  const date = (value: string | null) =>
    value
      ? new Date(value).toLocaleDateString("zh-CN", {
          timeZone: "Asia/Shanghai",
        })
      : "日期未披露";
  return (
    <main className="workspace research-workspace">
      <SectionHeading
        eyebrow="DECISION INTELLIGENCE"
        zh="看清影响，准备下一步。"
        en="Understand implications. Prepare the next step."
        description="把真实资料整理为已知事实、条件性影响和应对清单，每项判断都能追溯来源。"
        descriptionEn="Facts, conditional scenarios and actions grounded in published evidence."
      />
      <section className="panel mb-7 research-controls">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          <label className="text-sm">
            {t("关注矿种", "Mineral")}
            <select
              className="w-full mt-2"
              aria-label="研判矿种"
              value={mineral}
              onChange={(e) => {
                setMineral(e.target.value);
                setGenerated(undefined);
              }}
            >
              <option value="">{t("全部矿种", "All minerals")}</option>
              {facets.data?.minerals.map((x) => (
                <option key={x.name}>{x.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            {t("关注地区", "Region")}
            <select
              className="w-full mt-2"
              aria-label="研判地区"
              value={region}
              onChange={(e) => {
                setRegion(e.target.value);
                setGenerated(undefined);
              }}
            >
              <option value="">{t("全球", "Global")}</option>
              {facets.data?.regions.map((x) => (
                <option key={x.name}>{x.name}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            {t("资讯观察范围", "Coverage window")}
            <select
              className="w-full mt-2"
              value={days}
              onChange={(e) => {
                setDays(Number(e.target.value));
                setGenerated(undefined);
              }}
            >
              <option value={7}>近一周</option>
              <option value={30}>近一个月</option>
              <option value={90}>近三个月</option>
              <option value={365}>近一年</option>
            </select>
          </label>
          <label className="text-sm">
            {t("决策视角", "Perspective")}
            <select
              className="w-full mt-2"
              value={role}
              onChange={(e) => setRole(e.target.value as ResearchInput["role"])}
            >
              <option value="general">通用经营决策</option>
              <option value="procurement">采购与供应链</option>
              <option value="project">矿山与项目开发</option>
              <option value="policy">政策与产业研究</option>
            </select>
          </label>
        </div>
        <label className="text-sm" htmlFor="research-focus">
          {t(
            "想了解哪些影响、准备采取什么行动？",
            "What implications and actions do you want to explore?",
          )}
        </label>
        <textarea
          id="research-focus"
          className="w-full mt-2"
          rows={3}
          maxLength={500}
          value={focus}
          onChange={(e) => setFocus(e.target.value)}
        />
        <div className="flex flex-wrap justify-between items-center gap-4 mt-4">
          <p className="text-sm text-muted">
            {t(
              "先查看资料研判；登录后可生成专题分析并保存。",
              "Browse evidence-based research; sign in to generate and save personalized analysis.",
            )}
          </p>
          {auth.token ? (
            <button
              className="btn btn-primary"
              disabled={generation.isPending || focus.trim().length < 2}
              onClick={() => generation.mutate()}
            >
              <Radar size={16} />
              {generation.isPending
                ? t("正在核对资料与分析…", "Analyzing evidence…")
                : t("生成专题研判", "Generate research")}
            </button>
          ) : (
            <Link className="btn btn-primary" href="/login?next=%2Fresearch">
              {t("登录后生成专题研判", "Sign in to generate")}
            </Link>
          )}
        </div>
        {generation.isPending && (
          <p role="status" className="text-sm text-muted mt-4">
            正在分析作用路径、成立条件和应对措施；结果会先核对来源，再呈现。
          </p>
        )}
        {generation.isError && (
          <ErrorState
            error={generation.error}
            retry={() => generation.mutate()}
          />
        )}
      </section>
      {overview.isError ? (
        <ErrorState error={overview.error} retry={() => overview.refetch()} />
      ) : !data ? (
        <SkeletonCards count={3} />
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-7">
            {[
              ["近期资料", data.coverage.article_count],
              ["本次引用信源", data.coverage.source_count],
              ["政策依据", data.coverage.policy_count],
              ["可比报价观测", data.coverage.price_observations],
            ].map(([label, value]) => (
              <div className="panel" key={label}>
                <p className="text-xs text-muted">{label}</p>
                <strong className="block text-3xl mt-3">{value}</strong>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap justify-between text-xs text-muted gap-3 mb-6">
            <span>资料截止：{date(data.coverage.latest_published_at)}</span>
            <span>
              {data.mode === "llm"
                ? "AI专题研判 · 事实引文已核对"
                : data.mode === "evidence_based"
                  ? "资料研判 · 条件性情景与核对建议"
                  : "资料不足"}{" "}
              · {date(data.generated_at)}
            </span>
          </div>
          {data.mode === "insufficient" ? (
            <EmptyState
              title="当前条件下资料不足"
              detail="调整矿种、地区或观察范围后再试。"
            />
          ) : (
            <>
              <section className="panel mb-7">
                <h2 className="flex items-center gap-2 mb-5">
                  <BookOpen size={19} />
                  已知事实
                </h2>
                <ol className="space-y-4">
                  {data.facts.map((fact, index) => (
                    <li key={index} className="leading-8">
                      {fact.text}
                      {refs([fact.source_id])}
                      <details className="text-xs text-muted mt-2">
                        <summary className="cursor-pointer">
                          核对原文依据（
                          {fact.quote_field === "title" ? "原标题" : "原文片段"}
                          ）
                        </summary>
                        <blockquote className="mt-2">{fact.quote}</blockquote>
                      </details>
                    </li>
                  ))}
                </ol>
              </section>
              <section className="mb-8">
                <div className="section-bar">
                  <h2 className="flex items-center gap-2">
                    <GitBranch size={19} />
                    可能发生什么影响
                  </h2>
                  <span className="text-xs text-muted">
                    有条件的推断，非确定结果
                  </span>
                </div>
                <div className="grid lg:grid-cols-2 gap-5">
                  {data.scenarios.map((scenario, index) => (
                    <article className="panel" key={index}>
                      <div className="flex gap-3 justify-between">
                        <span className="category-tag">
                          {scenario.direction === "risk"
                            ? "潜在风险"
                            : scenario.direction === "opportunity"
                              ? "潜在机会"
                              : "双向影响"}
                        </span>
                        <span className="tag">
                          依据支持：
                          {scenario.confidence === "medium" ? "一般" : "较弱"}
                        </span>
                      </div>
                      <h3 className="text-lg mt-4 mb-3">
                        {scenario.title}
                        {refs(scenario.source_ids)}
                      </h3>
                      <p className="leading-8">{scenario.impact}</p>
                      <p className="text-sm text-muted leading-7 mt-3">
                        作用路径：{scenario.mechanism}
                      </p>
                      <h4 className="text-sm mt-5 mb-2">成立条件</h4>
                      <ul className="list-disc pl-5 space-y-2 text-sm text-muted">
                        {scenario.conditions.map((condition) => (
                          <li key={condition}>{condition}</li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              </section>
              <section className="panel mb-7">
                <h2 className="flex items-center gap-2 mb-5">
                  <ListChecks size={19} />
                  现在怎么做更好
                </h2>
                <div className="grid lg:grid-cols-2 gap-5">
                  {data.actions.map((action, index) => (
                    <article
                      key={index}
                      className="border border-[var(--border)] rounded-xl p-5"
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <span className="tag">
                          {action.priority === "high"
                            ? "优先核对"
                            : action.priority === "medium"
                              ? "持续准备"
                              : "跟踪观察"}
                        </span>
                        <span className="text-xs text-muted">
                          {action.owner}
                        </span>
                      </div>
                      <h3 className="mb-3">
                        {action.title}
                        {refs(action.source_ids)}
                      </h3>
                      <p className="text-sm leading-7 text-muted">
                        {action.detail}
                      </p>
                    </article>
                  ))}
                </div>
              </section>
              <div className="grid lg:grid-cols-2 gap-5 mb-8">
                <section className="panel">
                  <h2 className="mb-4">下一步观察什么</h2>
                  <ul className="space-y-3 text-sm">
                    {data.watchlist.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </section>
                <section className="panel">
                  <h2 className="mb-4">判断边界与待补信息</h2>
                  <ul className="space-y-3 text-sm text-muted">
                    {data.limitations.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                  <p className="text-xs text-muted mt-4">
                    依据支持程度不是事件发生概率。
                  </p>
                </section>
              </div>
            </>
          )}
          <section>
            <div className="section-bar">
              <h2>研判来源</h2>
              <span className="text-xs text-muted">
                引用原始发布日期，保留可核对的原文
              </span>
            </div>
            <div className="policy-grid">
              {data.sources.map((source) => (
                <details
                  className="policy-card scroll-mt-24"
                  id={`research-source-${source.index}`}
                  key={source.article_id}
                >
                  <summary className="cursor-pointer leading-7">
                    [{source.index}] {source.title}
                  </summary>
                  <p className="text-xs text-muted my-3">
                    {source.source_name} · {date(source.published_at)}
                  </p>
                  <p className="text-sm leading-7">{source.snippet}</p>
                  <details className="text-xs text-muted my-3">
                    <summary className="cursor-pointer">展开原文片段</summary>
                    <blockquote className="mt-2 whitespace-pre-wrap">
                      {source.original_excerpt}
                    </blockquote>
                  </details>
                  <a
                    className="source-link mt-4"
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看原始来源 <ArrowUpRight size={12} />
                  </a>
                </details>
              ))}
            </div>
          </section>
        </>
      )}
      {!!archives.data?.length && (
        <section className="panel mt-10">
          <h2 className="mb-4">我的研判记录</h2>
          {restore.isError && <p role="alert">{restore.error.message}</p>}
          <div className="space-y-3">
            {archives.data.map((item) => (
              <button
                className="insight-row w-full text-left"
                key={item.id}
                onClick={() => restore.mutate(item.id)}
                disabled={restore.isPending}
              >
                <span>{item.focus}</span>
                <span className="text-xs text-muted">
                  {date(item.created_at)}{" "}
                  <RefreshCw size={12} className="inline" />
                </span>
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
