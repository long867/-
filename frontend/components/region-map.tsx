"use client";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import { useEffect } from "react";
import { usePreferences } from "@/hooks/use-preferences";
import type { ProjectLocation } from "@/types";
import { REGION_CENTERS } from "@/lib/resource-geography";
import "leaflet/dist/leaflet.css";
const centers: Record<string, [number, number]> = {
  中国: [35, 104],
  加拿大: [57, -106],
  美国: [39, -98],
  墨西哥: [23, -102],
  秘鲁: [-9, -75],
  阿根廷: [-35, -64],
  澳大利亚: [-25, 134],
  智利: [-30, -71],
  南非: [-29, 24],
  欧盟: [50, 10],
  巴西: [-14, -51],
  印度: [22, 79],
};
function Focus({
  points,
  center,
}: {
  points: ProjectLocation[];
  center: [number, number];
}) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1)
      map.fitBounds(
        points.map((p) => [p.latitude!, p.longitude!] as [number, number]),
        { padding: [40, 40], maxZoom: 9 },
      );
    else if (points.length === 1)
      map.setView([points[0].latitude!, points[0].longitude!], 6);
    else map.setView(center, 3);
    map.invalidateSize();
  }, [map, points, center]);
  return null;
}
export default function RegionMap({
  name,
  projects,
}: {
  name: string;
  projects: ProjectLocation[];
}) {
  const { theme, t } = usePreferences();
  const located = projects.filter(
    (item) => item.latitude !== null && item.longitude !== null,
  );
  const known = REGION_CENTERS[name];
  const center: [number, number] = known
    ? [known[1], known[0]]
    : centers[name] || [20, 0];
  return (
    <div className={`map-frame ${theme === "dark" ? "map-dark" : ""}`}>
      <MapContainer
        center={center}
        zoom={3}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%" }}
        aria-label={`${name} ${t("地区地图", "regional map")}`}
      >
        <TileLayer
          url={
            process.env.NEXT_PUBLIC_MAP_TILE_URL ||
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          }
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
        />
        <Focus points={located} center={center} />
        {located.map((project) => (
          <CircleMarker
            key={`${project.article_id}-${project.name}`}
            center={[project.latitude!, project.longitude!]}
            radius={7}
            pathOptions={{
              color: "#e0ab82",
              fillColor: "#e0ab82",
              fillOpacity: 0.7,
            }}
          >
            <Popup>
              <strong>{project.name}</strong>
              <br />
              <a href={project.url} target="_blank" rel="noopener noreferrer">
                {t("查看项目报道", "Read project coverage")}
              </a>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
