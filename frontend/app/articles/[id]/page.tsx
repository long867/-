import { ArticleDetail } from "@/components/article-detail";
import { notFound } from "next/navigation";
import type { Article } from "@/types";
export const dynamic = "force-dynamic";
export default async function Detail({ params }: { params: { id: string } }) {
  let initial: Article | undefined;
  let missing = false;
  try {
    const response = await fetch(
      `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8001"}/api/articles/${params.id}`,
      { cache: "no-store", signal: AbortSignal.timeout(2500) },
    );
    missing = response.status === 404;
    if (response.ok) initial = (await response.json()) as Article;
  } catch {
    /* Client offers an explicit retry when the API is unavailable. */
  }
  if (missing) notFound();
  return <ArticleDetail id={params.id} initial={initial} />;
}
