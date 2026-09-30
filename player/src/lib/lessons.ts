import { readdirSync } from "node:fs";
import path from "node:path";
import type { MDXContent } from "mdx/types";
import { notFound } from "next/navigation";
import type { LessonSlug } from "./lesson-paths";

export type { LessonSlug } from "./lesson-paths";

const LESSONS_DIR = path.join(process.cwd(), "src/content/lessons");
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** What each lesson MDX file exports as `lesson`. */
export interface Lesson {
  readonly title: string;
  readonly recorded: string; // ISO date, YYYY-MM-DD
  readonly summary: string; // one line for the index
}

/** Every lesson, one per `src/content/lessons/*.mdx`. */
export function lessonSlugs(): LessonSlug[] {
  return readdirSync(LESSONS_DIR)
    .filter((file) => file.endsWith(".mdx"))
    .map((file) => path.basename(file, ".mdx") as LessonSlug)
    .sort();
}

/** The one way a route param becomes a slug: it must name a lesson file. */
export function toLessonSlug(param: string): LessonSlug {
  const slug = lessonSlugs().find((known) => known === param);
  if (!slug) notFound();
  return slug;
}

/** Load a lesson's MDX. Throws if it does not export a well-formed `lesson`. */
export async function loadLesson(
  slug: LessonSlug,
): Promise<{ lesson: Lesson; Content: MDXContent }> {
  const mod = (await import(`@/content/lessons/${slug}.mdx`)) as {
    default: MDXContent;
    lesson?: unknown;
  };
  return { lesson: parseLesson(slug, mod.lesson), Content: mod.default };
}

/** Every lesson with its metadata, newest first. */
export async function allLessons(): Promise<{ slug: LessonSlug; lesson: Lesson }[]> {
  const lessons = await Promise.all(
    lessonSlugs().map(async (slug) => ({ slug, lesson: (await loadLesson(slug)).lesson })),
  );
  return lessons.sort((a, b) => b.lesson.recorded.localeCompare(a.lesson.recorded));
}

function parseLesson(slug: LessonSlug, value: unknown): Lesson {
  const fail = (why: string): never => {
    throw new Error(`${slug}.mdx: ${why} (export lesson = { title, recorded, summary })`);
  };
  if (typeof value !== "object" || value === null) return fail("no lesson export");
  const { title, recorded, summary } = value as Record<string, unknown>;
  if (typeof title !== "string" || title === "") return fail("missing title");
  if (typeof recorded !== "string" || !ISO_DATE.test(recorded)) {
    return fail("recorded must be a YYYY-MM-DD date");
  }
  if (typeof summary !== "string" || summary === "") return fail("missing summary");
  return { title, recorded, summary };
}
