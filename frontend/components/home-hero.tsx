import Link from "next/link";
import { ArrowDown, ArrowUpRight, Search, ShieldCheck } from "lucide-react";
import { ResourceAtlas, ObservatoryClock } from "./resource-atlas";
import { Locale } from "./locale";
import type { Facets } from "@/types";
import {
  ObservatorySignature,
  ObservatoryDestinations,
} from "./observatory-signature";

/** The observatory uses published article counts, never synthetic live counters. */
export function HomeHero({
  articleCount,
  sourceCount,
  facets,
}: {
  articleCount?: number;
  sourceCount?: number;
  facets?: Facets;
}) {
  const metrics = [
    {
      value: articleCount,
      zh: "已发布情报",
      en: "Published stories",
      code: "INTELLIGENCE",
    },
    {
      value: facets?.minerals.length,
      zh: "已报道矿种",
      en: "Minerals covered",
      code: "COMMODITIES",
    },
    {
      value: facets?.regions.length,
      zh: "报道覆盖地区",
      en: "Regions covered",
      code: "GEOGRAPHY",
    },
    {
      value: sourceCount,
      zh: "已配置信源",
      en: "Sources in catalog",
      code: "SOURCE NETWORK",
    },
  ];
  return (
    <>
      <div className="observatory-context">
        <span>
          <span className="status-dot" />
          <Locale
            zh="全球矿产资源观察站"
            en="Global mineral resource observatory"
          />
        </span>
        <span className="observatory-context-note">
          <ShieldCheck size={13} />
          <Locale
            zh="真实来源 · 有据可查"
            en="Original sources. Traceable evidence."
          />
          <ObservatoryClock />
        </span>
      </div>
      <section className="hero observatory-hero">
        <ObservatorySignature />
        <div className="hero-copy">
          <div className="hero-edition">
            <span className="edition-line" />
            <Locale
              zh="全球资源情报 · 专业研究工作台"
              en="Global resource intelligence · Your research desk"
            />
          </div>
          <div className="eyebrow">
            <span className="hero-eyebrow-line" /> GLOBAL RESOURCE INTELLIGENCE
          </div>
          <h1>
            <span className="locale-zh">
              <span className="hero-line">看清资源变化，</span>
              <br />
              <span className="hero-accent">让判断更进一步。</span>
            </span>
            <span className="locale-en">
              <span className="hero-line">Global signals.</span>
              <br />
              <span className="hero-accent">Your perspective.</span>
            </span>
          </h1>
          <p className="subtitle">
            <Locale
              zh="市场、政策、产业、科研，一张工作台掌握全球矿产变化。建立自己的观察清单，从真实资料进入深度研判。"
              en="Markets, policy, industry and research, in one resource desk. Build your watchlist and turn original sources into informed research."
            />
          </p>
          <div className="hero-capabilities">
            <span>
              <span className="capability-beacon" />{" "}
              <Locale zh="全球信源" en="Global sources" />
            </span>
            <span>
              <span className="capability-beacon" />{" "}
              <Locale zh="矿种追踪" en="Commodity intelligence" />
            </span>
            <span>
              <span className="capability-beacon" />{" "}
              <Locale zh="有据问答" en="Evidence-based answers" />
            </span>
          </div>
          <div className="hero-actions">
            <a href="#signal-desk" className="observatory-primary">
              <Locale zh="打开情报工作台" en="Open your intelligence desk" />
              <ArrowDown size={15} />
            </a>
            <Link
              href="/chat"
              prefetch={false}
              className="observatory-secondary"
            >
              <Locale zh="向矿眸智探提问" en="Ask 矿眸智探" />
              <ArrowUpRight size={15} />
            </Link>
          </div>
          <form className="hero-search" action="/search">
            <div className="search-field">
              <Search size={15} />
              <input
                name="q"
                aria-label="全局情报搜索 / Search all intelligence"
                placeholder="搜索矿种、公司、政策… / Search intelligence…"
                maxLength={200}
              />
            </div>
            <button className="icon-button" aria-label="提交搜索 / Search">
              <ArrowUpRight size={18} />
            </button>
          </form>
        </div>
        <ResourceAtlas regions={facets?.regions} />
        <div className="observatory-metrics">
          {metrics.map((metric, index) => (
            <div className="observatory-metric" key={metric.code}>
              <span className="metric-serial" aria-hidden="true">
                0{index + 1}
              </span>
              <span className="metric-code">{metric.code}</span>
              <div>
                <strong>{metric.value?.toLocaleString("en-US") ?? "—"}</strong>
                <span>
                  <Locale zh={metric.zh} en={metric.en} />
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>
      <ObservatoryDestinations />
    </>
  );
}
