"use client";

import {
  useEffect,
  useRef,
  useState,
  type FocusEvent,
  type PointerEvent,
  type RefObject,
} from "react";
import { usePageMotion } from "./use-page-motion";

/** Advance only on screen and while the reader is not interacting with content. */
export function useAmbientCycle(
  surface: RefObject<HTMLElement>,
  advance: () => void,
  automatic: boolean,
  delay = 9000,
) {
  const { enabled } = usePageMotion();
  const action = useRef(advance);
  action.current = advance;
  const [visible, setVisible] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    const element = surface.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.12 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [surface]);
  const running = enabled && automatic && visible && !hovered && !focused;
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => action.current(), delay);
    return () => clearInterval(timer);
  }, [running, delay]);
  return {
    running,
    visible,
    interactionProps: {
      onPointerEnter: (event: PointerEvent<HTMLElement>) => {
        if (event.pointerType === "mouse") setHovered(true);
      },
      onPointerLeave: () => setHovered(false),
      onFocusCapture: () => setFocused(true),
      onBlurCapture: (event: FocusEvent<HTMLElement>) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setFocused(false);
      },
    },
  };
}
