"use client";

import { useEffect, useState } from "react";

/** The clock is independent of lazy visualization modules and coverage statistics. */
export function ObservatoryClock() {
  const [time, setTime] = useState("—:—:—");
  useEffect(() => {
    const update = () =>
      setTime(
        new Intl.DateTimeFormat("en-GB", {
          timeZone: "Asia/Shanghai",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hourCycle: "h23",
        }).format(new Date()),
      );
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="observatory-clock">
      <span>BJT</span> <time suppressHydrationWarning>{time}</time>
    </span>
  );
}
