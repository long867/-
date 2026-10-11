"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { ErrorState, EmptyState, SkeletonCards } from "./ui/states";

type System = {
  articles_total: number;
  articles_published: number;
  articles_today: number;
  chat_total: number;
  chat_today: number;
  error_rate_5m: number;
  requests_5m: number;
  active_sources: number;
  failing_sources: number;
  pending_articles: number;
  workers: string[];
  beat_alive: boolean;
  queues: Record<string, number>;
};
type Task = {
  task_id: string;
  name: string;
  state: string;
  retries: number;
  updated_at: string;
  duration_seconds?: number;
  error_type?: string;
  worker?: string;
};
type TaskPage = {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
};

export function SystemOverview() {
  const auth = useAuth();
  const { t } = usePreferences();
  const query = useQuery({
    queryKey: ["admin-system", auth.user?.id],
    queryFn: () => api<System>("/admin/system", {}, auth.token),
    enabled: !!auth.token && !!auth.user?.is_admin,
    refetchInterval: 15000,
  });
  if (query.isError) return <ErrorState error={query.error} />;
  if (!query.data) return <SkeletonCards count={2} />;
  const data = query.data;
  const cards = [
    [
      t("文章总数", "Total articles"),
      data.articles_total,
      `${t("已发布", "Published")} ${data.articles_published}`,
    ],
    [
      t("今日新增", "New today"),
      data.articles_today,
      `${t("待加工", "Pending")} ${data.pending_articles}`,
    ],
    [
      t("今日问答", "Chats today"),
      data.chat_today,
      `${t("累计", "Total")} ${data.chat_total}`,
    ],
    [
      t("近五分钟错误率", "5-minute error rate"),
      `${(data.error_rate_5m * 100).toFixed(1)}%`,
      `${data.requests_5m} ${t("请求", "requests")}`,
    ],
  ];
  return (
    <section aria-label={t("系统指标", "System metrics")} className="mb-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(([label, value, note]) => (
          <div className="panel" key={label}>
            <p className="text-sm text-muted">{label}</p>
            <strong className="block text-3xl my-3">{value}</strong>
            <p className="text-xs text-muted">{note}</p>
          </div>
        ))}
      </div>
      <p className="text-sm text-muted mt-4" role="status">
        Worker: {data.workers.length || t("未发现心跳", "No heartbeat")} · Beat:{" "}
        {data.beat_alive
          ? t("运行中", "Running")
          : t("未发现心跳", "No heartbeat")}{" "}
        · {t("活跃信源", "Active sources")} {data.active_sources} ·{" "}
        {t("连续失败信源", "Failing sources")} {data.failing_sources}
      </p>
      <p className="text-xs text-muted mt-2">
        {t("队列待执行", "Queued work")}:{" "}
        {Object.entries(data.queues)
          .map(([key, count]) => `${key} ${count}`)
          .join(" · ")}
      </p>
    </section>
  );
}

export function OperationsTasks() {
  const auth = useAuth();
  const { t } = usePreferences();
  const [page, setPage] = useState(1);
  const [state, setState] = useState("");
  const tasks = useQuery({
    queryKey: ["admin-history", auth.user?.id, page, state],
    queryFn: () =>
      api<TaskPage>(
        `/admin/tasks?page=${page}&page_size=20${state ? `&state=${state}` : ""}`,
        {},
        auth.token,
      ),
    enabled: !!auth.token && !!auth.user?.is_admin,
    refetchInterval: 15000,
  });
  const schedules = useQuery({
    queryKey: ["admin-schedule", auth.user?.id],
    queryFn: () =>
      api<{ name: string; task: string; schedule: string; timezone: string }[]>(
        "/admin/schedule",
        {},
        auth.token,
      ),
    enabled: !!auth.token && !!auth.user?.is_admin,
    staleTime: 300000,
  });
  return (
    <section className="mb-8" aria-label={t("任务历史", "Task history")}>
      <div className="section-bar">
        <h2>{t("全部任务历史", "All task history")}</h2>
        <select
          aria-label={t("任务状态筛选", "Task state filter")}
          value={state}
          onChange={(event) => {
            setState(event.target.value);
            setPage(1);
          }}
        >
          <option value="">{t("全部状态", "All states")}</option>
          {["QUEUED", "STARTED", "RETRY", "SUCCESS", "FAILURE", "REVOKED"].map(
            (value) => (
              <option key={value}>{value}</option>
            ),
          )}
        </select>
      </div>
      {tasks.isError ? (
        <ErrorState error={tasks.error} />
      ) : tasks.isPending ? (
        <SkeletonCards />
      ) : !tasks.data?.items.length ? (
        <EmptyState title={t("暂无任务记录", "No task records")} />
      ) : (
        <>
          <div className="table-scroll">
            <table className="admin-table">
              <thead>
                <tr>
                  {[
                    t("更新时间", "Updated"),
                    t("任务 / ID", "Task / ID"),
                    t("状态", "State"),
                    t("重试", "Retries"),
                    t("耗时", "Duration"),
                    t("错误类型", "Error type"),
                  ].map((label) => (
                    <th scope="col" key={label}>
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tasks.data.items.map((task) => (
                  <tr key={task.task_id}>
                    <td>{new Date(task.updated_at).toLocaleString()}</td>
                    <td>
                      <strong>{task.name.replace("miningintel.", "")}</strong>
                      <code className="block text-xs text-muted mt-1">
                        {task.task_id}
                      </code>
                    </td>
                    <td
                      className={
                        task.state === "FAILURE"
                          ? "text-red"
                          : task.state === "SUCCESS"
                            ? "text-green"
                            : "text-accent"
                      }
                    >
                      {task.state}
                    </td>
                    <td>{task.retries}</td>
                    <td>
                      {task.duration_seconds == null
                        ? "—"
                        : `${Number(task.duration_seconds).toFixed(2)}s`}
                    </td>
                    <td>{task.error_type || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-4">
            <button
              className="btn btn-outline btn-sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              {t("上一页", "Previous")}
            </button>
            <span className="text-sm text-muted">
              {page} · {tasks.data.total} {t("条记录", "records")}
            </span>
            <button
              className="btn btn-outline btn-sm"
              disabled={page * 20 >= tasks.data.total}
              onClick={() => setPage(page + 1)}
            >
              {t("下一页", "Next")}
            </button>
          </div>
        </>
      )}
      <details className="panel mt-6">
        <summary className="cursor-pointer">
          {t("定时任务配置（上海时区）", "Scheduled tasks (Shanghai time)")}
        </summary>
        {schedules.isError ? (
          <ErrorState error={schedules.error} />
        ) : (
          <ul className="mt-4 space-y-3 text-sm">
            {schedules.data?.map((item) => (
              <li key={item.name}>
                <strong>{item.name}</strong>
                <span className="block text-xs text-muted">
                  {item.task} · {item.schedule} · {item.timezone}
                </span>
              </li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}
