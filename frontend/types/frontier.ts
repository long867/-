export interface FrontierPaper {
  id: string;
  title: string;
  title_zh: string | null;
  summary_zh: string | null;
  doi: string;
  url: string;
  source_name: string;
  journal: string;
  publisher: string;
  authors: string[];
  institutions: string[];
  minerals: string[];
  directions: string[];
  published_at: string | null;
  published_date: string | null;
  date_precision: "day" | "month" | "year" | "unknown";
  abstract_available: boolean;
  evidence_scope: "abstract" | "bibliographic";
}

export interface FrontierPage {
  items: FrontierPaper[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
  overview: {
    total: number;
    recent_30_days: number;
    abstract_count: number;
    journal_count: number;
    directions: {
      key: string;
      name: string;
      english_name: string;
      count: number;
    }[];
    minerals: { name: string; count: number }[];
    last_collected_at: string | null;
    refresh_interval_hours: number;
  };
}

export interface FrontierFilters {
  direction: string;
  mineral: string;
  search: string;
  days: number;
  page: number;
}
