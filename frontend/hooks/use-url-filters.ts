"use client";
import { useCallback, useEffect, useRef, useState } from "react";
export interface FeedFilters {
  minerals: string[];
  regions: string[];
  tags: string[];
  search: string;
  category: string;
  sort_by: string;
  date_from: string;
  date_to: string;
  company: string;
}
export const emptyFilters: FeedFilters = {
  minerals: [],
  regions: [],
  tags: [],
  search: "",
  category: "",
  sort_by: "published_at",
  date_from: "",
  date_to: "",
  company: "",
};
export function parseFilters(search: string): FeedFilters {
  const params = new URLSearchParams(search);
  return {
    minerals: params
      .getAll("minerals")
      .concat(params.getAll("mineral"))
      .slice(0, 20),
    regions: params
      .getAll("regions")
      .concat(params.getAll("region"))
      .slice(0, 20),
    tags: params.getAll("tags").concat(params.getAll("tag")).slice(0, 20),
    search: params.get("q") || params.get("search") || "",
    category: params.get("category") || "",
    sort_by:
      params.get("sort_by") === "quality_score"
        ? "quality_score"
        : "published_at",
    date_from: params.get("date_from") || "",
    date_to: params.get("date_to") || "",
    company: params.get("company") || "",
  };
}
export function filterParams(filters: FeedFilters, page = 1): URLSearchParams {
  const params = new URLSearchParams({
    page: String(page),
    page_size: "10",
    sort_by: filters.sort_by,
  });
  for (const key of ["minerals", "regions", "tags"] as const)
    for (const value of filters[key]) params.append(key, value);
  for (const key of ["category", "date_from", "date_to", "company"] as const)
    if (filters[key]) params.set(key, filters[key]);
  if (filters.search.trim()) params.set("search", filters.search.trim());
  return params;
}
export function useUrlFilters() {
  const [filters, setFilters] = useState<FeedFilters>(emptyFilters);
  const latest = useRef(filters);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const sync = () => {
      latest.current = parseFilters(location.search);
      setFilters(latest.current);
    };
    sync();
    setReady(true);
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const update = useCallback((changes: Partial<FeedFilters>) => {
    const next = { ...latest.current, ...changes };
    latest.current = next;
    setFilters(next);
    const params = filterParams(next);
    params.delete("page");
    params.delete("page_size");
    if (next.sort_by === "published_at") params.delete("sort_by");
    const view = new URLSearchParams(location.search).get("view");
    if (view) params.set("view", view);
    history.replaceState(
      null,
      "",
      `${location.pathname}${params.size ? "?" + params : ""}`,
    );
  }, []);
  return { filters, update, ready };
}
