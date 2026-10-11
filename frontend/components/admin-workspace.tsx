"use client";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Edit3,
  Play,
  Trash2,
  Check,
  EyeOff,
  Activity,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "./section-heading";
import { Dialog } from "./ui/dialog";
import { OperationsTasks, SystemOverview } from "./operations-dashboard";
import { ErrorState, EmptyState, SkeletonCards } from "./ui/states";
import type { Article, Run, Source } from "@/types";
type Draft = {
  name: string;
  url: string;
  type: string;
  category: string;
  language: string;
  region: string;
  authority_score: number;
  fetch_interval: number;
  active: boolean;
  config: string;
};
const blank: Draft = {
  name: "",
  url: "",
  type: "rss",
  category: "news",
  language: "en",
  region: "",
  authority_score: 5,
  fetch_interval: 900,
  active: true,
  config: "{}",
};
const sourceBody = (s: Source) => ({
  name: s.name,
  url: s.url,
  type: s.type || "rss",
  category: s.category,
  language: s.language,
  region: s.region,
  authority_score: s.authority_score,
  fetch_interval: s.fetch_interval || 900,
  active: s.active ?? true,
  config_json: s.config_json || {},
});
export function AdminWorkspace() {
  const auth = useAuth();
  const { t } = usePreferences();
  const client = useQueryClient();
  const allowed = !!auth.token && !!auth.user?.is_admin;
  const [tab, setTab] = useState("sources");
  const [status, setStatus] = useState("processed");
  const [sourceFilter, setSourceFilter] = useState("");
  const [edit, setEdit] = useState<Source>();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(blank);
  const [validation, setValidation] = useState("");
  const [remove, setRemove] = useState<Source>();
  const [tagArticle, setTagArticle] = useState<Article>();
  const [tags, setTags] = useState("");
  const [taskId, setTaskId] = useState("");
  const [taskDraft, setTaskDraft] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const sources = useQuery({
    queryKey: ["admin-sources", auth.user?.id],
    queryFn: () => api<Source[]>("/admin/sources", {}, auth.token),
    enabled: allowed,
  });
  const articles = useQuery({
    queryKey: ["admin-articles", auth.user?.id, status],
    queryFn: () =>
      api<Article[]>(`/admin/articles?status=${status}`, {}, auth.token),
    enabled: allowed && (tab === "review" || tab === "tags"),
  });
  const runs = useQuery({
    queryKey: ["admin-runs", auth.user?.id],
    queryFn: () => api<Run[]>("/admin/runs", {}, auth.token),
    enabled: allowed && tab === "tasks",
    refetchInterval: allowed && tab === "tasks" ? 15000 : false,
  });
  const task = useQuery({
    queryKey: ["admin-task", auth.user?.id, taskId],
    queryFn: () =>
      api<{ task_id: string; state: string }>(
        `/admin/tasks/${encodeURIComponent(taskId)}`,
        {},
        auth.token,
      ),
    enabled: allowed && !!taskId,
    refetchInterval: allowed && !!taskId ? 5000 : false,
  });
  const mutation = useMutation({
    mutationFn: ({
      path,
      method,
      body,
    }: {
      path: string;
      method: string;
      body?: unknown;
    }) =>
      api<{ task_id?: string } | undefined>(
        path,
        {
          method,
          ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        },
        auth.token,
      ),
    onSuccess: (result) => {
      setSelected([]);
      if (result?.task_id) {
        setTaskId(result.task_id);
        setTaskDraft(result.task_id);
        setTab("tasks");
      }
      setOpen(false);
      setRemove(undefined);
      setTagArticle(undefined);
      for (const key of [
        "admin-sources",
        "admin-articles",
        "admin-runs",
        "admin-history",
        "admin-system",
        "facets",
        "feed",
        "articles",
        "hot",
        "hot-minerals",
        "policy-updates",
        "digest",
        "events",
        "article",
      ])
        client.invalidateQueries({ queryKey: [key] });
    },
  });
  function startEdit(s?: Source) {
    setEdit(s);
    setDraft(
      s
        ? {
            ...sourceBody(s),
            region: s.region || "",
            config: JSON.stringify(s.config_json || {}, null, 2),
          }
        : blank,
    );
    setValidation("");
    mutation.reset();
    setOpen(true);
  }
  if (!auth.user)
    return (
      <main className="small-page">
        <SectionHeading
          eyebrow="OPERATIONS"
          zh="管理后台"
          en="Operations"
          description="登录管理员账号管理信源与审核。"
          descriptionEn="Sign in as an administrator to manage sources and reviews."
        />
        <Link className="btn" href="/login">
          {t("管理员登录", "Administrator sign in")}
        </Link>
      </main>
    );
  if (!allowed)
    return (
      <main className="small-page">
        <h1>{t("需要管理员权限", "Administrator access required")}</h1>
        <p className="subtitle">
          {t(
            "当前账号无权访问运营数据。",
            "This account cannot access operational data.",
          )}
        </p>
      </main>
    );
  const shown = sources.data?.filter((s) =>
    `${s.name} ${s.category} ${s.region || ""}`
      .toLowerCase()
      .includes(sourceFilter.toLowerCase()),
  );
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="INTELLIGENCE OPERATIONS"
        zh="信源、审核与任务。"
        en="Sources, reviews and operations."
        description="管理可信输入，检查加工结果，追踪真实任务状态。"
        descriptionEn="Manage trusted inputs, review processing and monitor actual task states."
        actions={<span className="category-tag">{auth.user.email}</span>}
      />
      <SystemOverview />
      <div
        className="tabs mb-6"
        role="tablist"
        aria-label={t("管理模块", "Administration module")}
      >
        {[
          ["sources", "信源管理", "Sources"],
          ["review", "文章审核", "Review"],
          ["tags", "标签管理", "Tags"],
          ["tasks", "任务监控", "Tasks"],
        ].map(([key, zh, en]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "active" : ""}
            onClick={() => {
              setTab(key);
              mutation.reset();
            }}
          >
            {t(zh, en)}
          </button>
        ))}
      </div>
      {mutation.isError && <ErrorState error={mutation.error} />}{" "}
      {mutation.isSuccess && (
        <p className="success-notice mb-4" role="status">
          {t("操作已完成。", "Operation completed.")}
        </p>
      )}
      {tab === "sources" && (
        <>
          <div className="filter-panel flex gap-4 mb-5">
            <input
              aria-label={t("筛选信源", "Filter sources")}
              placeholder={t(
                "查找名称、类别或地区…",
                "Find source, category or region…",
              )}
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            />
            <button className="btn shrink-0" onClick={() => startEdit()}>
              <Plus size={15} />
              {t("添加信源", "Add source")}
            </button>
          </div>
          {sources.isError ? (
            <ErrorState error={sources.error} />
          ) : sources.isPending ? (
            <SkeletonCards />
          ) : (
            <div className="table-scroll">
              <table className="admin-table">
                <thead>
                  <tr>
                    {[
                      t("信源 / 地址", "Source / URL"),
                      t("类型 / 语言", "Type / language"),
                      t("权威性", "Authority"),
                      t("状态", "Status"),
                      t("操作", "Actions"),
                    ].map((h) => (
                      <th key={h} scope="col">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {shown?.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <strong>{s.name}</strong>
                        <a
                          className="block text-xs text-muted truncate max-w-xs mt-1"
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {s.url}
                        </a>
                      </td>
                      <td>
                        {s.type} · {s.language}
                        <small className="block text-muted">
                          {s.category} · {s.fetch_interval}s
                        </small>
                      </td>
                      <td>{s.authority_score}/10</td>
                      <td>
                        <span
                          className={`status-pill ${s.active ? "text-green" : "text-muted"}`}
                        >
                          {s.active ? t("启用", "Active") : t("停用", "Paused")}
                        </span>
                      </td>
                      <td>
                        <div className="flex gap-1">
                          <button
                            className="icon-button"
                            aria-label={`${t("编辑", "Edit")} ${s.name}`}
                            onClick={() => startEdit(s)}
                          >
                            <Edit3 size={14} />
                          </button>
                          <button
                            className="icon-button"
                            disabled={mutation.isPending || !s.active}
                            aria-label={`${t("测试采集", "Test fetch")} ${s.name}`}
                            onClick={() =>
                              mutation.mutate({
                                path: `/admin/sources/${s.id}/fetch`,
                                method: "POST",
                              })
                            }
                          >
                            <Play size={14} />
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            disabled={mutation.isPending}
                            onClick={() =>
                              mutation.mutate({
                                path: `/admin/sources/${s.id}`,
                                method: "PUT",
                                body: { ...sourceBody(s), active: !s.active },
                              })
                            }
                          >
                            {s.active
                              ? t("停用", "Pause")
                              : t("启用", "Enable")}
                          </button>
                          <button
                            className="icon-button"
                            aria-label={`${t("删除", "Delete")} ${s.name}`}
                            onClick={() => setRemove(s)}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      {(tab === "review" || tab === "tags") && (
        <>
          <div className="section-bar">
            <h2>
              {tab === "review"
                ? t("发布队列", "Publishing queue")
                : t("文章标签", "Article tags")}
            </h2>
            <select
              aria-label={t("审核状态", "Review status")}
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setSelected([]);
              }}
            >
              <option value="processed">
                {t("待审核", "Ready for review")}
              </option>
              <option value="pending">
                {t("待加工", "Pending processing")}
              </option>
              <option value="published">{t("已发布", "Published")}</option>
            </select>
          </div>
          {tab === "review" && (
            <div className="filter-panel flex flex-wrap items-center gap-3 mb-5">
              <button
                className="btn btn-outline btn-sm"
                onClick={() =>
                  setSelected(
                    selected.length
                      ? []
                      : articles.data?.map((article) => article.id) || [],
                  )
                }
              >
                {selected.length
                  ? t("清除选择", "Clear selection")
                  : t("选择全部", "Select all")}
              </button>
              <span className="text-sm text-muted">
                {t("已选择", "Selected")} {selected.length}
              </span>
              {(
                [
                  ["publish", "批量发布", "Publish selected"],
                  ["hide", "批量隐藏", "Withdraw selected"],
                  ["reprocess", "重新加工", "Reprocess selected"],
                ] as const
              ).map(([action, zh, en]) => (
                <button
                  key={action}
                  className="btn btn-outline btn-sm"
                  disabled={
                    !selected.length ||
                    mutation.isPending ||
                    ((action === "publish" || action === "hide") &&
                      status === "pending")
                  }
                  onClick={() =>
                    mutation.mutate({
                      path: "/admin/articles/batch",
                      method: "POST",
                      body: { article_ids: selected, action },
                    })
                  }
                >
                  {t(zh, en)}
                </button>
              ))}
            </div>
          )}
          {articles.isError ? (
            <ErrorState error={articles.error} />
          ) : articles.isPending ? (
            <SkeletonCards />
          ) : articles.data?.length ? (
            articles.data.map((a) => (
              <article className="article-card" key={a.id}>
                {tab === "review" && (
                  <label className="flex items-center gap-2 mb-3 text-sm text-muted">
                    <input
                      type="checkbox"
                      aria-label={`${t("选择文章", "Select article")} ${a.title_zh || a.title}`}
                      checked={selected.includes(a.id)}
                      onChange={(event) =>
                        setSelected((values) =>
                          event.target.checked
                            ? [...values, a.id]
                            : values.filter((value) => value !== a.id),
                        )
                      }
                    />
                    {t("选择文章", "Select article")}
                  </label>
                )}
                <div className="article-meta">
                  <span>{a.source_name}</span>
                  <span>{a.status}</span>
                  <span>
                    {t("质量", "Quality")} {a.quality_score.toFixed(0)}
                  </span>
                </div>
                <h3>{a.title_zh || a.title}</h3>
                <p className="article-summary">{a.summary_zh || a.summary}</p>
                <div className="article-tags mb-4">
                  {a.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
                <div className="flex flex-wrap gap-3">
                  <a
                    className="btn btn-outline btn-sm"
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("核验原文", "Verify source")}
                  </a>
                  {a.status === "pending" ? (
                    <button
                      className="btn btn-outline btn-sm"
                      disabled={mutation.isPending}
                      onClick={() =>
                        mutation.mutate({
                          path: `/admin/articles/${a.id}/retry`,
                          method: "POST",
                        })
                      }
                    >
                      {t("重新加工", "Retry processing")}
                    </button>
                  ) : (
                    <>
                      <button
                        className="btn btn-outline btn-sm"
                        disabled={mutation.isPending}
                        onClick={() => {
                          setTagArticle(a);
                          setTags(a.tags.join("，"));
                          mutation.reset();
                        }}
                      >
                        <Edit3 size={12} />
                        {t("编辑标签", "Edit tags")}
                      </button>
                      <button
                        className="btn btn-sm"
                        disabled={mutation.isPending}
                        onClick={() =>
                          mutation.mutate({
                            path: `/admin/articles/${a.id}`,
                            method: "PATCH",
                            body: {
                              status:
                                a.status === "published"
                                  ? "processed"
                                  : "published",
                            },
                          })
                        }
                      >
                        {a.status === "published" ? (
                          <EyeOff size={13} />
                        ) : (
                          <Check size={13} />
                        )}{" "}
                        {a.status === "published"
                          ? t("隐藏文章", "Withdraw")
                          : t("发布文章", "Publish")}
                      </button>
                    </>
                  )}
                </div>
              </article>
            ))
          ) : (
            <EmptyState title={t("当前队列为空", "The queue is empty")} />
          )}
        </>
      )}
      {tab === "tasks" && (
        <>
          <OperationsTasks />
          <div className="panel mb-6">
            <h2 className="flex items-center gap-2 mb-4">
              <Activity size={18} />
              {t("Celery 任务状态", "Celery task status")}
            </h2>
            <form
              className="flex gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                setTaskId(taskDraft.trim());
              }}
            >
              <input
                aria-label={t("任务 ID", "Task ID")}
                value={taskDraft}
                onChange={(e) => setTaskDraft(e.target.value)}
                maxLength={100}
                required
                placeholder={t("粘贴任务 ID", "Paste a task ID")}
              />
              <button className="btn btn-outline shrink-0">
                {t("查询", "Check")}
              </button>
            </form>
            {task.isError ? (
              <ErrorState error={task.error} />
            ) : (
              task.data && (
                <p className="mt-4 text-sm">
                  <code>{task.data.task_id}</code>
                  <strong className="text-accent ml-4">
                    {task.data.state}
                  </strong>
                </p>
              )
            )}
            <p className="text-xs text-muted mt-3">
              {t(
                "状态每 5 秒更新。PENDING 表示尚未执行或结果未记录，请检查 Worker。",
                "Updates every 5 seconds. PENDING means unstarted or no recorded result; check the worker.",
              )}
            </p>
          </div>
          <div className="section-bar">
            <h2>{t("采集运行记录", "Ingestion runs")}</h2>
            <span className="text-xs text-muted">
              {t("每 15 秒刷新", "Refreshes every 15 seconds")}
            </span>
          </div>
          {runs.isError ? (
            <ErrorState error={runs.error} />
          ) : runs.isPending ? (
            <SkeletonCards />
          ) : runs.data?.length ? (
            <div className="table-scroll">
              <table className="admin-table">
                <thead>
                  <tr>
                    {[
                      t("时间", "Time"),
                      t("状态", "Status"),
                      t("采集", "Fetched"),
                      t("新增", "New"),
                      t("重复", "Duplicate"),
                      t("错误", "Errors"),
                    ].map((x) => (
                      <th key={x} scope="col">
                        {x}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {runs.data.map((r) => (
                    <tr key={r.id}>
                      <td>{new Date(r.created_at).toLocaleString()}</td>
                      <td>
                        {r.status}
                        {r.error && (
                          <p className="text-red text-xs max-w-sm">{r.error}</p>
                        )}
                      </td>
                      <td>{r.fetched_count}</td>
                      <td>{r.new_count}</td>
                      <td>{r.duplicate_count}</td>
                      <td>{r.error_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState />
          )}
        </>
      )}
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={
          edit ? t("编辑信源", "Edit source") : t("添加信源", "Add source")
        }
        description={t(
          "设置采集地址、权威性与解析参数。",
          "Configure the source URL, authority and parser options.",
        )}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            try {
              const parsed: unknown = JSON.parse(draft.config);
              if (
                typeof parsed !== "object" ||
                parsed === null ||
                Array.isArray(parsed)
              )
                throw new Error();
              setValidation("");
              const { config, ...values } = draft;
              mutation.mutate({
                path: edit ? `/admin/sources/${edit.id}` : "/admin/sources",
                method: edit ? "PUT" : "POST",
                body: {
                  ...values,
                  region: draft.region || null,
                  config_json: parsed,
                },
              });
            } catch {
              setValidation(
                t(
                  "采集配置必须是有效的 JSON 对象。",
                  "Parser configuration must be a valid JSON object.",
                ),
              );
            }
          }}
          className="source-form"
        >
          <label htmlFor="source-name">{t("名称", "Name")}</label>
          <input
            id="source-name"
            required
            maxLength={200}
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <label htmlFor="source-url">{t("公网 URL", "Public URL")}</label>
          <input
            id="source-url"
            type="url"
            required
            value={draft.url}
            onChange={(e) => setDraft({ ...draft, url: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-3 mt-3">
            {(
              [
                ["type", ["rss", "web", "api"], "类型", "Type"],
                [
                  "category",
                  ["news", "price", "policy", "report", "company"],
                  "类别",
                  "Category",
                ],
              ] as const
            ).map(([key, options, zh, en]) => (
              <label key={key}>
                {t(zh, en)}
                <select
                  value={draft[key]}
                  onChange={(e) =>
                    setDraft({ ...draft, [key]: e.target.value })
                  }
                >
                  {options.map((o) => (
                    <option key={o}>{o}</option>
                  ))}
                </select>
              </label>
            ))}
            <label>
              {t("语言", "Language")}
              <input
                required
                value={draft.language}
                maxLength={20}
                onChange={(e) =>
                  setDraft({ ...draft, language: e.target.value })
                }
              />
            </label>
            <label>
              {t("地区", "Region")}
              <input
                value={draft.region}
                maxLength={100}
                onChange={(e) => setDraft({ ...draft, region: e.target.value })}
              />
            </label>
            <label>
              {t("权威性 1–10", "Authority 1–10")}
              <input
                type="number"
                min={1}
                max={10}
                value={draft.authority_score}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    authority_score: Number(e.target.value),
                  })
                }
              />
            </label>
            <label>
              {t("间隔（秒）", "Interval (seconds)")}
              <input
                type="number"
                min={60}
                max={604800}
                value={draft.fetch_interval}
                onChange={(e) =>
                  setDraft({ ...draft, fetch_interval: Number(e.target.value) })
                }
              />
            </label>
          </div>
          <label htmlFor="source-config" className="mt-4">
            {t("解析配置 JSON", "Parser configuration JSON")}
          </label>
          <textarea
            id="source-config"
            rows={4}
            value={draft.config}
            onChange={(e) => setDraft({ ...draft, config: e.target.value })}
          />
          {validation && (
            <p className="text-red mt-3" role="alert">
              {validation}
            </p>
          )}
          {mutation.isError && <ErrorState error={mutation.error} />}
          <button className="btn mt-5" disabled={mutation.isPending}>
            {t("保存信源", "Save source")}
          </button>
        </form>
      </Dialog>
      <Dialog
        open={!!remove}
        onOpenChange={(o) => !o && setRemove(undefined)}
        title={t("删除信源", "Delete source")}
        description={t(
          "已有文章的信源会保留，请改用停用。",
          "Sources referenced by articles are retained; pause them instead.",
        )}
      >
        <p>{remove?.name}</p>
        {mutation.isError && <ErrorState error={mutation.error} />}
        <button
          className="btn btn-outline mt-5"
          disabled={mutation.isPending}
          onClick={() =>
            remove &&
            mutation.mutate({
              path: `/admin/sources/${remove.id}`,
              method: "DELETE",
            })
          }
        >
          <Trash2 size={14} />
          {t("确认删除", "Confirm delete")}
        </button>
      </Dialog>
      <Dialog
        open={!!tagArticle}
        onOpenChange={(o) => !o && setTagArticle(undefined)}
        title={t("编辑文章标签", "Edit article tags")}
        description={t(
          "使用逗号分隔，保留当前发布状态。",
          "Comma-separated tags; the publication state is preserved.",
        )}
      >
        <label htmlFor="article-tags">{t("标签", "Tags")}</label>
        <input
          id="article-tags"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
        />
        {mutation.isError && <ErrorState error={mutation.error} />}
        <button
          className="btn mt-5"
          disabled={mutation.isPending}
          onClick={() =>
            tagArticle &&
            mutation.mutate({
              path: `/admin/articles/${tagArticle.id}`,
              method: "PATCH",
              body: {
                status: tagArticle.status,
                tags: tags
                  .split(/[,，]/)
                  .map((x) => x.trim())
                  .filter(Boolean),
              },
            })
          }
        >
          {t("保存标签", "Save tags")}
        </button>
      </Dialog>
    </main>
  );
}
