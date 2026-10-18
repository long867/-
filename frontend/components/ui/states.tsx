"use client";
import { RefreshCw, FileSearch } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <div
      className="skeleton-stream"
      aria-label="正在加载 / Loading"
      aria-busy="true"
    >
      {Array.from({ length: count }, (_, i) => (
        <div className="skeleton-card" key={i}>
          <div className="skeleton w-1/4 h-3" />
          <div className="skeleton w-4/5 h-5 mt-5" />
          <div className="skeleton w-full h-3 mt-4" />
          <div className="skeleton w-2/3 h-3 mt-3" />
        </div>
      ))}
    </div>
  );
}
export function EmptyState({
  title,
  detail,
}: {
  title?: string;
  detail?: string;
}) {
  const { t } = usePreferences();
  return (
    <div className="empty">
      <FileSearch size={26} className="mx-auto mb-3 text-muted" />
      <strong>
        {title || t("暂时没有相关资料", "No matching evidence yet")}
      </strong>
      <p>
        {detail ||
          t(
            "调整筛选条件，或稍后查看新的已发布资讯。",
            "Adjust your filters or check back for newly published intelligence.",
          )}
      </p>
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  const { t } = usePreferences();
  return (
    <div className="error" role="alert">
      <p>{error.message}</p>
      {retry && (
        <button className="inline-flex items-center gap-2 mt-3" onClick={retry}>
          <RefreshCw size={14} />
          {t("重试", "Try again")}
        </button>
      )}
    </div>
  );
}
