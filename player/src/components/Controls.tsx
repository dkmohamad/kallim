import { RATES, type Rate } from "@/lib/player-state";

const BUTTON =
  "rounded-md border border-neutral-800 px-2.5 py-1 text-sm aria-pressed:bg-neutral-900 aria-pressed:text-white";

export function Controls({
  looping,
  showEnglish,
  rate,
  onReplay,
  onToggleLoop,
  onToggleEnglish,
  onRate,
}: {
  looping: boolean;
  showEnglish: boolean;
  rate: Rate;
  onReplay: () => void;
  onToggleLoop: () => void;
  onToggleEnglish: () => void;
  onRate: (rate: Rate) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button type="button" className={BUTTON} onClick={onReplay} title="Replay line (←)">
        ↺ Replay
      </button>
      <button type="button" className={BUTTON} aria-pressed={looping} onClick={onToggleLoop} title="Loop line (L)">
        ⟳ Loop
      </button>
      <button type="button" className={BUTTON} aria-pressed={showEnglish} onClick={onToggleEnglish} title="Show English">
        EN
      </button>
      {Object.values(RATES).map((r) => (
        <button key={r} type="button" className={BUTTON} aria-pressed={rate === r} onClick={() => onRate(r)}>
          {r}×
        </button>
      ))}
    </div>
  );
}
