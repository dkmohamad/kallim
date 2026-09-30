import type { Line } from "./lines";

export const RATES = { Slow: 0.75, Normal: 1 } as const;
export type Rate = (typeof RATES)[keyof typeof RATES];

export interface PlayerState {
  /** Set only by `tick`, from timeline.at(currentTime); undefined before line 1. */
  readonly active: Line | undefined;
  /** The line being looped; undefined when loop is off. */
  readonly loop: Line | undefined;
  readonly showEnglish: boolean;
  readonly rate: Rate;
}

export type PlayerAction =
  | { type: "tick"; active: Line | undefined }
  | { type: "toggleLoop" } // on pins the loop to `active`
  | { type: "jump"; line: Line } // moves the loop, if it is on; the seek sets `active`
  | { type: "toggleEnglish" }
  | { type: "setRate"; rate: Rate };

export const initialState: PlayerState = {
  active: undefined,
  loop: undefined,
  showEnglish: true,
  rate: RATES.Normal,
};

export function reducer(state: PlayerState, action: PlayerAction): PlayerState {
  switch (action.type) {
    case "tick":
      return { ...state, active: action.active };
    case "toggleLoop":
      return { ...state, loop: state.loop ? undefined : state.active };
    case "jump":
      return state.loop ? { ...state, loop: action.line } : state;
    case "toggleEnglish":
      return { ...state, showEnglish: !state.showEnglish };
    case "setRate":
      return { ...state, rate: action.rate };
  }
}
