import type { Metadata } from "next";
import Link from "next/link";
import { ShadowingPlayer } from "@/components/ShadowingPlayer";
import { formatDate } from "@/lib/dates";
import { ROUTES } from "@/lib/lesson-paths";
import { lessonSlugs, loadLesson, toLessonSlug } from "@/lib/lessons";

export const dynamicParams = false;

export function generateStaticParams() {
  return lessonSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: PageProps<"/lessons/[slug]">): Promise<Metadata> {
  const { lesson } = await loadLesson(toLessonSlug((await params).slug));
  return { title: lesson.title };
}

export default async function LessonPage({ params }: PageProps<"/lessons/[slug]">) {
  const slug = toLessonSlug((await params).slug);
  const { lesson, Content } = await loadLesson(slug);

  // The MDX writes a bare <Player />; the slug is bound here, from the file name.
  const components = { Player: () => <ShadowingPlayer slug={slug} /> };

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8">
      <Link href={ROUTES.Home} className="text-sm text-neutral-600 underline">
        All lessons
      </Link>
      <h1 className="mt-3 text-2xl font-semibold">{lesson.title}</h1>
      <p className="mt-1 text-sm text-neutral-500">{formatDate(lesson.recorded)}</p>
      <article className="prose prose-neutral mt-6 max-w-none">
        <Content components={components} />
      </article>
    </main>
  );
}
