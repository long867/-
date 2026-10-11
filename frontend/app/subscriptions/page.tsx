"use client";
import Link from "next/link";
import { usePreferences } from "@/hooks/use-preferences";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, publicApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { ArticleCard } from "@/components/article-card";
import type { Article, Subscription } from "@/types";
export default function Subscriptions() {
  const auth = useAuth();
  const { t } = usePreferences();
  const client = useQueryClient();
  const [minerals, setMinerals] = useState("");
  const [regions, setRegions] = useState("");
  const [frequency, setFrequency] = useState("daily");
  const [emailEnabled, setEmailEnabled] = useState(false);
  const subscription = useQuery({
    queryKey: ["subscription", auth.user?.id],
    queryFn: () =>
      api<Subscription | null>("/subscriptions/me", {}, auth.token),
    enabled: !!auth.token,
  });
  const feed = useQuery({
    queryKey: ["subscribed-feed", auth.user?.id],
    queryFn: () => api<Article[]>("/subscriptions/feed", {}, auth.token),
    enabled: !!auth.token,
  });
  useEffect(() => {
    setMinerals(subscription.data?.subscribed_minerals.join("，") || "");
    setRegions(subscription.data?.subscribed_regions.join("，") || "");
    setFrequency(subscription.data?.frequency || "daily");
    setEmailEnabled(subscription.data?.email_enabled || false);
  }, [subscription.data, auth.user?.id]);
  const mutation = useMutation({
    mutationFn: () =>
      publicApi<Subscription>(
        "/subscriptions",
        {
          method: "POST",
          body: JSON.stringify({
            subscribed_minerals: minerals
              .split(/[,，]/)
              .map((item) => item.trim())
              .filter(Boolean),
            subscribed_regions: regions
              .split(/[,，]/)
              .map((item) => item.trim())
              .filter(Boolean),
            frequency,
            email: auth.user?.email,
            email_enabled: emailEnabled,
          }),
        },
        auth.token,
      ),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["subscription", auth.user?.id] });
      client.invalidateQueries({
        queryKey: ["subscribed-feed", auth.user?.id],
      });
    },
  });
  if (!auth.user)
    return (
      <main className="small-page">
        <h1>{t("订阅你的矿产领域", "Subscribe to your mineral interests")}</h1>
        <p className="subtitle mb-5">
          {t(
            "登录后保存关注矿种与地区。",
            "Sign in to save minerals and regions of interest.",
          )}
        </p>
        <Button asChild>
          <Link href="/login">{t("登录 / 注册", "Sign in / Register")}</Link>
        </Button>
      </main>
    );
  return (
    <main className="small-page">
      <div className="eyebrow">PERSONAL INTELLIGENCE FEED</div>
      <h1>{t("我的订阅", "My subscriptions")}</h1>
      <p className="subtitle mb-6">
        {t(
          "按矿种与地区生成站内关注流。多个矿种或地区分别取并集，两组条件取交集。",
          "Your reading feed matches any selected mineral and any selected region.",
        )}
      </p>
      <form
        className="form-card mb-8"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label htmlFor="minerals">
          {t(
            "关注矿种（逗号分隔；留空表示全部）",
            "Minerals (comma-separated; blank for all)",
          )}
        </label>
        <input
          id="minerals"
          placeholder="铜，锂，稀土"
          value={minerals}
          onChange={(event) => setMinerals(event.target.value)}
        />
        <label htmlFor="regions">
          {t(
            "关注地区（逗号分隔；留空表示全部）",
            "Regions (comma-separated; blank for all)",
          )}
        </label>
        <input
          id="regions"
          placeholder="澳大利亚，智利"
          value={regions}
          onChange={(event) => setRegions(event.target.value)}
        />
        <label htmlFor="frequency">
          {t("简报频率偏好", "Digest frequency")}
        </label>
        <select
          id="frequency"
          value={frequency}
          onChange={(event) => setFrequency(event.target.value)}
        >
          <option value="daily">{t("每日", "Daily")}</option>
          <option value="weekly">{t("每周", "Weekly")}</option>
        </select>
        <label className="flex gap-3 items-center mt-4">
          <input
            type="checkbox"
            checked={emailEnabled}
            onChange={(event) => setEmailEnabled(event.target.checked)}
          />
          {t("同时接收邮件简报", "Receive email digests")}
        </label>
        <p className="text-xs text-muted">
          {t(
            "邮件服务启用后，按所选频率发送匹配的已发布资讯。",
            "When mail delivery is configured, receive matching published coverage at this frequency.",
          )}
        </p>
        <Button
          className="mt-6"
          disabled={mutation.isPending || subscription.isPending}
        >
          {t("保存偏好", "Save preferences")}
        </Button>
        {mutation.isSuccess && (
          <p className="text-primary mt-3">
            {t("已保存，关注流已更新。", "Saved. Your feed is updated.")}
          </p>
        )}
        {(mutation.isError || subscription.isError) && (
          <p role="alert" className="text-red-700 mt-3">
            {mutation.error?.message || subscription.error?.message}
          </p>
        )}
      </form>
      <h2 className="mb-5">{t("关注资讯", "Following")}</h2>
      {feed.isPending ? (
        <p>{t("正在加载…", "Loading…")}</p>
      ) : feed.isError ? (
        <p role="alert">{feed.error.message}</p>
      ) : feed.data?.length ? (
        feed.data.map((article) => (
          <ArticleCard key={article.id} article={article} />
        ))
      ) : (
        <div className="empty">
          {t(
            "暂无符合关注偏好的资讯。",
            "No coverage matches your interests yet.",
          )}
        </div>
      )}
    </main>
  );
}
