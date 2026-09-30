"use client";

import { useCallback, useEffect, useEffectEvent, useReducer, useRef, useState } from "react";
import { lessonCues, type LessonSlug } from "@/lib/lesson-paths";
import { parseVtt, type Line } from "@/lib/lines";
import { initialState, reducer, type Rate } from "@/lib/player-state";
import { Timeline } from "@/lib/timeline";

export type Load =
  | { status: "loading" }
  | { status: "ready"; timeline: Timeline }
  | { status: "failed"; message: string };

/**
 * Everything the player does with the audio element. Sync is one path: fetch
 * and parse the VTT once, then poll `currentTime` and ask the timeline which
 * line that is. Polling runs on timeupdate and seeked, and on every animation
 * frame while playing; the loop check rides on the same callback.
 */
export function usePlayer(slug: LessonSlug) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [state, dispatch] = useReducer(reducer, initialState);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(lessonCues(slug))
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`${slug}.vtt wasn't found (${res.status}). Copy it from kallim's output/ run.`);
        }
        return new Timeline(parseVtt(await res.text()));
      })
      .then(
        (timeline) => !cancelled && setLoad({ status: "ready", timeline }),
        (error: unknown) =>
          !cancelled &&
          setLoad({ status: "failed", message: error instanceof Error ? error.message : String(error) }),
      );
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const timeline = load.status === "ready" ? load.timeline : null;

  // Read by the frame callback without re-subscribing it on every change.
  const loopOn = useEffectEvent(() => state.loop);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !timeline) return;
    let frame = 0;
    let shown: number | undefined;
    let wakeLock: WakeLockSentinel | null = null;
    let wantLock = false;

    const sample = () => {
      const loop = loopOn();
      if (loop && audio.currentTime >= timeline.loopBoundary(loop)) audio.currentTime = loop.start;
      const active = timeline.at(audio.currentTime);
      if (active?.n !== shown) {
        shown = active?.n;
        dispatch({ type: "tick", active });
      }
    };
    const onFrame = () => {
      sample();
      frame = requestAnimationFrame(onFrame);
    };
    const onPlay = () => {
      setPlaying(true);
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(onFrame);
      // Optional: keeps the phone awake while shadowing. Refused or
      // unsupported just means the screen may sleep, so nothing to report.
      wantLock = true;
      navigator.wakeLock?.request("screen").then(
        (lock) => {
          // A pause can land before the request resolves; don't hold it then.
          if (wantLock) wakeLock = lock;
          else void lock.release();
        },
        () => undefined,
      );
    };
    const onPause = () => {
      setPlaying(false);
      cancelAnimationFrame(frame);
      wantLock = false;
      void wakeLock?.release();
      wakeLock = null;
      sample();
    };

    audio.addEventListener("timeupdate", sample);
    audio.addEventListener("seeked", sample);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    sample();
    if (!audio.paused) onPlay();
    return () => {
      audio.removeEventListener("timeupdate", sample);
      audio.removeEventListener("seeked", sample);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      cancelAnimationFrame(frame);
      wantLock = false;
      void wakeLock?.release();
    };
  }, [timeline]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.defaultPlaybackRate = state.rate; // survives a reload of the source
    audio.playbackRate = state.rate;
  }, [state.rate, timeline]);

  const seekAndPlay = useCallback((t: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = t;
    void audio.play();
  }, []);

  // The seek's own `seeked` sample sets the active line; jump only moves the loop.
  const jump = useCallback(
    (line: Line) => {
      dispatch({ type: "jump", line });
      seekAndPlay(line.start);
    },
    [seekAndPlay],
  );

  const replay = useCallback(() => {
    const target = state.loop ?? state.active;
    if (target) seekAndPlay(target.start);
  }, [state.loop, state.active, seekAndPlay]);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) void audio.play();
    else audio.pause();
  }, []);

  const toggleLoop = useCallback(() => dispatch({ type: "toggleLoop" }), []);
  const toggleEnglish = useCallback(() => dispatch({ type: "toggleEnglish" }), []);
  const setRate = useCallback((rate: Rate) => dispatch({ type: "setRate", rate }), []);

  const onKey = useEffectEvent((event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null;
    if (target?.closest("input, textarea, select, audio, [contenteditable='true']")) return;
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.code === "Space") togglePlay();
    else if (event.code === "ArrowLeft") replay();
    else if (event.code === "KeyL") toggleLoop();
    else return;
    // The audio element handles its own keys when focused, so it is skipped
    // above. This stops Space scrolling the page or also clicking a button.
    event.preventDefault();
  });

  useEffect(() => {
    const handler = (event: KeyboardEvent) => onKey(event);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return { audioRef, load, state, playing, jump, replay, toggleLoop, toggleEnglish, setRate };
}
