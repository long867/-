import { ArrowUpRight, Globe2, Search } from "lucide-react";

/** Server-rendered headline and native search stay usable before hydration. */
function Locale({ zh, en }: { zh: string; en: string }) {
  return (
    <>
      <span className="locale-zh">{zh}</span>
      <span className="locale-en">{en}</span>
    </>
  );
}
export function HomeHero({
  articleCount,
  sourceCount,
}: {
  articleCount?: number;
  sourceCount?: number;
}) {
  return (
    <section className="hero">
      <div className="hero-copy">
        <div className="eyebrow">
          <span className="status-dot" />
          THE GLOBAL MINING INTELLIGENCE DESK
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
            zh="全球政策、市场与产业动向，汇于一处。每一条情报，都有可追溯的来源。"
            en="Global policy, market and industry intelligence. Every story leads back to its source."
          />
        </p>
        <form className="hero-search" action="/search">
          <div className="search-field">
            <Search size={14} />
            <input
              name="q"
              aria-label="全局情报搜索 / Search all intelligence"
              placeholder="搜索锂价、关键矿产… / Search minerals…"
              maxLength={200}
            />
          </div>
          <button className="icon-button" aria-label="提交搜索 / Search">
            <ArrowUpRight size={18} />
          </button>
        </form>
      </div>
      <div className="hero-summary">
        <div>
          <div className="hero-number">
            {articleCount ?? "—"}
            <small>
              <Locale zh="篇" en="stories" />
            </small>
          </div>
          <div className="hero-label">
            <Locale zh="可追溯的已发布资讯" en="Published & sourced" />
          </div>
        </div>
        <div>
          <div className="hero-number">
            {sourceCount ?? "—"}
            <small>
              <Locale zh="个" en="sources" />
            </small>
          </div>
          <div className="hero-label">
            <Locale zh="已配置全球信源" en="Global source catalog" />
          </div>
        </div>
        <div className="live-caption">
          <Globe2 size={12} />
          <Locale
            zh="全球视角 · 中文洞察"
            en="A global perspective, in your language"
          />
        </div>
      </div>
    </section>
  );
}
