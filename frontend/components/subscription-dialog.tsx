"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import { Bell } from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
const Content = dynamic(
  () =>
    import("./subscription-dialog-content").then(
      (x) => x.SubscriptionDialogContent,
    ),
  { ssr: false },
);

export function SubscriptionDialog({
  mineral,
  region,
  compact = false,
}: {
  mineral?: string;
  region?: string;
  compact?: boolean;
}) {
  const { t } = usePreferences();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className={`btn ${compact ? "btn-ghost" : "btn-primary"} h-8 px-3`}
        onClick={() => setOpen(true)}
      >
        <Bell size={14} />
        {t("订阅情报", "Follow intelligence")}
      </button>
      {open && (
        <Content
          mineral={mineral}
          region={region}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
