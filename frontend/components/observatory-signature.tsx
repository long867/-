import Link from "next/link";
import { ArrowUpRight, Orbit, Gem, ScanLine, BrainCircuit } from "lucide-react";
import { Locale } from "./locale";

/** Geological line work is decorative; it does not depict measured deposits. */
export function ObservatorySignature() {
  return (
    <div className="observatory-signature" aria-hidden="true">
      <div className="signature-light" />
      <svg
        viewBox="0 0 1400 600"
        fill="none"
        preserveAspectRatio="xMidYMax slice"
      >
        <defs>
          <linearGradient
            id="signature-vein"
            x1="0"
            y1="600"
            x2="1400"
            y2="0"
            gradientUnits="userSpaceOnUse"
          >
            <stop stopColor="#d8ac6a" stopOpacity=".02" />
            <stop offset=".45" stopColor="#edcf92" stopOpacity=".65" />
            <stop offset="1" stopColor="#73c5d5" stopOpacity=".08" />
          </linearGradient>
        </defs>
        <g className="signature-strata" stroke="url(#signature-vein)">
          {[0, 1, 2, 3, 4, 5, 6].map((i) => (
            <path
              key={i}
              d={`M-40 ${510 + i * 18} 160 ${430 + i * 15} 310 ${475 + i * 13} 480 ${340 + i * 17} 650 ${415 + i * 15} 890 ${235 + i * 20} 1050 ${330 + i * 13} 1260 ${190 + i * 17} 1460 ${275 + i * 20}`}
            />
          ))}
          <path
            d="M160 430 190 580M310 475 340 590M480 340 520 580M650 415 680 590M890 235 930 600M1050 330 1080 570M1260 190 1295 590"
            strokeOpacity=".5"
          />
        </g>
        <path
          className="signature-flow"
          d="M-40 510 160 430 310 475 480 340 650 415 890 235 1050 330 1260 190 1460 275"
          stroke="url(#signature-vein)"
          strokeWidth="2"
          strokeDasharray="24 240"
        />
        <g className="signature-nodes" fill="#e7c489">
          <circle cx="480" cy="340" r="3" />
          <circle cx="890" cy="235" r="3" />
          <circle cx="1260" cy="190" r="3" />
        </g>
      </svg>
    </div>
  );
}

const destinations = [
  {
    href: "/minerals",
    icon: Gem,
    code: "MARKET",
    zh: "矿产行情",
    en: "Mineral markets",
    detail: "多矿种报价 · 产业脉搏",
    detailEn: "Daily quotes. Industry signals.",
  },
  {
    href: "/regions",
    icon: Orbit,
    code: "WORLD",
    zh: "全球动向",
    en: "Country intelligence",
    detail: "国家政策 · 全球资源格局",
    detailEn: "Policy shifts. Global resources.",
  },
  {
    href: "/frontier",
    icon: ScanLine,
    code: "FRONTIER",
    zh: "研究前沿",
    en: "Research frontiers",
    detail: "前沿成果 · 发现研究线索",
    detailEn: "New findings. Research directions.",
  },
  {
    href: "/chat",
    icon: BrainCircuit,
    code: "INSIGHT",
    zh: "矿眸智探",
    en: "矿眸智探",
    detail: "多轮分析 · 原文证据溯源",
    detailEn: "In-depth analysis. Original evidence.",
  },
];

/** Direct routes into existing tools; no extra requests or invented live signals. */
export function ObservatoryDestinations() {
  return (
    <nav
      className="observatory-destinations"
      aria-label="探索矿产研究工具 / Explore intelligence tools"
    >
      {destinations.map((item, index) => (
        <Link
          className="destination-card"
          key={item.code}
          href={item.href}
          prefetch={false}
        >
          <span className="destination-icon">
            <item.icon size={24} strokeWidth={1.3} />
          </span>
          <span className="destination-copy">
            <span className="destination-code">
              0{index + 1} / {item.code}
            </span>
            <strong>
              <Locale zh={item.zh} en={item.en} />
            </strong>
            <span className="destination-detail">
              <Locale zh={item.detail} en={item.detailEn} />
            </span>
          </span>
          <ArrowUpRight className="destination-arrow" size={17} />
        </Link>
      ))}
    </nav>
  );
}
