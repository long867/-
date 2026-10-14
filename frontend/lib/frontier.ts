import type { FrontierFilters } from "@/types/frontier";

const directions = [
  "exploration",
  "processing",
  "recycling",
  "environment",
  "digital",
  "governance",
];

export function frontierFilters(
  params: Record<string, string | string[] | undefined>,
): FrontierFilters {
  const text = (name: string, limit: number) =>
    typeof params[name] === "string"
      ? (params[name] as string).trim().slice(0, limit)
      : "";
  const direction = text("direction", 30);
  const days = Number(text("days", 3));
  const page = Number(text("page", 5));
  return {
    direction: directions.includes(direction) ? direction : "",
    mineral: text("mineral", 100),
    search: text("search", 200),
    days: [7, 30, 90, 365].includes(days) ? days : 90,
    page: Number.isInteger(page) && page >= 1 && page <= 10000 ? page : 1,
  };
}

export function frontierParams(filters: FrontierFilters): string {
  const params = new URLSearchParams({
    days: String(filters.days),
    page: String(filters.page),
    page_size: "12",
  });
  if (filters.direction) params.set("direction", filters.direction);
  if (filters.mineral) params.set("mineral", filters.mineral);
  if (filters.search) params.set("search", filters.search);
  return params.toString();
}
