import Image from "next/image";

import { cn } from "@/lib/utils";

type LogoProps = {
  variant?: "mark" | "lockup";
  tone?: "light" | "dark";
  size?: number;
  className?: string;
};

/** Client-supplied sun mark with the HelioFlow wordmark (one word). `tone="dark"` sits on night teal. */
export function Logo({ variant = "lockup", tone = "light", size = 36, className }: LogoProps) {
  const mark = (
    <Image
      src="/brand/helio-mark.png"
      alt={variant === "mark" ? "HelioFlow" : ""}
      width={size}
      height={size}
      priority
      className={cn("shrink-0 rounded-[24%]", tone === "dark" && "ring-1 ring-white/15")}
    />
  );
  if (variant === "mark") return <span className={className}>{mark}</span>;

  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      {mark}
      <span
        className={cn(
          "font-display text-[1.2rem] font-semibold leading-none",
          tone === "dark" ? "text-white" : "text-ink",
        )}
      >
        HelioFlow
      </span>
    </span>
  );
}
