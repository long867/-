import { serverApi } from "@/lib/server-api";
import { TrendWorkspace } from "@/components/trend-workspace";
import type { Insights, PolicyUpdate } from "@/types";
export const revalidate = 300;
export default async function Trends() {
  const [hot, alerts, policies] = await Promise.all([
    serverApi<Insights["hotspots"]>("/trends/hot-minerals"),
    serverApi<Insights["price_alerts"]>("/trends/price-alerts"),
    serverApi<PolicyUpdate[]>("/trends/policy-updates"),
  ]);
  return <TrendWorkspace initial={{ hot, alerts, policies }} />;
}
