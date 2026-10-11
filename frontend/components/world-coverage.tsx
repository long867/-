import Link from "next/link";
import { ArrowUpRight, Globe2 } from "lucide-react";
import { WORLD_LAND } from "@/lib/world-land";
import type { Facets } from "@/types";
import { Locale } from "./locale";
import { MotionControl } from "./motion-control";

/** Geographic centers indicate country-level article coverage, not mine locations. */
const CENTERS: Record<string, [number, number, string]> = {
  中国: [104, 35, "China"],
  加拿大: [-106, 56, "Canada"],
  美国: [-100, 39, "United States"],
  墨西哥: [-102, 24, "Mexico"],
  秘鲁: [-75, -10, "Peru"],
  阿根廷: [-64, -34, "Argentina"],
  巴西: [-52, -14, "Brazil"],
  智利: [-71, -30, "Chile"],
  澳大利亚: [134, -25, "Australia"],
  南非: [25, -29, "South Africa"],
  刚果民主共和国: [23, -3, "DR Congo"],
  "刚果（金）": [23, -3, "DR Congo"],
  赞比亚: [28, -13, "Zambia"],
  印度尼西亚: [118, -3, "Indonesia"],
  印度: [79, 22, "India"],
  蒙古: [104, 47, "Mongolia"],
  俄罗斯: [95, 60, "Russia"],
  哈萨克斯坦: [67, 48, "Kazakhstan"],
  英国: [-3, 54, "United Kingdom"],
  德国: [10, 51, "Germany"],
  法国: [2, 47, "France"],
  欧盟: [15, 51, "European Union"],
  日本: [138, 37, "Japan"],
  韩国: [128, 36, "South Korea"],
  瑞典: [16, 62, "Sweden"],
  芬兰: [26, 64, "Finland"],
  挪威: [10, 63, "Norway"],
  津巴布韦: [30, -19, "Zimbabwe"],
  纳米比亚: [17, -22, "Namibia"],
  马达加斯加: [47, -19, "Madagascar"],
  沙特阿拉伯: [45, 24, "Saudi Arabia"],
  土耳其: [35, 39, "Türkiye"],
  乌兹别克斯坦: [64, 41, "Uzbekistan"],
};

export function WorldCoverage({ regions }: { regions?: Facets["regions"] }) {
  const points = (regions ?? []).filter((region) => CENTERS[region.name]);
  const labeled = new Set(
    [...points]
      .sort((a, b) => b.count - a.count)
      .slice(0, 2)
      .map((region) => region.name),
  );
  return (
    <div className="world-coverage">
      <div className="world-coverage-heading">
        <Globe2 size={14} />
        <span>GLOBAL RESOURCE ATLAS</span>
        <span className="atlas-coordinates">180° W — 180° E</span>
      </div>
      <div className="atlas-canvas">
        <div className="atlas-scan" aria-hidden="true" />
        <div className="atlas-orbit atlas-orbit-one" />
        <div className="atlas-orbit atlas-orbit-two" />
        <svg
          viewBox="0 0 720 310"
          className="coverage-map"
          role="group"
          aria-label="已发布文章的国家与地区覆盖 / Published article coverage by region"
        >
          <defs>
            <path id="atlas-land-outline" d={WORLD_LAND} />
            <pattern
              id="atlas-dots"
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="3" cy="3" r="0.8" fill="currentColor" />
            </pattern>
            <clipPath id="atlas-land-clip">
              <use href="#atlas-land-outline" />
            </clipPath>
          </defs>
          {[50, 100, 150, 200, 250].map((y) => (
            <line
              key={`h${y}`}
              x1="0"
              y1={y}
              x2="720"
              y2={y}
              className="atlas-gridline"
            />
          ))}
          {[90, 180, 270, 360, 450, 540, 630].map((x) => (
            <line
              key={`v${x}`}
              x1={x}
              y1="0"
              x2={x}
              y2="310"
              className="atlas-gridline"
            />
          ))}
          <use href="#atlas-land-outline" className="atlas-land" />
          <rect
            width="720"
            height="310"
            fill="url(#atlas-dots)"
            clipPath="url(#atlas-land-clip)"
            className="atlas-texture"
          />
          <g className="atlas-intelligence-links" aria-hidden="true">
            {points.map((region) => {
              const [lon, lat] = CENTERS[region.name];
              const x = (lon + 180) * 2,
                y = (85 - lat) * 2;
              const route = `M360,250 Q${(360 + x) / 2},${Math.min(250, y) - 60} ${x},${y}`;
              return (
                <g key={region.name}>
                  <path d={route} className="atlas-link-base" />
                  <path d={route} className="atlas-link-flow" />
                </g>
              );
            })}
            <circle cx="360" cy="250" r="14" className="atlas-hub-wave" />
            <circle
              cx="360"
              cy="250"
              r="14"
              className="atlas-hub-wave atlas-hub-wave-second"
            />
            <circle cx="360" cy="250" r="13" className="atlas-hub" />
            <text
              x="360"
              y="253.5"
              textAnchor="middle"
              className="atlas-hub-label"
            >
              MI
            </text>
          </g>
          {points.map((region) => {
            const [lon, lat, en] = CENTERS[region.name];
            const x = (lon + 180) * 2,
              y = (85 - lat) * 2;
            return (
              <a
                href={`/regions/${encodeURIComponent(region.name)}`}
                key={region.name}
                className="atlas-point"
                aria-label={`${region.name} / ${en}: ${region.count} 篇 / articles`}
              >
                <title>{`${region.name} · ${region.count} 篇已发布文章 / ${en} · ${region.count} published articles`}</title>
                <circle cx={x} cy={y} r="14" className="atlas-point-halo" />
                <circle cx={x} cy={y} r="5" className="atlas-point-core" />
                <circle cx={x} cy={y} r="2" className="atlas-point-center" />
                {labeled.has(region.name) && (
                  <g
                    transform={`translate(${x + 14},${y - 14})`}
                    className="atlas-point-label"
                  >
                    <rect x="-5" y="-14" width="83" height="38" rx="5" />
                    <text y="0" className="locale-zh">
                      {region.name}
                    </text>
                    <text y="0" className="locale-en">
                      {en}
                    </text>
                    <text y="15" className="atlas-point-count">
                      {region.count} <tspan className="locale-zh">篇情报</tspan>
                      <tspan className="locale-en">stories</tspan>
                    </text>
                  </g>
                )}
              </a>
            );
          })}
        </svg>
      </div>
      <div className="atlas-footer">
        <span>
          <span className="atlas-legend-dot" />
          <Locale
            zh="全球情报网络 · 报道覆盖"
            en="Intelligence network · Published coverage"
          />
        </span>
        <Link href="/regions" prefetch={false}>
          <Locale zh="探索地图" en="Explore atlas" />
          <ArrowUpRight size={13} />
        </Link>
        <MotionControl />
      </div>
      <div className="atlas-footnote">
        <Locale
          zh="标记为地区中心，非矿山坐标"
          en="Markers are regional centers, not mine locations"
        />
      </div>
    </div>
  );
}
