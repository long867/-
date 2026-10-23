"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowDownRight, ListTree } from "lucide-react";
import { usePageMotion } from "@/hooks/use-page-motion";
import { usePreferences } from "@/hooks/use-preferences";
import { Dialog } from "./ui/dialog";

interface Entry {
  id: string;
  title: string;
}
const excluded =
  "article,.article-card,.market-card,.country-card,.directory-card,.policy-card,.hot-card,.frontier-paper,.topic-card,.modal-content,.message,aside,.desk-story-list";

/** Derive a navigable outline from real page headings, including async sections. */
export function PageOutline() {
  const pathname = usePathname();
  const { language, t } = usePreferences();
  const { enabled } = usePageMotion();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState("");
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const destination = useRef<string | null>(null);
  useEffect(() => {
    setOpen(false);
  }, [pathname]);
  useEffect(() => {
    const root = document.getElementById("main-content");
    if (!root) return;
    let frame = 0;
    let counter = 0;
    let signature = "";
    let observer: IntersectionObserver | undefined;
    function scan() {
      frame = 0;
      const headings = [...root!.querySelectorAll<HTMLElement>("main h2")]
        .filter(
          (heading) =>
            !heading.closest(excluded) &&
            heading.getClientRects().length &&
            heading.innerText.trim(),
        )
        .slice(0, 20);
      const values = headings.map((heading) => {
        if (!heading.id) {
          let id: string;
          do {
            id = `mi-section-${++counter}`;
          } while (document.getElementById(id));
          heading.id = id;
        }
        return {
          id: heading.id,
          title: heading.innerText.replace(/\s+/g, " ").trim().slice(0, 100),
        };
      });
      const next = JSON.stringify(values);
      if (next === signature) return;
      signature = next;
      setEntries(values);
      setActive("");
      observer?.disconnect();
      observer = new IntersectionObserver(
        (observations) => {
          const current = observations.find((entry) => entry.isIntersecting);
          if (current) setActive(current.target.id);
        },
        { rootMargin: "-10% 0px -65% 0px" },
      );
      headings.forEach((heading) => observer!.observe(heading));
    }
    const mutations = new MutationObserver(() => {
      if (!frame) frame = requestAnimationFrame(scan);
    });
    mutations.observe(root, { subtree: true, childList: true });
    scan();
    return () => {
      mutations.disconnect();
      observer?.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [pathname, language]);
  function finishClose(event: Event) {
    event.preventDefault();
    const id = destination.current;
    destination.current = null;
    const heading = id ? document.getElementById(id) : null;
    if (heading) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      heading.scrollIntoView({
        behavior: enabled ? "smooth" : "auto",
        block: "start",
      });
    } else trigger.current?.focus();
  }
  if (entries.length < 2) return null;
  return (
    <>
      <button
        type="button"
        className="page-outline-trigger"
        ref={trigger}
        onClick={() => {
          destination.current = null;
          setOpen(true);
        }}
        aria-label={t("打开本页目录", "Open page outline")}
        title={t("本页目录 · 快速定位章节", "Page outline · jump to a section")}
        aria-haspopup="dialog"
      >
        <ListTree size={17} />
        <span>{t("本页目录", "On this page")}</span>
        <small>{entries.length}</small>
      </button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={t("本页目录", "On this page")}
        description={t(
          "选择章节，快速定位本页内容。",
          "Jump directly to a section on this page.",
        )}
        className="page-outline-dialog"
        onCloseAutoFocus={finishClose}
      >
        <nav aria-label={t("本页章节", "Page sections")}>
          {entries.map((entry, index) => (
            <button
              key={entry.id}
              type="button"
              aria-current={active === entry.id ? "location" : undefined}
              onClick={() => {
                destination.current = entry.id;
                setOpen(false);
              }}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{entry.title}</strong>
              <ArrowDownRight size={17} />
            </button>
          ))}
        </nav>
      </Dialog>
    </>
  );
}
