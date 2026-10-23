import type { Metadata, Viewport } from "next";
import { Providers } from "./providers";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { PwaRegister } from "@/components/pwa-register";
import { AssistantDock } from "@/components/assistant-dock";
import { SiteExperience } from "@/components/site-experience";
import { ReadingTools } from "@/components/reading-tools";
import { WorkspaceRibbon } from "@/components/workspace-tools";
import { PageOutline } from "@/components/page-outline";
import "./fonts.css";
import "./globals.css";
import "./mineral-design.css";
import "./mineral-luxe.css";
import "./readability.css";
import "./mobile.css";
import "./country-watch.css";
import "./frontier.css";
import "./experience.css";
import "./cinematic.css";
import "./studio.css";
import "./workbench.css";
import "./immersive.css";
export const metadata: Metadata = {
  title: {
    default: "MiningIntel · 全球矿产情报",
    template: "%s · MiningIntel",
  },
  description:
    "全球矿产政策、市场与产业情报。追踪真实来源，用证据回答每一个问题。",
  applicationName: "MiningIntel",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg", apple: "/icon-192.png" },
  appleWebApp: { capable: true, statusBarStyle: "black-translucent" },
};
export const viewport: Viewport = {
  themeColor: "#0b111c",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};
const preferencesScript =
  "try{document.documentElement.dataset.theme=localStorage.getItem('mi-theme')==='light'?'light':'dark';document.documentElement.lang=localStorage.getItem('mi-language')==='en'?'en':'zh-CN';document.documentElement.dataset.motion=localStorage.getItem('mi-motion')==='paused'?'paused':'running';document.documentElement.dataset.readingSize=localStorage.getItem('mi-reading-size')==='large'?'large':'standard';document.documentElement.dataset.density=localStorage.getItem('mi-density')==='compact'?'compact':'comfortable'}catch(e){}";
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="zh-CN"
      data-theme="dark"
      data-visuals="off"
      suppressHydrationWarning
    >
      <head>
        <link
          rel="preload"
          as="font"
          href="/fonts/miningintel-display.woff2"
          media="(min-width: 801px)"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <script dangerouslySetInnerHTML={{ __html: preferencesScript }} />
      </head>
      <body>
        <a href="#main-content" className="skip-link">
          跳转到内容 / Skip to content
        </a>
        <Providers>
          <Header />
          <WorkspaceRibbon />
          <ReadingTools />
          <PageOutline />
          <div id="main-content">
            <SiteExperience>{children}</SiteExperience>
          </div>
          <Footer />
          <AssistantDock />
          <PwaRegister />
        </Providers>
      </body>
    </html>
  );
}
