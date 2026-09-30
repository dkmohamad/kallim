/**
 * Where a lesson's pages and files live. No `node:fs` here, so client
 * components can import it; listing and loading lessons is in `lessons.ts`.
 */

/** A lesson's slug is its MDX file name, and nothing else states it. */
export type LessonSlug = string & { readonly __brand: "LessonSlug" };

export const ROUTES = { Home: "/", Lessons: "/lessons" } as const;

/** `public/lessons/`: kallim's files, served beside the pages of the same name. */
const LESSON_FILES = "/lessons";

export function lessonHref(slug: LessonSlug): string {
  return `${ROUTES.Lessons}/${slug}`;
}

/** The lesson's audio, copied byte for byte from a kallim run. */
export function lessonAudio(slug: LessonSlug): string {
  return `${LESSON_FILES}/${slug}.mp3`;
}

/** The lesson's line timings, from the same kallim run as its audio. */
export function lessonCues(slug: LessonSlug): string {
  return `${LESSON_FILES}/${slug}.vtt`;
}
