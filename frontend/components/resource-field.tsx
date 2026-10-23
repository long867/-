"use client";

import Link from "next/link";
import { useMemo, useRef, useState, type CSSProperties } from "react";
import {
  ArrowUpRight,
  Expand,
  Globe2,
  Layers3,
  Orbit,
  Pause,
  Play,
  Scan,
  Sparkles,
} from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { useAmbientCycle } from "@/hooks/use-ambient-cycle";
import { resourceNodes, resourcePreview } from "@/lib/resource-field.mjs";
import { latestQuotation } from "@/lib/observation.mjs";
import { REGION_CENTERS } from "@/lib/resource-geography";
import type { Article, Facets, MineralMarket } from "@/types";
import { Dialog } from "./ui/dialog";
import { ResourceAtlas } from "./resource-atlas";
import { MineralWatchButton } from "./mineral-watch-button";
import { MotionControl } from "./motion-control";

type Scope = "minerals" | "regions";
interface FieldProps {
  facets?: Facets;
  market?: MineralMarket;
  articles?: Article[];
  scope: Scope;
  setScope: (scope: Scope) => void;
  focus: string;
  setFocus: (name: string) => void;
  automatic: boolean;
  setAutomatic: (value: boolean) => void;
}

/** Visualize actual coverage counts; animated paths are directory connections. */
function ResourceField({
  facets,
  market,
  articles,
  scope,
  setScope,
  focus,
  setFocus,
  automatic,
  setAutomatic,
}: FieldProps) {
  const { t, language } = usePreferences();
  const content = useRef<HTMLDivElement>(null);
  const nodes = useMemo(() => resourceNodes(facets?.[scope]), [facets, scope]);
  const current = nodes.find((node) => node.name === focus) || nodes[0];
  const metadata = market?.items.find((item) => item.name === current?.name);
  const preview = resourcePreview(articles, scope, current?.name) as Article[];
  const { running, visible, interactionProps } = useAmbientCycle(
    content,
    () => {
      if (nodes.length < 2) return;
      const index = nodes.findIndex((node) => node.name === current?.name);
      setFocus(nodes[(index + 1) % nodes.length].name);
    },
    automatic && nodes.length > 1,
    8000,
  );
  const name = (value: string) =>
    language === "zh"
      ? value
      : scope === "regions"
        ? REGION_CENTERS[value]?.[2] || value
        : market?.items.find((item) => item.name === value)?.english_name ||
          value;
  const href = `/${scope}/${encodeURIComponent(current?.name || "")}`;
  const quote = scope === "minerals" ? latestQuotation(metadata?.prices) : null;
  return (
    <div
      className="resource-field"
      data-scope={scope}
      data-cruising={running}
      data-visible={visible}
    >
      <div className="field-controls">
        <div
          className="field-scopes"
          role="group"
          aria-label={t("星图维度", "Constellation dimension")}
        >
          <button
            aria-pressed={scope === "minerals"}
            onClick={() => {
              setScope("minerals");
              setFocus("");
            }}
          >
            <Layers3 size={12} />
            {t("矿种", "Minerals")}
          </button>
          <button
            aria-pressed={scope === "regions"}
            onClick={() => {
              setScope("regions");
              setFocus("");
            }}
          >
            <Globe2 size={12} />
            {t("国家地区", "Regions")}
          </button>
        </div>
        <div className="field-motion-actions">
          <MotionControl compact />
          <button
            className="field-cruise"
            aria-pressed={automatic}
            onClick={() => setAutomatic(!automatic)}
            aria-label={
              automatic
                ? t("暂停星图巡航", "Pause constellation tour")
                : t("开启星图巡航", "Start constellation tour")
            }
          >
            {automatic ? <Pause size={11} /> : <Play size={11} />}
            <span>{t("巡航", "Tour")}</span>
          </button>
        </div>
      </div>
      <div className="field-content" ref={content} {...interactionProps}>
        <div
          className="field-stage"
          aria-label={t("报道覆盖星图", "Published coverage constellation")}
        >
          <div className="field-nebula" aria-hidden="true" />
          <div className="field-grid" aria-hidden="true" />
          <svg
            className="field-connections"
            viewBox="0 0 600 460"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <radialGradient id={`field-aura-${scope}`}>
                <stop stopColor="currentColor" stopOpacity=".14" />
                <stop offset="1" stopColor="currentColor" stopOpacity="0" />
              </radialGradient>
            </defs>
            <ellipse
              cx="300"
              cy="230"
              rx="214"
              ry="160"
              fill={`url(#field-aura-${scope})`}
            />
            <ellipse
              className="field-orbit-track"
              cx="300"
              cy="230"
              rx="224"
              ry="167"
            />
            <ellipse
              className="field-orbit-inner"
              cx="300"
              cy="230"
              rx="168"
              ry="118"
            />
            {nodes.map((node, index) => (
              <g
                key={node.name}
                className={
                  node.name === current?.name
                    ? "field-link is-focused"
                    : "field-link"
                }
              >
                <path
                  d={`M300 230 Q${(300 + node.x) / 2 + 30} ${(230 + node.y) / 2 - 35} ${node.x} ${node.y}`}
                />
                <path
                  className="field-link-flow"
                  pathLength="1"
                  style={
                    { "--flow-delay": `${-index * 1.3}s` } as CSSProperties
                  }
                  d={`M300 230 Q${(300 + node.x) / 2 + 30} ${(230 + node.y) / 2 - 35} ${node.x} ${node.y}`}
                />
              </g>
            ))}
          </svg>
          <div className="field-axis field-axis-n" aria-hidden="true">
            RESOURCE INTELLIGENCE
          </div>
          <div className="field-core" aria-hidden="true">
            <span className="field-core-orbit" />
            <span className="field-core-orbit field-core-orbit-two" />
            <div className="field-core-sphere">
              <svg viewBox="0 0 120 120">
                <path d="M60 12 99 35 99 83 60 107 21 83 21 35ZM60 12V60L99 83M21 83 60 60 99 35M21 35 60 60V107" />
                <path
                  className="field-core-flow"
                  d="M60 12 99 35 99 83 60 107 21 83 21 35Z"
                />
              </svg>
            </div>
            <strong>
              {scope === "minerals" ? (
                metadata?.symbol || "MI"
              ) : (
                <Globe2 size={29} />
              )}
            </strong>
            <span>MININGINTEL</span>
          </div>
          {nodes.map((node, index) => (
            <button
              type="button"
              key={node.name}
              className={`field-node ${node.name === current?.name ? "is-focused" : ""}`}
              style={
                {
                  left: `${node.x / 6}%`,
                  top: `${node.y / 4.6}%`,
                  "--node-delay": `${-index * 0.7}s`,
                } as CSSProperties
              }
              aria-pressed={node.name === current?.name}
              aria-label={t(
                `聚焦${node.name}，${node.count}篇报道`,
                `Focus ${name(node.name)}, ${node.count} stories`,
              )}
              onClick={() => {
                setFocus(node.name);
                setAutomatic(false);
              }}
            >
              <span className="field-node-target">
                <span />
                <i />
              </span>
              <strong>{name(node.name)}</strong>
              <small>{node.count.toLocaleString("en-US")}</small>
            </button>
          ))}
          {!nodes.length && (
            <div className="field-empty">
              {t(
                "等待已发布资料的覆盖统计",
                "Waiting for published coverage statistics",
              )}
            </div>
          )}
        </div>
        {current && (
          <div className="field-inspector" key={`${scope}-${current.name}`}>
            <div className="field-inspector-heading">
              <span>
                <Scan size={12} />
                {t("当前聚焦", "IN FOCUS")}
              </span>
              {scope === "minerals" && (
                <MineralWatchButton name={current.name} />
              )}
            </div>
            <div className="field-focus-title">
              <Link href={href} prefetch={false}>
                <h3>{name(current.name)}</h3>
                <ArrowUpRight size={17} />
              </Link>
              <span>
                <strong>{current.count.toLocaleString("en-US")}</strong>{" "}
                {t("篇已发布报道", "published stories")}
              </span>
            </div>
            {quote && (
              <div className="field-price">
                <span>{quote.product || current.name}</span>
                <strong>
                  {Number(quote.price).toLocaleString("en-US", {
                    maximumFractionDigits: 2,
                  })}{" "}
                  <small>
                    {quote.currency}/{quote.unit}
                  </small>
                </strong>
                <a
                  href={quote.source_url || quote.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="field-quote-source"
                >
                  <time dateTime={quote.date}>
                    {t("报价", "Quoted")} {quote.date}
                  </time>
                  <ArrowUpRight size={10} />
                </a>
              </div>
            )}
            {!!preview.length && (
              <div className="field-preview">
                {preview.slice(0, 1).map((article) => (
                  <Link
                    key={article.id}
                    href={`/articles/${article.id}`}
                    prefetch={false}
                  >
                    <span>{t("本页资料快览", "From this page's sources")}</span>
                    <strong>
                      {language === "zh"
                        ? article.title_zh || article.title
                        : article.title}
                    </strong>
                    <ArrowUpRight size={12} />
                  </Link>
                ))}
              </div>
            )}
            <div className="field-inspector-actions">
              <Link href={href} prefetch={false}>
                {t("查看全部资料", "Explore coverage")}{" "}
                <ArrowUpRight size={12} />
              </Link>
              <Link
                href={`/chat?q=${encodeURIComponent(t(`请分析${current.name}近期的矿产资源动向、潜在影响与需要核实的信息。`, `Analyze recent mineral resource developments involving ${name(current.name)}, possible impacts and information to verify.`))}`}
                prefetch={false}
              >
                <Sparkles size={12} />
                {t("研判", "Analyze")}
              </Link>
            </div>
          </div>
        )}
      </div>
      <div className="field-legend">
        <span className="field-legend-dot" />
        {t(
          "节点显示报道数；连线为资料导航，非贸易流量。",
          "Nodes show coverage; lines navigate sources, not trade flows.",
        )}
      </div>
    </div>
  );
}

/** Switch between an immersive coverage constellation and the geographic atlas. */
export function HeroObservatory({
  facets,
  market,
  articles,
}: {
  facets?: Facets;
  market?: MineralMarket;
  articles?: Article[];
}) {
  const { t } = usePreferences();
  const [view, setView] = useState<"field" | "globe">("field");
  const [scope, setScope] = useState<Scope>("minerals");
  const [focus, setFocus] = useState("");
  const [automatic, setAutomatic] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const expandTrigger = useRef<HTMLButtonElement>(null);
  const props: FieldProps = {
    facets,
    market,
    articles,
    scope,
    setScope,
    focus,
    setFocus,
    automatic,
    setAutomatic,
  };
  return (
    <div className="hero-observatory">
      <div className="observatory-mode-bar">
        <span>
          <Orbit size={13} />
          {t("资源观测舱", "RESOURCE OBSERVATORY")}
        </span>
        <div
          role="group"
          aria-label={t("资源可视化模式", "Resource visualization mode")}
        >
          <button
            aria-pressed={view === "field"}
            onClick={() => setView("field")}
          >
            <Scan size={12} />
            {t("资源星图", "Constellation")}
          </button>
          <button
            aria-pressed={view === "globe"}
            onClick={() => setView("globe")}
          >
            <Globe2 size={12} />
            {t("全球地球", "Globe")}
          </button>
          <button
            ref={expandTrigger}
            className="field-expand"
            onClick={() => setExpanded(true)}
            aria-label={t("展开资源星图", "Expand resource constellation")}
          >
            <Expand size={13} />
          </button>
        </div>
      </div>
      {view === "globe" && !expanded ? (
        <ResourceAtlas regions={facets?.regions} />
      ) : (
        <div className="field-embed">
          {!expanded && <ResourceField {...props} />}
        </div>
      )}
      <Dialog
        open={expanded}
        onOpenChange={setExpanded}
        title={t("全球资源星图", "Global resource constellation")}
        description={t(
          "从已发布报道观察矿种与国家。选择节点进入资料；布局位置不代表地理坐标。",
          "Explore minerals and regions through published coverage. Choose a node to open sources; layout positions are not geographic coordinates.",
        )}
        className="field-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          expandTrigger.current?.focus();
        }}
      >
        {expanded && <ResourceField {...props} />}
      </Dialog>
    </div>
  );
}
