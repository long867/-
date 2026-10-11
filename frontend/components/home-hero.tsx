import Link from "next/link";
import { ArrowDown, ArrowUpRight, Search, ShieldCheck } from "lucide-react";
import { WorldCoverage } from "./world-coverage";
import { Locale } from "./locale";
import type { Facets } from "@/types";

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
        </span>
      </div>
      <section className="hero observatory-hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="hero-eyebrow-line" /> RESOURCES SHAPE THE WORLD
          </div>
          <h1>
            <span className="locale-zh">
              <span className="hero-line">看见资源的流向，</span>
              <br />
              <span className="hero-accent">看清世界的动向。</span>
            </span>
            <span className="locale-en">
              <span className="hero-line">Follow the resources.</span>
              <br />
              <span className="hero-accent">Understand the world.</span>
            </span>
          </h1>
          <p className="subtitle">
            <Locale
              zh="从一座矿山到全球供应链。追踪价格、政策与产业变化，让每一次判断都有情报支撑。"
              en="From a single mine to the global supply chain. Track markets, policy and industry with intelligence you can verify."
            />
          </p>
          <div className="hero-actions">
            <a href="#intelligence-feed" className="observatory-primary">
              <Locale zh="探索矿产情报" en="Explore intelligence" />
              <ArrowDown size={15} />
            </a>
            <Link
              href="/chat"
              prefetch={false}
              className="observatory-secondary"
            >
              <Locale zh="向 AI 提问" en="Ask MiningIntel" />
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
        <WorldCoverage regions={facets?.regions} />
        <div className="observatory-metrics">
          {metrics.map((metric) => (
            <div className="observatory-metric" key={metric.code}>
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
    </>
  );
}
