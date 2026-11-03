import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

/** Label, control, hint and error wired together; `id` links them for screen readers. */
export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: ReactNode;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id} className="text-[0.9375rem] font-semibold text-ink">
        {label}
      </Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-[0.8125rem] text-ink-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** aria-describedby for a Field's control. */
export function describedBy(id: string, error?: unknown, hint?: unknown): string | undefined {
  if (error) return `${id}-error`;
  return hint ? `${id}-hint` : undefined;
}

/** An input with a unit on its edge ("₹" before, "sq ft" after). */
export function UnitInput({
  unit,
  position = "end",
  children,
}: {
  unit: string;
  position?: "start" | "end";
  children: ReactNode;
}) {
  return (
    <div className="relative">
      {children}
      <span
        aria-hidden
        className={`pointer-events-none absolute inset-y-0 flex items-center text-ink-2 ${
          position === "start" ? "left-3.5" : "right-3.5"
        }`}
      >
        {unit}
      </span>
    </div>
  );
}
