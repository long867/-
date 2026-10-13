"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { MapPin } from "lucide-react";
import { ArticleFeed } from "./article-feed";
import { CountryBrief } from "./country-brief";
import { PolicyCard } from "./policy-card";
import { SectionHeading } from "./section-heading";
import { SubscriptionDialog } from "./subscription-dialog";
import { usePreferences } from "@/hooks/use-preferences";
import { publicApi } from "@/lib/api";
import { ErrorState, SkeletonCards } from "./ui/states";
import type { ArticlePage, ProjectLocation, PolicyPage } from "@/types";
const RegionMap = dynamic(() => import("./region-map"), {
  ssr: false,
  loading: () => <SkeletonCards count={2} />,
});
export function RegionWorkspace({
  name,
  initial,
}: {
  name: string;
  initial?: ArticlePage;
}) {
  const { t } = usePreferences();
  const projects = useQuery({
    queryKey: ["region-projects", name],
    queryFn: () =>
      publicApi<ProjectLocation[]>(
        `/regions/${encodeURIComponent(name)}/projects`,
      ),
  });
  const policies = useQuery({
    queryKey: ["region-policies", name],
    queryFn: () =>
      publicApi<PolicyPage>(`/policies?region=${encodeURIComponent(name)}`),
  });
  return (
    <main className="workspace">
      <SectionHeading
        eyebrow="REGIONAL RESOURCE INTELLIGENCE"
        zh={`${name} · 国家资源动向`}
        en={`${name} · Regional intelligence`}
        description="资源、项目与政策，在地理视角下连接。"
        descriptionEn="Connect resources, projects and policy through a regional lens."
        actions={<SubscriptionDialog region={name} />}
      />
      <CountryBrief name={name} />
      {projects.isPending ? (
        <SkeletonCards count={2} />
      ) : projects.isError ? (
        <ErrorState error={projects.error} retry={() => projects.refetch()} />
      ) : (
        <RegionMap name={name} projects={projects.data} />
      )}
      <p className="map-caption">
        <MapPin size={12} />
        {projects.data?.filter((p) => p.latitude !== null).length || 0}{" "}
        {t("个项目有来源坐标", "projects with source coordinates")} ·{" "}
        {projects.data?.length || 0}{" "}
        {t(
          "个已提取项目。地图仅标注信源提供的位置。",
          "extracted projects. Only source-provided positions are marked.",
        )}
      </p>
      <div className="dashboard">
        <ArticleFeed region={name} initial={initial} excludePrices />
        <aside>
          <section className="panel">
            <h2 className="panel-title">{t("项目观察", "Project watch")}</h2>
            {projects.data?.map((item) => (
              <div className="insight-row" key={item.name}>
                <Link href={`/articles/${item.article_id}`}>
                  {item.name}
                  <small className="block text-muted mt-1">
                    {item.latitude === null
                      ? t("位置待补充", "Location not provided")
                      : t("来源坐标已标注", "Source position mapped")}
                  </small>
                </Link>
              </div>
            ))}
            {!projects.data?.length && (
              <p className="subtitle text-xs">
                {t(
                  "暂无已提取的项目资料。",
                  "No project records extracted yet.",
                )}
              </p>
            )}
          </section>
          <section className="panel">
            <h2 className="panel-title">{t("地区政策", "Regional policy")}</h2>
            {policies.data?.items.length ? (
              policies.data.items.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} />
              ))
            ) : (
              <p className="subtitle text-xs">
                {t(
                  "暂无已发布的相关政策。",
                  "No published regional policies yet.",
                )}
              </p>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
