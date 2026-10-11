import { MineralWorkspace } from "@/components/mineral-workspace";
import { serverApi } from "@/lib/server-api";
import type { ArticlePage } from "@/types";
export const revalidate = 300;
export default async function Page({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  return (
    <MineralWorkspace
      name={name}
      initial={await serverApi<ArticlePage>(
        `/articles?mineral=${encodeURIComponent(name)}&page_size=10`,
      )}
    />
  );
}
