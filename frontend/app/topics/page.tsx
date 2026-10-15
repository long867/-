import type { Metadata } from "next";
import { TopicWorkspace } from "@/components/topic-workspace";
import "./topics.css";

export const metadata: Metadata = {
  title: "选题推荐 · MiningIntel",
  description:
    "基于矿产资讯与研究成果的账号专属选题工作台，提供原文证据与研究建议。",
  robots: { index: false, follow: false },
};

export default function Topics() {
  return <TopicWorkspace />;
}
