import { LineFormatError, type Line } from "./lines";

/** Silence after a looped line before it repeats. Under kallim's 700 ms minimum gap. */
export const LOOP_TAIL_S = 0.5;

/** The lesson's lines in order, and the two questions the player asks of them. */
export class Timeline {
  readonly lines: readonly Line[];

  /** Throws LineFormatError on an empty, unsorted or overlapping list, or a gap in `n`. */
  constructor(lines: readonly Line[]) {
    if (lines.length === 0) throw new LineFormatError("the lesson has no lines");
    lines.forEach((line, i) => {
      if (line.n !== i + 1) {
        throw new LineFormatError(`expected line ${i + 1}, found ${line.n}`);
      }
      if (line.end <= line.start) throw new LineFormatError(`line ${line.n} ends before it starts`);
      const prev = lines[i - 1];
      if (prev && line.start < prev.end) {
        throw new LineFormatError(`line ${line.n} starts before line ${prev.n} ends`);
      }
    });
    this.lines = lines;
  }

  /**
   * The last line that started at or before `t`. It stays set through the
   * silence after a line, so the display never blanks between lines.
   * Undefined only before the first line starts.
   */
  at(t: number): Line | undefined {
    let lo = 0;
    let hi = this.lines.length - 1;
    let found: Line | undefined;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (this.lines[mid].start <= t) {
        found = this.lines[mid];
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return found;
  }

  /** Where a loop on `line` jumps back: just after it ends, never into the next line. */
  loopBoundary(line: Line): number {
    const next = this.lines[line.n]; // n is 1-based, so this is the following line
    const tail = line.end + LOOP_TAIL_S;
    return next ? Math.min(tail, next.start) : tail;
  }
}
