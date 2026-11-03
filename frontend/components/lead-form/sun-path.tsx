"use client";

/**
 * The form's progress shown as the sun crossing the sky: three stops on an arc, the sun sits on
 * the current one and the path behind it is lit gold. Text labels underneath carry the meaning;
 * the drawing is decorative.
 */

import { cn } from "@/lib/utils";

type Props = {
  steps: string[];
  current: number; // 0-based
  label: string; // "Step 2 of 3"
  className?: string;
};

// Points on a shallow arc across a 300 × 90 box.
const STOPS = [
  { x: 30, y: 72 },
  { x: 150, y: 22 },
  { x: 270, y: 72 },
];
const ARC = "M30 72 Q150 -28 270 72";

export function SunPath({ steps, current, label, className }: Props) {
  const sun = STOPS[Math.min(current, STOPS.length - 1)];
  // Fraction of the arc that is lit: 0, 0.5, 1 for the three stops.
  const lit = current / (STOPS.length - 1);

  return (
    <nav aria-label={label} className={cn("w-full", className)}>
      <svg viewBox="0 0 300 90" className="w-full overflow-visible" aria-hidden focusable="false">
        <path d={ARC} fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth="2" strokeDasharray="3 6" strokeLinecap="round" />
        <path
          d={ARC}
          fill="none"
          stroke="#E5B257"
          strokeWidth="2.5"
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset={1 - lit}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
        {STOPS.map((s, i) => (
          <circle
            key={i}
            cx={s.x}
            cy={s.y}
            r={5}
            fill={i <= current ? "#E5B257" : "#012E2B"}
            stroke={i <= current ? "#E5B257" : "rgba(255,255,255,0.5)"}
            strokeWidth="2"
          />
        ))}
        <g
          style={{ transform: `translate(${sun.x}px, ${sun.y}px)` }}
          className="transition-transform duration-700 ease-out"
        >
          <circle r="15" fill="#E5B257" opacity="0.2" />
          <circle r="10" fill="#E5B257" />
        </g>
      </svg>
      <ol className="mt-2 grid grid-cols-3 text-center text-sm">
        {steps.map((step, i) => (
          <li
            key={step}
            aria-current={i === current ? "step" : undefined}
            className={cn(
              i === current ? "font-semibold text-white" : i < current ? "text-gold-soft" : "text-white/60",
            )}
          >
            {step}
          </li>
        ))}
      </ol>
      <p className="sr-only">{label}</p>
    </nav>
  );
}
