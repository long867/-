import { MineralMarketPage } from "@/components/mineral-market";
import { Suspense } from "react";
import { serverApi } from "@/lib/server-api";
import type { MineralMarket } from "@/types";
export const revalidate = 300;
export default async function Page() {
  return (
    <Suspense>
      <MineralMarketPage
        initial={await serverApi<MineralMarket>("/minerals/market")}
      />
    </Suspense>
  );
}
