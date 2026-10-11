"use client";
import { useState } from "react";
import Link from "next/link";
import { Check } from "lucide-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import type { Facets } from "@/types";
export function SubscriptionDialogContent({
  mineral,
  region,
  onClose,
}: {
  mineral?: string;
  region?: string;
  onClose: () => void;
}) {
  const { t } = usePreferences();
  const auth = useAuth();
  const open = true;
  const setOpen = (value: boolean) => {
    if (!value) onClose();
  };
  const [minerals, setMinerals] = useState<string[]>(mineral ? [mineral] : []);
  const [regions, setRegions] = useState<string[]>(region ? [region] : []);
  const [frequency, setFrequency] = useState("weekly");
  const [email, setEmail] = useState(false);
  const [priceAlerts, setPriceAlerts] = useState(false);
  const facets = useQuery({
    queryKey: ["facets"],
    queryFn: () => publicApi<Facets>("/facets"),
    enabled: open,
  });
  const save = useMutation({
    mutationFn: () =>
      publicApi(
        "/subscriptions",
        {
          method: "POST",
          body: JSON.stringify({
            email: auth.user?.email,
            subscribed_minerals: minerals,
            subscribed_regions: regions,
            frequency,
            email_enabled: email,
            price_alerts_enabled: email && priceAlerts,
          }),
        },
        auth.token,
      ),
  });
  const toggle = (
    name: string,
    values: string[],
    set: (values: string[]) => void,
  ) =>
    set(
      values.includes(name)
        ? values.filter((v) => v !== name)
        : [...values, name].slice(0, 20),
    );
  return (
    <>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={t("让重要动向找到你", "Keep your intelligence close")}
        description={t(
          "选择关注的矿种和地区，汇成你的专属情报。",
          "Follow commodities and regions that matter to your work.",
        )}
      >
        {save.isSuccess ? (
          <div className="empty">
            <Check className="mx-auto text-primary mb-3" />
            {t("订阅偏好已保存", "Preferences saved")}
            <Link
              className="source-link block mt-3"
              href="/subscriptions"
              onClick={() => setOpen(false)}
            >
              {t("查看我的订阅", "View subscriptions")}
            </Link>
          </div>
        ) : (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (auth.user) save.mutate();
            }}
          >
            <label className="field-label">
              {t("关注矿种", "Commodities")}
            </label>
            <div className="chips mb-4">
              {(facets.data?.minerals || []).map((item) => (
                <button
                  type="button"
                  className={`chip ${minerals.includes(item.name) ? "selected" : ""}`}
                  aria-pressed={minerals.includes(item.name)}
                  key={item.name}
                  onClick={() => toggle(item.name, minerals, setMinerals)}
                >
                  {item.name}
                </button>
              ))}
            </div>
            <label className="field-label">{t("关注地区", "Regions")}</label>
            <div className="chips mb-4">
              {(facets.data?.regions || []).map((item) => (
                <button
                  type="button"
                  className={`chip ${regions.includes(item.name) ? "selected" : ""}`}
                  aria-pressed={regions.includes(item.name)}
                  key={item.name}
                  onClick={() => toggle(item.name, regions, setRegions)}
                >
                  {item.name}
                </button>
              ))}
            </div>
            <label className="field-label" htmlFor="subscription-email">
              {t("电子邮箱", "Email address")}
            </label>
            <input
              className="w-full"
              id="subscription-email"
              type="email"
              value={auth.user?.email || ""}
              readOnly
              placeholder={t(
                "登录后使用账户邮箱",
                "Sign in to use your account email",
              )}
            />
            <label
              className="field-label mt-4"
              htmlFor="subscription-frequency"
            >
              {t("汇总频率", "Digest frequency")}
            </label>
            <select
              id="subscription-frequency"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="w-full"
            >
              <option value="daily">{t("每日", "Daily")}</option>
              <option value="weekly">{t("每周", "Weekly")}</option>
            </select>
            <label className="flex items-center gap-2 my-4">
              <input
                type="checkbox"
                checked={email}
                onChange={(e) => setEmail(e.target.checked)}
              />
              {t("同时接收邮件简报", "Receive email digests")}
            </label>
            <label className="flex gap-3 items-center text-sm">
              <input
                type="checkbox"
                checked={priceAlerts}
                disabled={!email}
                onChange={(e) => setPriceAlerts(e.target.checked)}
              />
              {t(
                "接收订阅矿种的价格预警邮件",
                "Email price warnings for subscribed minerals",
              )}
            </label>
            {save.isError && (
              <p className="error" role="alert">
                {save.error.message}
              </p>
            )}
            {!auth.user ? (
              <Button asChild className="w-full">
                <Link href="/login" onClick={() => setOpen(false)}>
                  {t("登录并订阅", "Sign in to subscribe")}
                </Link>
              </Button>
            ) : (
              <Button className="w-full" disabled={save.isPending}>
                {t(
                  save.isPending ? "正在保存…" : "保存订阅",
                  save.isPending ? "Saving…" : "Save subscription",
                )}
              </Button>
            )}
          </form>
        )}
      </Dialog>
    </>
  );
}
