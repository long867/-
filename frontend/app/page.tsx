import { HomeDashboard, type HomeData } from "@/components/home-dashboard";
import { serverApi } from "@/lib/server-api";
import { HomeHero } from "@/components/home-hero";
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
  ];
  const keys = [
    "articles",
    "hot",
    "facets",
    "sources",
    "minerals",
    "alerts",
    "policies",
  ] as const;
  const values = await Promise.all(paths.map((path) => serverApi(path)));
  const initial = Object.fromEntries(
    keys.map((key, index) => [key, values[index]]),
  ) as HomeData;
  const { sources, ...dashboardData } = initial;
  return (
    <main className="workspace">
      <HomeHero
        articleCount={initial.articles?.total}
        sourceCount={sources?.length}
      />
      <HomeDashboard initial={dashboardData} />
    </main>
  );
}
