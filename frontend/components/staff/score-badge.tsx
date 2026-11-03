import { cn } from "@/lib/utils";

/** High in brand teal, Low in attention amber (§20: amber only for Low, flags, stuck). */
export function ScoreBadge({ score, className }: { score: "high" | "low" | null; className?: string }) {
  if (!score) return <span className={cn("text-sm text-ink-2", className)}>Not scored</span>;
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2.5 text-[0.8125rem] font-semibold",
        score === "high" ? "bg-teal text-white" : "bg-attention-bg text-attention",
        className,
      )}
    >
      {score === "high" ? "High" : "Low"}
    </span>
  );
}

export function FlagChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-attention/30 bg-attention-bg/60 px-2 py-0.5 text-[0.75rem] text-attention">
      {children}
    </span>
  );
}
