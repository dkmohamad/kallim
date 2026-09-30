import type { Line } from "@/lib/lines";

export function CurrentLine({
  line,
  total,
  showEnglish,
}: {
  line: Line;
  total: number;
  showEnglish: boolean;
}) {
  return (
    <div>
      <p className="text-right text-xs text-neutral-500">
        {`${line.n} / ${total}`} · <bdi className="font-arabic">{line.label}</bdi>
      </p>
      <p lang="ar" dir="rtl" className="ar font-arabic text-xl sm:text-3xl">
        {line.ar}
      </p>
      {showEnglish && <p className="text-sm text-neutral-600 sm:text-base">{line.en}</p>}
    </div>
  );
}
