import type { ReactNode } from "react";

/** An empty screen is an invitation to act: one illustration, one title, one sentence, at most one action. */
export function EmptyState({
  illustration,
  title,
  message,
  action,
}: {
  illustration: ReactNode;
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-3xl border border-border bg-background px-6 py-12 text-center">
      <div className="w-44">{illustration}</div>
      <h2 className="font-display mt-2 text-xl font-semibold text-ink">{title}</h2>
      <p className="max-w-md text-[0.9375rem] text-ink-2">{message}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}
