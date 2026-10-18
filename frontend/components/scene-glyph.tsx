"use client";

import { usePathname } from "next/navigation";
import { pageScene } from "@/lib/page-scene.mjs";

/** Lightweight decorative SVG; no synthetic statistics, locations or forecasts. */
export function SceneGlyph({ className = "" }: { className?: string }) {
  const scene = pageScene(usePathname());
  return (
    <div
      className={`scene-glyph scene-glyph-${scene} ${className}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 200 160" fill="none" focusable="false">
        <g className="glyph-orbit glyph-orbit-outer">
          <circle
            cx="100"
            cy="80"
            r="70"
            stroke="currentColor"
            strokeDasharray="2 10"
          />
        </g>
        <g className="glyph-orbit glyph-orbit-inner">
          <ellipse
            cx="100"
            cy="80"
            rx="86"
            ry="52"
            stroke="currentColor"
            strokeDasharray="32 28 2 12"
          />
        </g>
        {scene === "crystal" || scene === "observatory" ? (
          <g className="glyph-core">
            <path
              d="M100 25 138 52 150 109 100 139 50 109 62 52Z"
              fill="currentColor"
              fillOpacity=".06"
            />
            <path
              className="glyph-draw"
              d="M100 25 138 52 150 109 100 139 50 109 62 52 100 25 100 139M62 52 100 67 138 52M50 109 100 67 150 109"
              stroke="currentColor"
              strokeWidth="1.4"
            />
            <circle
              cx="100"
              cy="67"
              r="4"
              fill="currentColor"
              className="glyph-beacon"
            />
          </g>
        ) : scene === "atlas" || scene === "network" ? (
          <g>
            <circle cx="100" cy="80" r="51" stroke="currentColor" />
            <ellipse cx="100" cy="80" rx="25" ry="51" stroke="currentColor" />
            <ellipse cx="100" cy="80" rx="51" ry="20" stroke="currentColor" />
            <path
              d="M49 80H151M100 29V131"
              stroke="currentColor"
              strokeOpacity=".4"
            />
            <path
              className="glyph-flow"
              d="M59 105Q96 3 145 65M64 49Q96 131 141 105"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray="12 60"
            />
            <circle
              cx="64"
              cy="49"
              r="4"
              fill="currentColor"
              className="glyph-beacon"
            />
            <circle cx="141" cy="105" r="3" fill="currentColor" />
          </g>
        ) : scene === "policy" || scene === "brief" ? (
          <g className="glyph-core">
            <path
              d="M58 50 45 56V129H128V120M69 38 57 44V118H140V110M71 28H125L151 54V107H71Z"
              stroke="currentColor"
              fill="currentColor"
              fillOpacity=".025"
            />
            <path
              d="M124 29V55H150M85 72H135M85 83H128M85 94H116"
              stroke="currentColor"
            />
            <path
              className="glyph-flow"
              d="M85 60H115M85 72H135M85 83H128M85 94H116"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeDasharray="16 55"
            />
          </g>
        ) : scene === "signals" || scene === "operations" ? (
          <g>
            <path
              d="M44 38V124H159M44 97H158M44 69H158"
              stroke="currentColor"
              strokeOpacity=".35"
            />
            <path
              className="glyph-draw"
              d="M45 111 67 89 87 98 110 61 130 73 156 42"
              stroke="currentColor"
              strokeWidth="2"
            />
            <path
              className="glyph-flow"
              d="M45 111 67 89 87 98 110 61 130 73 156 42"
              stroke="currentColor"
              strokeWidth="4"
              strokeDasharray="3 55"
            />
            <circle
              cx="110"
              cy="61"
              r="5"
              className="glyph-beacon"
              fill="currentColor"
            />
          </g>
        ) : scene === "radar" ? (
          <g>
            {[20, 40, 60].map((r) => (
              <circle
                key={r}
                cx="100"
                cy="80"
                r={r}
                stroke="currentColor"
                strokeOpacity=".45"
              />
            ))}
            <path
              d="M100 19V141M39 80H161"
              stroke="currentColor"
              strokeOpacity=".3"
            />
            <g className="glyph-orbit">
              <path
                d="M100 80 100 20A60 60 0 0 1 160 80Z"
                fill="currentColor"
                fillOpacity=".12"
              />
              <path d="M100 80 100 20" stroke="currentColor" strokeWidth="2" />
            </g>
            <circle
              cx="125"
              cy="56"
              r="4"
              fill="currentColor"
              className="glyph-beacon"
            />
          </g>
        ) : (
          <g>
            <path
              className="glyph-draw"
              d="M100 30 145 55 145 105 100 130 55 105 55 55ZM100 30V80L145 105M55 105 100 80 145 55M55 55 100 80 100 130"
              stroke="currentColor"
            />
            <path
              className="glyph-flow"
              d="M100 30V80L145 105 145 55 100 80 55 105 55 55 100 30"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeDasharray="8 80"
            />
            {[
              [100, 30],
              [145, 55],
              [145, 105],
              [100, 130],
              [55, 105],
              [55, 55],
              [100, 80],
            ].map(([x, y], i) => (
              <circle
                key={i}
                cx={x}
                cy={y}
                r={i === 6 ? 6 : 3}
                fill="currentColor"
                className={i === 6 ? "glyph-beacon" : ""}
              />
            ))}
          </g>
        )}
      </svg>
    </div>
  );
}
