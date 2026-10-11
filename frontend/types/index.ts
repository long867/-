export interface Article {
  id: string;
  source_id: string;
  source_name?: string | null;
  date_precision?: "day" | "time" | null;
  title: string;
  title_zh: string | null;
  summary: string | null;
  summary_zh: string | null;
  url: string;
  published_at: string | null;
  fetched_at: string;
  category: string;
  language: string;
  is_translated: boolean;
  quality_score: number;
  relevance_score: number;
  event_id: string | null;
  minerals: string[];
  regions: string[];
  companies: string[];
  projects: string[];
  tags: string[];
  status: string;
  content?: string;
  content_zh?: string | null;
}
export interface ArticlePage {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
}
export interface Source {
  id: string;
  name: string;
  url: string;
  category: string;
  language: string;
  authority_score: number;
  type?: string;
  region?: string | null;
  fetch_interval?: number;
  active?: boolean;
  last_fetched_at?: string | null;
  config_json?: Record<string, unknown>;
}
export interface MineralEvent {
  id: string;
  title_zh: string;
  summary_zh: string | null;
  last_updated_at: string;
  article_count: number;
  minerals: string[];
  regions: string[];
  importance_score: number;
}
export interface Price {
  id: string;
  mineral: string;
  price: string;
  unit: string;
  currency: string;
  date: string;
  source: string;
  change_pct: string | null;
  product?: string | null;
  price_type?: "spot" | "futures" | "benchmark";
  source_url?: string | null;
}

export interface EventPage {
  items: MineralEvent[];
  total: number;
  page: number;
  page_size: number;
}
export interface PolicyPage {
  items: Policy[];
  total: number;
  page: number;
  page_size: number;
}
export interface MineralFacet {
  name: string;
  article_count: number;
  recent_count: number;
  previous_count: number;
  trend: "up" | "down" | "flat";
}
export interface Digest {
  id?: string | null;
  scheduled?: boolean;
  analysis?: {
    hot_minerals?: { mineral: string; count: number }[];
    hot_signals?: Insights["hotspots"];
    policies?: PolicyUpdate[];
    price_alerts?: Insights["price_alerts"];
    price_trends?: PriceTrend[];
    price_series?: Price[];
    events?: {
      id: string;
      title: string;
      importance_score: number;
      article_count: number;
    }[];
    coverage_by_day?: { date: string; count: number }[];
  };
  kind: "daily" | "weekly" | "monthly";
  title: string;
  content: string;
  mode: "extractive" | "llm" | "empty";
  period_start: string;
  period_end: string;
  timezone: string;
  generated_at: string;
  stats: {
    article_count: number;
    source_count: number;
    minerals: Record<string, number>;
    regions: Record<string, number>;
    categories: Record<string, number>;
  };
  sources: {
    article_id: string;
    title: string;
    url: string;
    source_name: string;
    published_at: string | null;
    snippet: string;
  }[];
}
export interface Policy {
  id: string;
  title: string;
  title_zh: string | null;
  country: string;
  region?: string | null;
  minerals: string[];
  effective_date: string | null;
  url: string;
  summary_zh: string | null;
  impact_score: number;
}

export interface ProjectLocation {
  name: string;
  article_id: string;
  title: string;
  url: string;
  latitude: number | null;
  longitude: number | null;
}
export interface SearchResults {
  query: string;
  articles: Article[];
  events: MineralEvent[];
  policies: Policy[];
  counts: Record<string, number>;
}
export interface User {
  id: string;
  email: string;
  is_admin: boolean;
}
export interface Token {
  access_token: string;
  user: User;
}
export interface Citation {
  id: number;
  index: number;
  article_id: string;
  chunk_id: string;
  title: string;
  url: string;
  quote: string;
  start_char: number;
  end_char: number;
  published_at: string | null;
  source_name: string;
  snippet: string;
}
export interface ChatAnswer {
  session_id: string;
  message_id: string;
  answer: string;
  sources: Citation[];
  mode: "grounded" | "extractive" | "insufficient";
}
export interface ChatMessage {
  id: string;
  session_id: string;
  question: string;
  answer: string;
  sources_json: Citation[];
  mode: ChatAnswer["mode"];
  created_at: string;
}
export interface Session {
  id: string;
  title: string;
  created_at: string;
}
export interface Subscription {
  id: string;
  subscribed_minerals: string[];
  subscribed_regions: string[];
  frequency: "daily" | "weekly";
  email_enabled: boolean;
  price_alerts_enabled: boolean;
}
export interface Facet {
  name: string;
  count: number;
}
export interface Facets {
  minerals: Facet[];
  regions: Facet[];
  tags: Facet[];
}
export interface Insights {
  window_hours: number;
  generated_at: string;
  hotspots: {
    mineral: string;
    count: number;
    previous_count: number;
    growth_pct: number | null;
    is_new: boolean;
    window: "24h" | "48h" | "7d";
    heat_score: number;
    is_hot: boolean;
    trend: "up" | "down" | "flat";
    baseline_mean: number;
    baseline_std: number;
    baseline_samples: number;
    baseline_sufficient: boolean;
    z_score: number | null;
    sparkline: number[];
  }[];
  price_alerts: {
    mineral: string;
    price: string;
    unit: string;
    currency: string;
    change_pct: string;
    date: string;
    source: string;
    id?: string;
    product?: string | null;
    source_url?: string | null;
    severity?: "red" | "yellow" | "green";
    direction?: "up" | "down" | "flat";
  }[];
}

export interface PriceTrend extends Price {
  direction: "up" | "down" | "flat";
  consecutive_moves: number;
  observations: { date: string; price: string }[];
}
export interface PolicyUpdate extends Policy {
  published_at: string | null;
  themes: string[];
}
export interface ReportPage {
  items: Digest[];
  total: number;
  page: number;
  page_size: number;
}
export interface Notice {
  id: string;
  kind: "report" | "price_alert";
  title: string;
  body: string;
  minerals: string[];
  regions: string[];
  url: string;
  created_at: string;
  read: boolean;
  severity: "red" | "yellow" | "green" | null;
}
export interface NoticePage {
  items: Notice[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}
export interface Report {
  id: string;
  title: string;
  content: string;
  kind: string;
  period_start: string;
  period_end: string;
}
export interface Run {
  id: string;
  source_id: string | null;
  status: string;
  fetched_count: number;
  new_count: number;
  duplicate_count: number;
  error_count: number;
  error: string | null;
  created_at: string;
}
