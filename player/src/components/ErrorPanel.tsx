export function ErrorPanel({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-red-700 bg-red-50 p-3 text-sm text-red-900">
      <p className="font-semibold">This lesson can&apos;t play.</p>
      <p className="mt-1">{message}</p>
      <p className="mt-1">No line was skipped. Fix it in kallim and copy both files again.</p>
    </div>
  );
}
