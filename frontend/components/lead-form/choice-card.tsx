"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Choice<T extends string> = { value: T; label: string; hint?: string; icon?: ReactNode };

/**
 * Large tap targets backed by native radio inputs, so arrow keys, screen readers and form
 * semantics work without extra ARIA.
 */
export function ChoiceGroup<T extends string>({
  name,
  legend,
  options,
  value,
  onChange,
  error,
  columns = 2,
}: {
  name: string;
  legend: string;
  options: Choice<T>[];
  value: T | undefined;
  onChange: (value: T) => void;
  error?: string;
  columns?: 2 | 4;
}) {
  const errorId = `${name}-error`;
  return (
    <fieldset aria-describedby={error ? errorId : undefined}>
      <legend className="mb-3 text-[0.9375rem] font-semibold text-ink">{legend}</legend>
      <div className={cn("grid gap-3", columns === 4 ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2")}>
        {options.map((option) => {
          const checked = value === option.value;
          return (
            <label
              key={option.value}
              className={cn(
                "relative flex min-h-[4.5rem] cursor-pointer flex-col gap-1 rounded-2xl border bg-background p-3.5 transition-colors",
                "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-teal",
                checked ? "border-teal bg-teal-wash/60 ring-1 ring-teal" : "border-border hover:border-teal/50",
                error && !value ? "border-destructive/60" : null,
              )}
            >
              <input
                type="radio"
                name={name}
                value={option.value}
                checked={checked}
                onChange={() => onChange(option.value)}
                className="sr-only"
              />
              {option.icon ? <span className="text-teal">{option.icon}</span> : null}
              <span className="font-medium leading-snug text-ink">{option.label}</span>
              {option.hint ? <span className="text-[0.8125rem] leading-snug text-ink-2">{option.hint}</span> : null}
              <span
                aria-hidden
                className={cn(
                  "absolute right-3 top-3 size-4 rounded-full border-2",
                  checked ? "border-teal bg-teal shadow-[inset_0_0_0_2px_white]" : "border-input",
                )}
              />
            </label>
          );
        })}
      </div>
      {error ? (
        <p id={errorId} className="mt-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
