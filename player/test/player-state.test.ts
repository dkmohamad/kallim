import { describe, expect, it } from "vitest";
import type { Line } from "../src/lib/lines";
import { initialState, reducer } from "../src/lib/player-state";

const line = (n: number): Line => ({
  n, start: n, end: n + 0.5, speaker: "david", label: "ديفيد", section: null, ar: "نَعَم", en: "Yes.",
});

describe("reducer", () => {
  it("pins the loop to the active line, and clears it on a second toggle", () => {
    const playing = reducer(initialState, { type: "tick", active: line(2) });
    const looping = reducer(playing, { type: "toggleLoop" });
    expect(looping.loop?.n).toBe(2);
    expect(reducer(looping, { type: "toggleLoop" }).loop).toBeUndefined();
  });

  it("moves the loop when you jump to another line while looping", () => {
    let state = reducer(initialState, { type: "tick", active: line(2) });
    state = reducer(state, { type: "toggleLoop" });
    state = reducer(state, { type: "jump", line: line(5) });
    expect(state.loop?.n).toBe(5);
  });

  it("leaves the active line to the next tick: only the timeline sets it", () => {
    const state = reducer(initialState, { type: "tick", active: line(2) });
    expect(reducer(state, { type: "jump", line: line(5) }).active?.n).toBe(2);
  });

  it("does not start a loop when you jump with loop off", () => {
    expect(reducer(initialState, { type: "jump", line: line(5) }).loop).toBeUndefined();
  });

  it("toggles English and sets the rate", () => {
    expect(reducer(initialState, { type: "toggleEnglish" }).showEnglish).toBe(false);
    expect(reducer(initialState, { type: "setRate", rate: 0.75 }).rate).toBe(0.75);
  });
});
