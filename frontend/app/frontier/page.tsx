import type { Metadata } from "next";
import { FrontierWorkspace } from "@/components/frontier-workspace";
import { frontierFilters, frontierParams } from "@/lib/frontier";
import { serverApi } from "@/lib/server-api";
import type { FrontierPage } from "@/types/frontier";

export const metadata: Metadata = {
  title: "前沿成果",
  description:
    "追踪全球矿产资源最新研究：中文摘要、研究方向、作者与期刊，保留 DOI 和原文证据。",
};
export const dynamic = "force-dynamic";

export default async function Frontier({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const filters = frontierFilters(searchParams);
  const initial = await serverApi<FrontierPage>(
    `/frontier?${frontierParams(filters)}`,
  );
  return <FrontierWorkspace initial={initial} initialFilters={filters} />;
}
