/**
 * The lesson's lines, as kallim's `to_vtt` writes them (scripts/script.py).
 *
 * kallim writes a strict subset of WebVTT: a `WEBVTT` header, then one block
 * per line of a timing line, a single line of JSON, and a blank line. This
 * reads exactly that, and refuses anything else rather than guessing.
 */

/** Mirrors kallim's `Speaker` enum values (scripts/model.py). */
export const SPEAKERS = { Teacher: "teacher", David: "david" } as const;
export type Speaker = (typeof SPEAKERS)[keyof typeof SPEAKERS];
const SPEAKER_IDS: readonly string[] = Object.values(SPEAKERS);

export interface Line {
  readonly n: number; // 1..N with no gaps; matches kallim's .txt transcript
  readonly speaker: Speaker;
  readonly label: string; // the Arabic name shown on the page
  readonly section: string | null; // the heading the line falls under
  readonly ar: string; // shown verbatim, never normalised
  readonly en: string;
  readonly start: number; // seconds
  readonly end: number;
}

export class LineFormatError extends Error {
  override name = "LineFormatError";
}

const TIMING = /^(\d{2}):(\d{2}):(\d{2})\.(\d{3}) --> (\d{2}):(\d{2}):(\d{2})\.(\d{3})$/;

/** Parse a kallim VTT into its lines, in order. Throws LineFormatError. */
export function parseVtt(text: string): Line[] {
  const blocks = text.replace(/\r\n/g, "\n").trim().split(/\n{2,}/);
  if (blocks[0]?.trim() !== "WEBVTT") {
    throw new LineFormatError("not a WebVTT file: the first line must be WEBVTT");
  }
  return blocks.slice(1).map((block, i) => parseBlock(block, i + 1));
}

function parseBlock(block: string, position: number): Line {
  const [timing, payload, ...rest] = block.split("\n");
  const where = `cue ${position}`;
  const times = TIMING.exec(timing ?? "");
  if (!times) throw new LineFormatError(`${where}: bad timing line "${timing}"`);
  if (payload === undefined || rest.length > 0) {
    throw new LineFormatError(`${where}: expected exactly one JSON line under the timing`);
  }

  let data: unknown;
  try {
    data = JSON.parse(payload);
  } catch (error) {
    throw new LineFormatError(`${where}: payload is not JSON`, { cause: error });
  }
  if (typeof data !== "object" || data === null) {
    throw new LineFormatError(`${where}: payload is not an object`);
  }
  const d = data as Record<string, unknown>;

  const n = d.n;
  if (typeof n !== "number" || !Number.isInteger(n)) invalid(where, "n");
  const at = `cue ${n}`;
  return {
    n,
    speaker: speaker(d, at),
    label: text(d, "label", at),
    section: section(d, at),
    ar: text(d, "ar", at),
    en: text(d, "en", at),
    start: seconds(times, 1),
    end: seconds(times, 5),
  };
}

function text(d: Record<string, unknown>, key: string, at: string): string {
  const value = d[key];
  if (typeof value !== "string" || value === "") invalid(at, key);
  return value;
}

function section(d: Record<string, unknown>, at: string): string | null {
  const value = d.section;
  if (value !== null && typeof value !== "string") invalid(at, "section");
  return value;
}

function speaker(d: Record<string, unknown>, at: string): Speaker {
  const value = d.speaker;
  if (typeof value !== "string" || !SPEAKER_IDS.includes(value)) {
    throw new LineFormatError(`${at}: unknown speaker ${JSON.stringify(value)}`);
  }
  return value as Speaker;
}

function invalid(at: string, key: string): never {
  throw new LineFormatError(`${at}: missing or invalid "${key}"`);
}

function seconds(m: RegExpExecArray, from: number): number {
  const [h, min, s, ms] = m.slice(from, from + 4).map(Number);
  return h * 3600 + min * 60 + s + ms / 1000;
}
