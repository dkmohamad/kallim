import { describe, expect, it } from "vitest";
import type { Line } from "../src/lib/lines";
import { Timeline } from "../src/lib/timeline";

const line = (n: number, start: number, end: number): Line => ({
  n, start, end, speaker: "david", label: "ديفيد", section: null, ar: "نَعَم", en: "Yes.",
});

// Three lines with kallim's gaps: 0.7 s between turns, 2.3 s at a section break.
const timeline = new Timeline([line(1, 0, 4), line(2, 4.7, 10), line(3, 12.3, 15)]);

describe("Timeline.at", () => {
  it("is undefined only before the first line starts", () => {
    expect(new Timeline([line(1, 2, 3)]).at(1)).toBeUndefined();
  });

  it("returns the line that starts exactly then", () => {
    expect(timeline.at(4.7)?.n).toBe(2);
  });

  it("returns the line being spoken", () => {
    expect(timeline.at(7)?.n).toBe(2);
  });

  it("keeps the line that just ended through the silence after it", () => {
    expect(timeline.at(4.3)?.n).toBe(1);
    expect(timeline.at(11.5)?.n).toBe(2);
  });

  it("keeps the last line after the audio's last word", () => {
    expect(timeline.at(99)?.n).toBe(3);
  });

  it("agrees with a plain linear search at every 10 ms", () => {
    for (let t = -1; t <= 16; t += 0.01) {
      const linear = timeline.lines.findLast((l) => l.start <= t);
      expect(timeline.at(t), `t=${t.toFixed(2)}`).toBe(linear);
    }
  });
});

describe("Timeline.loopBoundary", () => {
  it("wraps half a second after the line ends", () => {
    expect(timeline.loopBoundary(timeline.lines[1])).toBeCloseTo(10.5);
  });

  it("never wraps inside the next line", () => {
    const tight = new Timeline([line(1, 0, 4), line(2, 4.2, 6)]);
    expect(tight.loopBoundary(tight.lines[0])).toBe(4.2);
  });

  it("handles the last line, which has no next", () => {
    expect(timeline.loopBoundary(timeline.lines[2])).toBeCloseTo(15.5);
  });
});

describe("new Timeline", () => {
  it("refuses an empty lesson", () => {
    expect(() => new Timeline([])).toThrow(/no lines/);
  });

  it("refuses a gap in the numbering", () => {
    expect(() => new Timeline([line(1, 0, 1), line(3, 2, 3)])).toThrow(/expected line 2/);
  });

  it("refuses a line that ends before it starts", () => {
    expect(() => new Timeline([line(1, 2, 1)])).toThrow(/ends before it starts/);
  });

  it("refuses overlapping lines", () => {
    expect(() => new Timeline([line(1, 0, 3), line(2, 2, 4)])).toThrow(/starts before/);
  });
});
