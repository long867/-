"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  TrendingUp,
  TrendingDown,
  Minus,
  MapPin,
} from "lucide-react";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import { SectionHeading } from "./section-heading";
import { ErrorState, SkeletonCards } from "./ui/states";
import type { MineralFacet } from "@/types";
const symbols: Record<string, string> = {
  锂: "Li",
  铜: "Cu",
  金: "Au",
  银: "Ag",
  镍: "Ni",
  钴: "Co",
  锌: "Zn",
  铀: "U",
  铝: "Al",
  铅: "Pb",
  锡: "Sn",
  钨: "W",
  锰: "Mn",
  镁: "Mg",
  铂: "Pt",
  钯: "Pd",
  铬: "Cr",
  铁矿石: "Fe",
  石墨: "C",
  稀土: "REE",
  煤: "COAL",
};
export function Directory({
  kind,
  initial,
}: {
  kind: "minerals" | "regions";
  initial?: MineralFacet[];
}) {
  const { t } = usePreferences();
  const query = useQuery({
    queryKey: [kind === "minerals" ? "mineral-catalog" : "region-catalog"],
    queryFn: () => publicApi<MineralFacet[]>(`/${kind}`),
    initialData: initial,
    staleTime: 300000,
  });
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow={
          kind === "minerals"
            ? "THE COMMODITY ATLAS"
            : "GLOBAL RESOURCE GEOGRAPHY"
        }
        zh={kind === "minerals" ? "矿种情报" : "全球地区"}
        en={
          kind === "minerals"
            ? "Commodity intelligence"
            : "Regional intelligence"
        }
        description={
          kind === "minerals"
            ? "一条资源链，一个持续更新的观察窗口。"
            : "从资源产地到政策中心，按地理视角解读矿业动向。"
        }
        descriptionEn="Explore original reporting, policy and market observations by focus area."
      />
      {query.isPending ? (
        <SkeletonCards />
      ) : query.isError ? (
        <ErrorState error={query.error} retry={() => query.refetch()} />
      ) : (
        <div className="directory-grid">
          {query.data.map((item) => (
            <Link
              href={`/${kind}/${encodeURIComponent(item.name)}`}
              className="directory-card"
              key={item.name}
            >
              <div className="flex justify-between items-center">
                <span className="mineral-symbol">
                  {kind === "minerals" ? (
                    symbols[item.name] || "MINERAL"
                  ) : (
                    <MapPin size={16} />
                  )}
                </span>
                <ArrowUpRight size={15} className="text-muted" />
              </div>
              <h2>{item.name}</h2>
              <p className="subtitle text-xs">
                {item.article_count} {t("篇可追溯资料", "sourced articles")}
              </p>
              <div className="directory-bottom">
                <span>
                  {t("近 7 天", "Past week")} · {item.recent_count}
                </span>
                <span
                  className={
                    item.trend === "up"
                      ? "up"
                      : item.trend === "down"
                        ? "down"
                        : "muted"
                  }
                >
                  {item.trend === "up" ? (
                    <TrendingUp size={14} />
                  ) : item.trend === "down" ? (
                    <TrendingDown size={14} />
                  ) : (
                    <Minus size={14} />
                  )}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
