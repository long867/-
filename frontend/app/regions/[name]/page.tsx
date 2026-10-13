import { RegionWorkspace } from "@/components/region-workspace";
import { serverApi } from "@/lib/server-api";
import type { ArticlePage } from "@/types";
export const revalidate = 300;
export default async function Page({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  return (
    <RegionWorkspace
      name={name}
      initial={await serverApi<ArticlePage>(
        `/regions/${encodeURIComponent(name)}/articles?page_size=10&exclude_prices=true`,
      )}
    />
  );
}
