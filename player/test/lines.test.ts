import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { LineFormatError, parseVtt } from "../src/lib/lines";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

// The file kallim's own test holds to_vtt to, byte for byte
// (tests/test_script.py). Parsing it here ties the reader to the writer.
const SHARED = read("../../tests/fixtures/lesson.vtt");

// The first four cues of a real to_vtt render of the damascus lesson.
const DAMASCUS = read("fixtures/damascus-head.vtt");

const cue = (payload: object, timing = "00:00:01.000 --> 00:00:02.000") =>
  `WEBVTT\n\n${timing}\n${JSON.stringify(payload)}\n`;

const GOOD = { n: 1, speaker: "david", label: "ديفيد", section: null, ar: "نَعَم", en: "Yes." };

describe("parseVtt", () => {
  it("reads the file kallim's writer is tested against", () => {
    const lines = parseVtt(SHARED);
    expect(lines.map((l) => [l.n, l.start, l.end])).toEqual([
      [1, 0, 1],
      [2, 1.7, 3.7],
      [3, 6, 9],
    ]);
    expect(lines[2].section).toBe("المَوْضُوع");
  });

  it("turns kallim's escaped arrow back into -->", () => {
    expect(parseVtt(SHARED)[1].en).toBe("Hi, teacher --> hello, teacher.");
  });

  it("reads a real lesson, fields verbatim and times in seconds", () => {
    const lines = parseVtt(DAMASCUS);
    expect(lines.map((l) => l.n)).toEqual([1, 2, 3, 4]);
    expect(lines.map((l) => l.speaker)).toEqual(["david", "teacher", "david", "teacher"]);
    expect(lines[1]).toMatchObject({
      label: "المعلِّمة",
      section: "التَّحِيَّةُ وَالأَحْوَال",
      ar: "أَنَا بِخَيْرٍ، شُكْرًا. كُلُّ شَيْءٍ عَلَى مَا يُرَامُ.",
      en: "I'm well, thank you. Everything is going fine.",
      start: 5.39,
      end: 11.009,
    });
  });

  it("reads hours, not just minutes", () => {
    const [line] = parseVtt(cue(GOOD, "01:02:03.004 --> 01:02:05.050"));
    expect(line.start).toBeCloseTo(3723.004);
    expect(line.end).toBeCloseTo(3725.05);
  });

  it("refuses a file without the WEBVTT header", () => {
    expect(() => parseVtt(DAMASCUS.replace("WEBVTT", "VTT"))).toThrow(LineFormatError);
  });

  it("refuses a payload that is not JSON", () => {
    expect(() => parseVtt("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nnot json\n")).toThrow(
      /not JSON/,
    );
  });

  it("names the cue and the field when one is missing, and never defaults it", () => {
    const noGloss: Record<string, unknown> = { ...GOOD };
    delete noGloss.en;
    expect(() => parseVtt(cue(noGloss))).toThrow(/cue 1: missing or invalid "en"/);
  });

  it("refuses a speaker kallim does not have", () => {
    expect(() => parseVtt(cue({ ...GOOD, speaker: "narrator" }))).toThrow(
      /cue 1: unknown speaker "narrator"/,
    );
  });
});
