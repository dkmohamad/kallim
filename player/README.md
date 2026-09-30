# player

A web page for shadowing a distilled Arabic lesson: the lesson's audio with its
lines, Arabic above English, in sync. Each lesson is an MDX page, so it can carry
notes and background around the player.

It is one of kallim's render targets (see [DESIGN.md](../DESIGN.md)). It reads
the `.mp3` and `.vtt` that `kallim script --render` writes, and nothing else from
kallim.

The home page lists every lesson, newest first. A lesson page shows the current
line large, with the whole transcript scrolling beneath it. Tap a line to jump
to it; Replay, Loop, an English toggle and 0.75×/1× speed sit with the audio
bar. Keys: Space plays or pauses, ← replays the line, L loops it.

## Run it

From this directory:

```bash
npm install
npm run dev        # http://localhost:3000
npm run build
npm test
npx tsc --noEmit && npx eslint
```

## Add a lesson

A lesson is three files that share one slug, the MDX file name:

1. Render it in kallim, from the repo root:
   `uv run kallim script scratch/<slug>.md --render`.
2. Copy both outputs from **the same run directory**, so the audio and the
   timings match:

   ```bash
   cp ../output/<run>/<slug>.{mp3,vtt} public/lessons/
   ```

3. Write `src/content/lessons/<slug>.mdx`. It exports the fields of `Lesson`
   in [src/lib/lessons.ts](src/lib/lessons.ts), and places the player with a
   bare `<Player />`:

   ```mdx
   export const lesson = {
     title: "Damascus and poetry",
     recorded: "2026-08-24",
     summary: "One line for the home page.",
   };

   A short intro.

   <Player />

   ## Notes
   ```

A missing or malformed field fails the build, naming the file and the field.

## Deploy

Vercel builds this directory: set the project's root directory to `player`.
Every page and file is served `noindex`, and the URL is not published anywhere.
