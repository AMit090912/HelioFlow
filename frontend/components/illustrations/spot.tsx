/**
 * Small spot illustrations: one per "how it works" step and one per empty state.
 * Line drawings in brand teal with a single gold accent each. Decorative (aria-hidden).
 */

type SpotProps = { className?: string };

const LINE = { fill: "none", stroke: "#006863", strokeWidth: 2.5, strokeLinecap: "round", strokeLinejoin: "round" } as const;

/** Step 1 — tell us about your home: a house with a short form beside it. */
export function SpotHome({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 96 80" className={className} aria-hidden focusable="false">
      <circle cx="74" cy="18" r="9" fill="#E5B257" />
      <path {...LINE} d="M10 70 V36 H52 V70 Z M6 36 H56 M26 70 V54 H36 V70" />
      <path {...LINE} d="M14 36 L20 26 H44 L50 36" />
      <rect x="62" y="40" width="28" height="30" rx="4" {...LINE} />
      <path {...LINE} d="M68 50 H84 M68 58 H80" />
    </svg>
  );
}

/** Step 2 — upload your bill: a bill page with a gold scan line passing over it. */
export function SpotBill({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 96 80" className={className} aria-hidden focusable="false">
      <path {...LINE} d="M28 8 H60 L70 18 V72 H28 Z M60 8 V18 H70" />
      <path {...LINE} d="M36 30 H62 M36 40 H62 M36 50 H52 M36 60 H58" />
      <path d="M20 44 H78" stroke="#E5B257" strokeWidth="3.5" strokeLinecap="round" />
      <path d="M20 44 H78" stroke="#E5B257" strokeWidth="12" strokeLinecap="round" opacity="0.18" />
    </svg>
  );
}

/** Step 3 — get your quote: a quote card with the rupee mark and a sun seal. */
export function SpotQuote({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 96 80" className={className} aria-hidden focusable="false">
      <rect x="18" y="10" width="50" height="62" rx="6" {...LINE} />
      <path {...LINE} d="M32 26 H52 M32 33 H52 M44 26 C 52 26, 52 40, 40 40 L 52 54" />
      <circle cx="68" cy="58" r="13" fill="#E5B257" />
      <path d="M62 58 L66.5 62.5 L74 54" fill="none" stroke="#012E2B" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Bill upload: a phone framing a bill, with a gold sun rising out of the screen as it goes up. */
export function SpotUpload({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 200 140" className={className} aria-hidden focusable="false">
      <circle cx="100" cy="76" r="62" fill="#E3EFED" />
      <rect x="66" y="30" width="68" height="100" rx="10" fill="#FFFFFF" stroke="#006863" strokeWidth="2.5" />
      <path d="M92 38 H108" stroke="#006863" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M78 58 H112 L122 68 V112 H78 Z" fill="none" stroke="#006863" strokeWidth="2" strokeLinejoin="round" />
      <path d="M86 78 H112 M86 88 H112 M86 98 H102" stroke="#006863" strokeWidth="2" strokeLinecap="round" opacity="0.55" />
      <path d="M72 84 H128" stroke="#E5B257" strokeWidth="3" strokeLinecap="round" />
      <circle cx="152" cy="34" r="12" fill="#E5B257" />
      <path d="M152 58 V48 M147 53 L152 48 L157 53" fill="none" stroke="#E5B257" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Account step: a key resting on a small house card (your place, your quote). */
export function SpotAccount({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 200 140" className={className} aria-hidden focusable="false">
      <circle cx="100" cy="76" r="62" fill="#E3EFED" />
      <rect x="54" y="44" width="92" height="64" rx="8" fill="#FFFFFF" stroke="#006863" strokeWidth="2.5" />
      <path d="M70 92 V72 L84 62 L98 72 V92 Z" fill="none" stroke="#006863" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M108 70 H132 M108 80 H126" stroke="#006863" strokeWidth="2.5" strokeLinecap="round" opacity="0.55" />
      <circle cx="150" cy="104" r="10" fill="none" stroke="#E5B257" strokeWidth="3.5" />
      <path d="M142 112 L124 130 M130 124 L135 129" stroke="#E5B257" strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  );
}

/** Project status: a home with its panels in place and the sun climbing an arc of progress. */
export function SpotProgress({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 200 140" className={className} aria-hidden focusable="false">
      <path d="M26 112 A 74 74 0 0 1 174 112" fill="none" stroke="#F6DFA8" strokeWidth="3" strokeDasharray="4 7" strokeLinecap="round" />
      <path d="M26 112 A 74 74 0 0 1 112 39" fill="none" stroke="#E5B257" strokeWidth="3.5" strokeLinecap="round" />
      <circle cx="112" cy="39" r="12" fill="#E5B257" />
      <path d="M58 112 V84 H142 V112" fill="#012E2B" stroke="#F6DFA8" strokeWidth="2" />
      <path d="M52 84 H148" stroke="#F6DFA8" strokeWidth="2.5" strokeLinecap="round" />
      <path d="M68 78 L94 78 L100 64 L74 64 Z M104 78 L130 78 L136 64 L110 64 Z" fill="#006863" stroke="#F6DFA8" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M92 112 V96 H108 V112" fill="none" stroke="#F6DFA8" strokeWidth="2" />
      <path d="M16 112 H184" stroke="#F6DFA8" strokeWidth="2" opacity="0.5" />
    </svg>
  );
}

/** Homeowner empty state: a roof waiting for its panels (dashed outlines). */
export function SpotEmptyRoof({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 200 140" className={className} aria-hidden focusable="false">
      <circle cx="100" cy="76" r="62" fill="#E3EFED" />
      <circle cx="154" cy="30" r="12" fill="#E5B257" />
      <path d="M44 112 V78 H156 V112" fill="#FFFFFF" stroke="#006863" strokeWidth="2.5" />
      <path d="M38 78 H162" stroke="#006863" strokeWidth="3" strokeLinecap="round" />
      <g fill="none" stroke="#006863" strokeWidth="2" strokeDasharray="5 5" strokeLinejoin="round">
        <path d="M56 70 L92 70 L100 50 L64 50 Z" />
        <path d="M102 70 L138 70 L146 50 L110 50 Z" />
      </g>
      <path d="M90 112 V94 H110 V112" fill="none" stroke="#006863" strokeWidth="2.5" />
    </svg>
  );
}

/** Staff empty inbox: a tray with an empty lead card and a spark of sun. */
export function SpotEmptyInbox({ className }: SpotProps) {
  return (
    <svg viewBox="0 0 200 140" className={className} aria-hidden focusable="false">
      <circle cx="100" cy="74" r="62" fill="#E3EFED" />
      <rect x="62" y="34" width="76" height="50" rx="6" fill="#FFFFFF" stroke="#006863" strokeWidth="2.5" strokeDasharray="6 5" />
      <path d="M74 50 H112 M74 62 H100" stroke="#006863" strokeWidth="2.5" strokeLinecap="round" opacity="0.5" />
      <path d="M40 84 H72 L80 98 H120 L128 84 H160 V112 H40 Z" fill="#FFFFFF" stroke="#006863" strokeWidth="2.5" strokeLinejoin="round" />
      <g stroke="#E5B257" strokeWidth="3" strokeLinecap="round">
        <path d="M150 26 V36 M145 31 H155 M162 18 L158 22 M142 18 L146 22" />
      </g>
    </svg>
  );
}
