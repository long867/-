export interface ResearchInput {
  mineral?: string | null;
  region?: string | null;
  days: number;
  role: "general" | "procurement" | "project" | "policy";
  focus: string;
}
export interface ResearchSource {
  index: number;
  article_id: string;
  title: string;
  original_title: string;
  original_excerpt: string;
  snippet: string;
  source_name: string;
  url: string;
  category: string;
  published_at: string | null;
  authority_score: number;
}
export interface ResearchResult {
  id?: string | null;
  mode: "llm" | "evidence_based" | "insufficient";
  scope: ResearchInput;
  generated_at: string;
  coverage: {
    article_count: number;
    evidence_count: number;
    source_count: number;
    policy_count: number;
    price_observations: number;
    latest_published_at: string | null;
  };
  limitations: string[];
  sources: ResearchSource[];
  facts: {
    text: string;
    source_id: number;
    quote: string;
    quote_field: "title" | "content";
    start_char: number;
    end_char: number;
  }[];
  scenarios: {
    title: string;
    direction: "risk" | "opportunity" | "mixed";
    impact: string;
    mechanism: string;
    conditions: string[];
    source_ids: number[];
    confidence: "low" | "medium";
  }[];
  actions: {
    title: string;
    detail: string;
    owner: string;
    priority: "high" | "medium" | "low";
    source_ids: number[];
  }[];
  watchlist: string[];
}
