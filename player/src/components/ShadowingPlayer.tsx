"use client";

import { lessonAudio, type LessonSlug } from "@/lib/lesson-paths";
import { Controls } from "./Controls";
import { CurrentLine } from "./CurrentLine";
import { ErrorPanel } from "./ErrorPanel";
import { Transcript } from "./Transcript";
import { usePlayer } from "./usePlayer";

/**
 * The shadowing player: the current line and the controls in a panel that
 * sticks to the top of the screen, with the whole transcript scrolling beneath.
 */
export function ShadowingPlayer({ slug }: { slug: LessonSlug }) {
  const { audioRef, load, state, playing, jump, replay, toggleLoop, toggleEnglish, setRate } =
    usePlayer(slug);

  if (load.status === "failed") {
    return (
      <div className="not-prose my-6">
        <ErrorPanel message={load.message} />
      </div>
    );
  }
  const timeline = load.status === "ready" ? load.timeline : undefined;

  return (
    <div className="not-prose my-6">
      <div className="sticky top-0 z-10 -mx-4 space-y-2 border-b border-neutral-300 bg-white px-4 py-3">
        {state.active && timeline ? (
          <CurrentLine
            line={state.active}
            total={timeline.lines.length}
            showEnglish={state.showEnglish}
          />
        ) : (
          <p className="text-sm text-neutral-500">Press play. The current line shows here.</p>
        )}
        <audio ref={audioRef} controls preload="metadata" src={lessonAudio(slug)} className="w-full" />
        <Controls
          looping={state.loop !== undefined}
          showEnglish={state.showEnglish}
          rate={state.rate}
          onReplay={replay}
          onToggleLoop={toggleLoop}
          onToggleEnglish={toggleEnglish}
          onRate={setRate}
        />
      </div>
      {timeline ? (
        <Transcript
          lines={timeline.lines}
          active={state.active?.n}
          follow={playing}
          showEnglish={state.showEnglish}
          onJump={jump}
        />
      ) : (
        <p className="mt-4 text-sm text-neutral-500">Loading the lines…</p>
      )}
    </div>
  );
}
