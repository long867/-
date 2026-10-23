import { HomeDashboard, type HomeData } from "@/components/home-dashboard";
import { serverApi } from "@/lib/server-api";
import { HomeHero } from "@/components/home-hero";
import { unstable_noStore } from "next/cache";
export const revalidate = 300;
export default async function Page() {
  const paths = [
    "/articles?page_size=2",
    "/articles/hot",
    "/facets",
    "/sources",
    "/trends/hot-minerals",
    "/trends/price-alerts",
    "/trends/policy-updates",
    "/minerals/%E9%94%82/prices",
    "/articles?page_size=3&sort_by=quality_score",
    "/minerals/market",
    "/articles?page_size=6&exclude_prices=true",
    "/articles?page_size=4&category=report&exclude_prices=true",
  ];
  const keys = [
    "articles",
    "hot",
    "facets",
    "sources",
    "minerals",
    "alerts",
    "policies",
    "prices",
    "featured",
    "market",
    "desk",
    "papers",
  ] as const;
  const values = await Promise.all(paths.map((path) => serverApi(path)));
  const initial = Object.fromEntries(
    keys.map((key, index) => [key, values[index]]),
  ) as HomeData;
  const { sources, ...dashboardData } = initial;
  // Image builds have no API connection. Never cache their unavailable state.
  // Successful API reads still retain their five-minute data revalidation.
  if (!initial.articles || !initial.facets) unstable_noStore();
  return (
    <main className="workspace mineral-observatory">
      <HomeHero
        articleCount={initial.articles?.total}
        sourceCount={sources?.length}
        facets={initial.facets}
      />
      <HomeDashboard initial={dashboardData} />
    </main>
  );
}
