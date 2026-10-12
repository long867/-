import { ResearchWorkspace } from "@/components/research-workspace";
import { serverApi } from "@/lib/server-api";
import type { ResearchResult } from "@/types/research";

export const dynamic = "force-dynamic";

export default async function Research({
  searchParams,
}: {
  searchParams: { mineral?: string; region?: string };
}) {
  const params = new URLSearchParams();
  const mineral =
    typeof searchParams.mineral === "string"
      ? searchParams.mineral.slice(0, 100)
      : "";
  const region =
    typeof searchParams.region === "string"
      ? searchParams.region.slice(0, 100)
      : "";
  if (mineral) params.set("mineral", mineral);
  if (region) params.set("region", region);
  return (
    <ResearchWorkspace
      initialScope={{ mineral, region }}
      initial={await serverApi<ResearchResult>(`/research/overview?${params}`)}
    />
  );
}
