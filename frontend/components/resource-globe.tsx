"use client";

import { useEffect, useRef } from "react";
import { WORLD_LAND } from "@/lib/world-land";
import { REGION_CENTERS } from "@/lib/resource-geography";
import type { Facet } from "@/types";

type Point = { x: number; y: number; z: number };
type Hit = { x: number; y: number; region: Facet };
const RAD = Math.PI / 180;
const LAND = WORLD_LAND.split("Z").map((polygon) =>
  [...polygon.matchAll(/[ML](-?[\d.]+),(-?[\d.]+)/g)].map((point) => [
    Number(point[1]) / 2 - 180,
    85 - Number(point[2]) / 2,
  ]),
);

function project(lon: number, lat: number, angle: number, tilt: number): Point {
  const latitude = lat * RAD;
  const longitude = lon * RAD - angle;
  const x = Math.cos(latitude) * Math.sin(longitude);
  const y = Math.sin(latitude);
  const z = Math.cos(latitude) * Math.cos(longitude);
  return {
    x,
    y: y * Math.cos(tilt) - z * Math.sin(tilt),
    z: y * Math.sin(tilt) + z * Math.cos(tilt),
  };
}

/** Project real country centers; particles decorate coverage, never imply live trades. */
export function ResourceGlobe({
  regions,
  focus,
  onSelect,
}: {
  regions: Facet[];
  focus: string;
  onSelect: (region: string) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const camera = useRef({
    angle: -65 * RAD,
    tilt: 0.22,
    target: null as number | null,
  });
  const selected = useRef(focus);
  const selection = useRef(onSelect);
  const hits = useRef<Hit[]>([]);
  const dragging = useRef({ active: false, x: 0, y: 0, distance: 0 });
  const drawNow = useRef<() => void>(() => {});
  selected.current = focus;
  selection.current = onSelect;

  useEffect(() => {
    const center = REGION_CENTERS[focus];
    if (center) {
      const current = camera.current.angle;
      const target = center[0] * RAD;
      camera.current.target =
        current +
        Math.atan2(Math.sin(target - current), Math.cos(target - current));
      drawNow.current();
    }
  }, [focus]);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext("2d", { alpha: true });
    if (!element || !context) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const points = regions.filter((region) => REGION_CENTERS[region.name]);
    let width = 600,
      height = 420,
      frame = 0,
      last = 0,
      visible = true,
      ready = false;
    let paused = document.documentElement.dataset.motion === "paused";
    let light = document.documentElement.dataset.theme === "light";
    let elapsed = 0;

    function path(values: Point[], close = false) {
      let active = false;
      context!.beginPath();
      for (const point of values) {
        if (point.z < 0) {
          active = false;
          continue;
        }
        const x = width / 2 + point.x * radius();
        const y = height / 2 - point.y * radius();
        if (active) context!.lineTo(x, y);
        else context!.moveTo(x, y);
        active = true;
      }
      if (close) context!.closePath();
    }
    function radius() {
      return Math.min(width * 0.36, height * 0.43);
    }
    function draw() {
      const ctx = context!;
      const r = radius(),
        cx = width / 2,
        cy = height / 2;
      const { angle, tilt } = camera.current;
      ctx.clearRect(0, 0, width, height);
      const atmosphere = ctx.createRadialGradient(
        cx,
        cy,
        r * 0.85,
        cx,
        cy,
        r * 1.38,
      );
      atmosphere.addColorStop(0, light ? "#46738615" : "#4894af28");
      atmosphere.addColorStop(0.62, light ? "#b6954820" : "#ad8a4e12");
      atmosphere.addColorStop(1, "#00000000");
      ctx.fillStyle = atmosphere;
      ctx.fillRect(0, 0, width, height);

      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-0.35);
      ctx.strokeStyle = light ? "#876c4935" : "#cfad7548";
      ctx.lineWidth = 0.7;
      ctx.beginPath();
      ctx.ellipse(0, 0, r * 1.38, r * 0.48, 0, 0, Math.PI * 2);
      ctx.stroke();
      const satellite = elapsed * 0.3;
      ctx.fillStyle = light ? "#875a28" : "#f1cf92";
      ctx.beginPath();
      ctx.arc(
        Math.cos(satellite) * r * 1.38,
        Math.sin(satellite) * r * 0.48,
        2.4,
        0,
        Math.PI * 2,
      );
      ctx.fill();
      ctx.restore();

      const ocean = ctx.createRadialGradient(
        cx - r * 0.35,
        cy - r * 0.4,
        0,
        cx + r * 0.2,
        cy + r * 0.1,
        r * 1.3,
      );
      ocean.addColorStop(0, light ? "#d8e6e4" : "#203c50");
      ocean.addColorStop(0.55, light ? "#cedbd8" : "#0d2335");
      ocean.addColorStop(1, light ? "#adc0bf" : "#030d17");
      ctx.fillStyle = ocean;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.save();
      ctx.clip();
      ctx.strokeStyle = light ? "#50797d35" : "#729aab38";
      ctx.lineWidth = 0.55;
      for (let lat = -60; lat <= 60; lat += 20) {
        path(
          Array.from({ length: 121 }, (_, index) =>
            project(index * 3 - 180, lat, angle, tilt),
          ),
        );
        ctx.stroke();
      }
      for (let lon = -180; lon < 180; lon += 25) {
        path(
          Array.from({ length: 61 }, (_, index) =>
            project(lon, index * 3 - 90, angle, tilt),
          ),
        );
        ctx.stroke();
      }
      const land = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r);
      land.addColorStop(0, light ? "#b19a66" : "#a49369");
      land.addColorStop(0.55, light ? "#66837b" : "#41666b");
      land.addColorStop(1, light ? "#57747a" : "#213e50");
      ctx.fillStyle = land;
      ctx.strokeStyle = light ? "#7b775a70" : "#d0bd8970";
      ctx.lineWidth = 0.65;
      for (const polygon of LAND) {
        if (polygon.length < 3) continue;
        const projected = polygon.map(([lon, lat]) =>
          project(lon, lat, angle, tilt),
        );
        if (!projected.some((point) => point.z >= 0)) continue;
        path(projected, true);
        ctx.fill();
        ctx.stroke();
      }
      ctx.strokeStyle = light ? "#8f73355c" : "#f2c98660";
      const scan = Math.sin(elapsed * 0.18) * 55;
      path(
        Array.from({ length: 121 }, (_, index) =>
          project(index * 3 - 180, scan, angle, tilt),
        ),
      );
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();
      ctx.strokeStyle = light ? "#6f8d8475" : "#82b5c760";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();

      const origin = REGION_CENTERS[selected.current];
      if (origin) {
        const destinations = points
          .filter((region) => region.name !== selected.current)
          .slice(0, 8);
        for (const [index, region] of destinations.entries()) {
          const destination = REGION_CENTERS[region.name];
          const delta = ((destination[0] - origin[0] + 540) % 360) - 180;
          const route = Array.from({ length: 41 }, (_, step) => {
            const progress = step / 40;
            const point = project(
              origin[0] + delta * progress,
              origin[1] + (destination[1] - origin[1]) * progress,
              angle,
              tilt,
            );
            const lift = 1 + Math.sin(progress * Math.PI) * 0.12;
            return { ...point, x: point.x * lift, y: point.y * lift };
          });
          path(route);
          ctx.strokeStyle = light ? "#95724255" : "#ddba7854";
          ctx.lineWidth = 0.7;
          ctx.stroke();
          const position = Math.floor(((elapsed * 0.12 + index / 8) % 1) * 40);
          const beacon = route[position];
          if (beacon.z > 0.08) {
            ctx.fillStyle = light ? "#90652b" : "#fae1ac";
            ctx.beginPath();
            ctx.arc(cx + beacon.x * r, cy - beacon.y * r, 1.7, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
      hits.current = [];
      for (const region of points) {
        const [lon, lat] = REGION_CENTERS[region.name];
        const point = project(lon, lat, angle, tilt);
        if (point.z < 0.08) continue;
        const x = cx + point.x * r,
          y = cy - point.y * r;
        const active = region.name === selected.current;
        const size = active
          ? 4.6
          : Math.min(4.2, 2 + Math.log1p(region.count) * 0.27);
        const pulse = (elapsed * 0.27 + lon / 360 + 1) % 1;
        ctx.beginPath();
        ctx.arc(x, y, size + 4 + pulse * 12, 0, Math.PI * 2);
        ctx.strokeStyle = light
          ? `rgba(139,95,37,${(1 - pulse) * 0.35})`
          : `rgba(235,188,116,${(1 - pulse) * 0.4})`;
        ctx.lineWidth = 0.7;
        ctx.stroke();
        ctx.fillStyle = light ? "#825326" : "#f5cb8b";
        ctx.shadowColor = light ? "transparent" : "#ecc47b";
        ctx.shadowBlur = active ? 12 : 6;
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = light ? "#fff5d8" : "#fff3d8";
        ctx.beginPath();
        ctx.arc(x, y, 1.3, 0, Math.PI * 2);
        ctx.fill();
        hits.current.push({ x, y, region });
      }
      element!.dataset.angle = angle.toFixed(4);
      if (!ready) {
        ready = true;
        element!.dataset.ready = "true";
      }
    }
    function tick(now: number) {
      frame = requestAnimationFrame(tick);
      if (now - last < (width < 430 ? 50 : 33) || !visible || document.hidden)
        return;
      const step = Math.min((now - last) / 1000 || 0.033, 0.08);
      last = now;
      const target = camera.current.target;
      if (target !== null) {
        camera.current.angle +=
          (target - camera.current.angle) *
          (reduced.matches || paused ? 1 : 0.07);
        if (Math.abs(target - camera.current.angle) < 0.002)
          camera.current.target = null;
      } else if (!paused && !reduced.matches && !dragging.current.active) {
        camera.current.angle += step * 0.065;
      }
      if (!paused && !reduced.matches) elapsed += step;
      if ((!paused && !reduced.matches) || target !== null) draw();
    }
    const resize = new ResizeObserver(() => {
      const bounds = element.getBoundingClientRect();
      width = bounds.width;
      height = bounds.height;
      const ratio = Math.min(
        window.devicePixelRatio || 1,
        width < 430 ? 1.25 : 1.5,
      );
      element.width = Math.round(width * ratio);
      element.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw();
    });
    const appearance = new MutationObserver(() => {
      paused = document.documentElement.dataset.motion === "paused";
      light = document.documentElement.dataset.theme === "light";
      draw();
    });
    const visibility = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    resize.observe(element);
    visibility.observe(element);
    appearance.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-motion", "data-theme"],
    });
    drawNow.current = draw;
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      appearance.disconnect();
      visibility.disconnect();
      drawNow.current = () => {};
    };
  }, [regions]);

  return (
    <canvas
      ref={canvas}
      className="resource-globe"
      aria-label="可拖动旋转的全球报道覆盖地球 / Rotatable published coverage globe"
      role="img"
      onPointerDown={(event) => {
        dragging.current = {
          active: true,
          x: event.clientX,
          y: event.clientY,
          distance: 0,
        };
        event.currentTarget.setPointerCapture(event.pointerId);
        camera.current.target = null;
      }}
      onPointerMove={(event) => {
        if (!dragging.current.active) return;
        const delta = event.clientX - dragging.current.x;
        camera.current.angle -= delta * 0.007;
        if (event.pointerType !== "touch")
          camera.current.tilt = Math.max(
            -0.65,
            Math.min(
              0.65,
              camera.current.tilt +
                (event.clientY - dragging.current.y) * 0.005,
            ),
          );
        dragging.current.distance +=
          Math.abs(delta) + Math.abs(event.clientY - dragging.current.y);
        dragging.current.x = event.clientX;
        dragging.current.y = event.clientY;
        drawNow.current();
      }}
      onPointerUp={(event) => {
        if (dragging.current.distance < 8) {
          const bounds = event.currentTarget.getBoundingClientRect();
          const hit = hits.current.find(
            (point) =>
              Math.hypot(
                point.x - event.clientX + bounds.left,
                point.y - event.clientY + bounds.top,
              ) < 15,
          );
          if (hit) selection.current(hit.region.name);
        }
        dragging.current.active = false;
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={() => {
        dragging.current.active = false;
      }}
    />
  );
}
