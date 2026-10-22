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
              zh="以全球视野，读懂资源价值"
              en="A global perspective on resource intelligence"
            />
          </div>
          <div className="eyebrow">
            <span className="hero-eyebrow-line" /> THE MINERAL INTELLIGENCE
            TERMINAL
          </div>
          <h1>
            <span className="locale-zh">
              <span className="hero-line">洞察资源脉动，</span>
              <br />
              <span className="hero-accent">看见全球格局。</span>
            </span>
            <span className="locale-en">
              <span className="hero-line">Intelligence.</span>
              <br />
              <span className="hero-accent">From the ground up.</span>
            </span>
          </h1>
          <p className="subtitle">
            <Locale
              zh="从一座矿山到全球供应链。追踪价格、政策与产业变化，让每一次判断都有情报支撑。"
              en="From a single mine to the global supply chain. Track markets, policy and industry with intelligence you can verify."
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
            <a href="#intelligence-feed" className="observatory-primary">
              <Locale zh="探索矿产情报" en="Explore intelligence" />
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
