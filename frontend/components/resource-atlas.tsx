"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  ArrowUpRight,
  Globe2,
  Map,
  MoveHorizontal,
  Crosshair,
} from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { REGION_CENTERS } from "@/lib/resource-geography";
import type { Facet } from "@/types";
import { WorldCoverage } from "./world-coverage";
import { MotionControl } from "./motion-control";

const Globe = dynamic(
  () => import("./resource-globe").then((module) => module.ResourceGlobe),
  {
    ssr: false,
    loading: () => (
      <div className="globe-placeholder" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    ),
  },
);

/** A live clock is separate from the data display; article counts never oscillate. */
export function ObservatoryClock() {
  const [time, setTime] = useState("—:—:—");
  useEffect(() => {
    const update = () =>
      setTime(
        new Intl.DateTimeFormat("en-GB", {
          timeZone: "Asia/Shanghai",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hourCycle: "h23",
        }).format(new Date()),
      );
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="observatory-clock">
      <span>BJT</span> <time suppressHydrationWarning>{time}</time>
    </span>
  );
}

export function ResourceAtlas({ regions }: { regions?: Facet[] }) {
  const { t, language } = usePreferences();
  const sorted = useMemo(
    () =>
      [...(regions || [])]
        .filter((region) => REGION_CENTERS[region.name])
        .sort((a, b) => b.count - a.count),
    [regions],
  );
  const [focus, setFocus] = useState(sorted[0]?.name || "");
  const [mode, setMode] = useState("globe");
  const selected = sorted.find((region) => region.name === focus) || sorted[0];
  const center = selected ? REGION_CENTERS[selected.name] : undefined;
  return (
    <section
      className="resource-atlas"
      aria-label={t("全球资源情报图谱", "Global resource intelligence atlas")}
    >
      <div className="resource-atlas-topline">
        <span>
          <span className="signal-indicator" />{" "}
          {t("全球资源图谱", "GLOBAL RESOURCE ATLAS")}
        </span>
        <div
          className="atlas-view-control"
          aria-label={t("图谱视图", "Atlas view")}
        >
          <button
            type="button"
            aria-pressed={mode === "globe"}
            onClick={() => setMode("globe")}
            aria-label={t("三维地球", "Globe view")}
          >
            <Globe2 size={13} />
          </button>
          <button
            type="button"
            aria-pressed={mode === "map"}
            onClick={() => setMode("map")}
            aria-label={t("平面地图", "Map view")}
          >
            <Map size={13} />
          </button>
        </div>
      </div>
      {mode === "globe" ? (
        <>
          <div className="globe-stage">
            <svg
              className="atlas-orbital-frame"
              viewBox="0 0 600 420"
              fill="none"
              aria-hidden="true"
            >
              <g className="atlas-orbit-ring">
                <ellipse
                  cx="300"
                  cy="210"
                  rx="238"
                  ry="182"
                  stroke="currentColor"
                  strokeDasharray="2 15"
                />
                <path
                  d="M300 28A182 182 0 0 1 482 210"
                  stroke="currentColor"
                  strokeWidth="2"
                />
              </g>
              <path
                d="M36 68V38H66M534 38H564V68M36 352V382H66M534 382H564V352"
                stroke="currentColor"
              />
            </svg>
            <div className="globe-reticle" aria-hidden="true" />
            <div className="globe-grid" aria-hidden="true" />
            <Globe regions={sorted} focus={focus} onSelect={setFocus} />
            <div className="globe-axis-label" aria-hidden="true">
              MININGINTEL
              <br />
              <span>RESOURCE NETWORK</span>
            </div>
            <div className="globe-instruction">
              <MoveHorizontal size={12} />{" "}
              {t("拖动旋转 · 点击地区", "Drag to rotate · Select a region")}
            </div>
            {selected && (
              <Link
                className="globe-focus-card"
                href={`/regions/${encodeURIComponent(selected.name)}`}
                prefetch={false}
              >
                <span className="globe-focus-eyebrow">
                  <Crosshair size={10} /> {t("当前聚焦", "REGION IN FOCUS")}{" "}
                  <ArrowUpRight size={12} />
                </span>
                <strong>
                  {language === "zh" ? selected.name : center?.[2]}
                </strong>
                <span className="globe-focus-count">
                  {selected.count.toLocaleString("en-US")}{" "}
                  <small>{t("篇已发布情报", "published stories")}</small>
                </span>
                {center && (
                  <span className="globe-focus-coordinates">
                    {Math.abs(center[1])}° {center[1] >= 0 ? "N" : "S"} /{" "}
                    {Math.abs(center[0])}° {center[0] >= 0 ? "E" : "W"}
                  </span>
                )}
              </Link>
            )}
          </div>
          <div
            className="globe-region-strip"
            aria-label={t("聚焦报道地区", "Focus on a coverage region")}
          >
            {sorted.slice(0, 5).map((region) => (
              <button
                type="button"
                key={region.name}
                aria-pressed={region.name === selected?.name}
                onClick={() => setFocus(region.name)}
              >
                <span>
                  {language === "zh"
                    ? region.name
                    : REGION_CENTERS[region.name][2]}
                </span>
                <small>{region.count}</small>
              </button>
            ))}
          </div>
          <div className="globe-footer">
            <span>
              <span className="atlas-legend-dot" />
              {t(
                "地区中心 · 已发布报道覆盖",
                "Regional centers · Published coverage",
              )}
            </span>
            <MotionControl />
          </div>
        </>
      ) : (
        <div className="flat-atlas-panel">
          <WorldCoverage regions={regions} />
        </div>
      )}
    </section>
  );
}
