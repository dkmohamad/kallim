"use client";

import { useEffect, useRef } from "react";
import type { Line } from "@/lib/lines";

/** How long a manual scroll suspends following the active line. */
const FOLLOW_PAUSE_MS = 5000;

export function Transcript({
  lines,
  active,
  follow,
  showEnglish,
  onJump,
}: {
  lines: readonly Line[];
  active: number | undefined;
  follow: boolean; // only while playing, so loading the page never scrolls it
  showEnglish: boolean;
  onJump: (line: Line) => void;
}) {
  const rows = useRef(new Map<number, HTMLButtonElement>());
  const lastManualScroll = useRef(0);

  useEffect(() => {
    const mark = () => {
      lastManualScroll.current = Date.now();
    };
    window.addEventListener("wheel", mark, { passive: true });
    window.addEventListener("touchmove", mark, { passive: true });
    return () => {
      window.removeEventListener("wheel", mark);
      window.removeEventListener("touchmove", mark);
    };
  }, []);

  useEffect(() => {
    if (!follow || active === undefined) return;
    if (Date.now() - lastManualScroll.current < FOLLOW_PAUSE_MS) return;
    rows.current.get(active)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [active, follow]);

  return (
    <ol className="mt-4 space-y-1">
      {lines.map((line, i) => (
        <li key={line.n}>
          {line.section !== lines[i - 1]?.section && line.section && (
            <h3 lang="ar" dir="rtl" className="ar font-arabic mt-5 mb-1 border-b border-neutral-300 text-lg font-semibold">
              {line.section}
            </h3>
          )}
          <button
            type="button"
            ref={(el) => {
              if (el) rows.current.set(line.n, el);
              else rows.current.delete(line.n);
            }}
            onClick={() => onJump(line)}
            aria-current={line.n === active ? "true" : undefined}
            className="block w-full scroll-my-40 rounded-md px-2 py-1 text-left hover:bg-neutral-100 aria-[current]:bg-blue-50 aria-[current]:outline aria-[current]:outline-blue-700"
          >
            <span lang="ar" dir="rtl" className="ar font-arabic block text-right text-lg">
              {line.ar}
            </span>
            {showEnglish && <span className="block text-sm text-neutral-600">{line.en}</span>}
          </button>
        </li>
      ))}
    </ol>
  );
}
