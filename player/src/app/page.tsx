import Link from "next/link";
import { formatDate } from "@/lib/dates";
import { lessonHref } from "@/lib/lesson-paths";
import { allLessons } from "@/lib/lessons";

/** Every lesson, newest first: a plain list of title, date and one-line summary. */
export default async function Home() {
  const lessons = await allLessons();

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <h1 className="text-3xl font-semibold">Lessons</h1>
      <p className="mt-2 text-neutral-600">
        {lessons.length} lessons, newest first. Open one to shadow it line by line.
      </p>
      <ul className="mt-6 divide-y divide-neutral-300 border-y border-neutral-300">
        {lessons.map(({ slug, lesson }) => (
          <li key={slug} className="py-5">
            <h2 className="text-lg font-semibold">
              <Link href={lessonHref(slug)} className="text-blue-800 underline underline-offset-2 hover:text-blue-950">
                {lesson.title}
              </Link>
            </h2>
            <p className="mt-1 text-sm text-neutral-500">
              <time dateTime={lesson.recorded}>{formatDate(lesson.recorded)}</time>
            </p>
            <p className="mt-2 text-neutral-700">{lesson.summary}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
