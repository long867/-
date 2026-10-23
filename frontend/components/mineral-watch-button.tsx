"use client";

import { Star } from "lucide-react";
import { useMineralWatchlist } from "@/hooks/use-mineral-watchlist";
import { usePreferences } from "@/hooks/use-preferences";

export function MineralWatchButton({
  name,
  label = false,
}: {
  name: string;
  label?: boolean;
}) {
  const { names, ready, toggle } = useMineralWatchlist();
  const { t } = usePreferences();
  const followed = names.includes(name);
  const full = names.length >= 12 && !followed;
  return (
    <button
      type="button"
      className={`mineral-watch-button ${followed ? "is-watched" : ""}`}
      aria-pressed={followed}
      disabled={!ready || full}
      aria-label={
        full
          ? t("观察清单已满，最多 12 项", "Watchlist full, up to 12 minerals")
          : followed
            ? t(`取消关注${name}`, `Unfollow ${name}`)
            : t(`关注${name}`, `Follow ${name}`)
      }
      title={
        full
          ? t("最多关注 12 个矿种", "Follow up to 12 minerals")
          : t("保存在此浏览器的观察清单", "Saved in this browser's watchlist")
      }
      onClick={() => toggle(name)}
    >
      <Star size={15} fill={followed ? "currentColor" : "none"} />
      {label && (
        <span>
          {followed ? t("已关注", "Following") : t("加入观察", "Follow")}
        </span>
      )}
    </button>
  );
}
