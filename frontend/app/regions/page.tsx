import { Suspense } from "react";
import { CountryWatch } from "@/components/country-watch";
import { serverApi } from "@/lib/server-api";
import type { CountryMonitor } from "@/types";
export const revalidate = 300;
export default async function Page() {
  return (
    <Suspense>
      <CountryWatch
        initial={await serverApi<CountryMonitor>("/regions/monitor")}
      />
    </Suspense>
  );
}
