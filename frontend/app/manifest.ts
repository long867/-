import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MiningIntel 全球矿产情报",
    short_name: "MiningIntel",
    description: "矿业政策、市场与产业情报",
    start_url: "/",
    display: "standalone",
    background_color: "#0b111c",
    theme_color: "#0b111c",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
  };
}
