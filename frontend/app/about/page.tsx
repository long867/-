"use client";
import { usePreferences } from "@/hooks/use-preferences";
import { SectionHeading } from "@/components/section-heading";
export default function About() {
  const { t } = usePreferences();
  return (
    <main className="small-page">
      <SectionHeading
        eyebrow="ABOUT MININGINTEL"
        zh="让矿产情报更有依据。"
        en="Mineral intelligence, grounded in evidence."
        description="全球矿产资源资讯聚合与咨询平台。"
        descriptionEn="Global mineral resources intelligence and consultation."
      />
      <div className="panel reading-content">
        <h2>
          {t(
            "从原始信源到可追溯的判断",
            "From original sources to traceable insight",
          )}
        </h2>
        <p>
          {t(
            "MiningIntel 采集新闻、政策、报价与公司公告，进行翻译、摘要、实体抽取和事件聚合。首页仅展示通过审核的已发布文章，并提供原文入口。",
            "MiningIntel collects news, policy, prices and company announcements, then translates, summarizes and organizes them. Published articles link directly to their original sources.",
          )}
        </p>
        <h2>{t("数据与引用", "Data and citations")}</h2>
        <p>
          {t(
            "报价保留原始产品、日期、币种、单位与来源，不能将碳酸锂现货报价等同于锂矿石价格。地图仅使用信源明确披露的项目坐标。AI 咨询依据检索片段生成答案；资料不足时会明确说明。",
            "Prices preserve their product, date, currency, unit and source. Lithium carbonate spot quotes do not represent lithium ore prices. Map markers require disclosed project coordinates. AI consultation cites retrieved evidence and states when evidence is insufficient.",
          )}
        </p>
        <h2>{t("收藏与订阅", "Bookmarks and subscriptions")}</h2>
        <p>
          {t(
            "收藏保存在当前浏览器，订阅偏好通过登录账号保存。离线页面用于提示网络状态，不展示缓存报价或私人对话。",
            "Bookmarks stay in this browser, while subscriptions are saved to your account. The offline page does not show stale prices or private conversations.",
          )}
        </p>
      </div>
    </main>
  );
}
