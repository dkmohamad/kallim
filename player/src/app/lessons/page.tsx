import { redirect } from "next/navigation";
import { ROUTES } from "@/lib/lesson-paths";

/** The index lives at the root; this keeps the old /lessons address working. */
export default function LessonsIndex() {
  redirect(ROUTES.Home);
}
