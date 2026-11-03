/**
 * Sign-in art: the product in one picture — "your bill, your roof and your quote, in one place".
 * Three cards (a thermal spot-bill receipt, a flat RCC rooftop with panels, the quote) rise over a
 * Vidarbha sunrise whose ray fan echoes the logo, joined by the gold energy line (the page's only
 * motion; reduced-motion respected). Numbers are Western digits, so it reads in every language.
 * Decorative (aria-hidden).
 */

const GOLD = "#E5B257";
const GOLD_SOFT = "#F6DFA8";
const NIGHT = "#012E2B";
const TEAL = "#006863";
const PAPER = "#FBF8F1";
const INK = "#18211F";
const LINE = "#C9D4D1";

// Server and browser trig differ in the last digits; round so the markup hydrates identically.
const r1 = (n: number) => Math.round(n * 10) / 10;

function Rays({ cx, cy, inner, outer, count = 13 }: { cx: number; cy: number; inner: number; outer: number; count?: number }) {
  return (
    <g stroke={GOLD} strokeWidth="2" strokeLinecap="round" opacity="0.16">
      {Array.from({ length: count }, (_, i) => {
        const a = Math.PI + (Math.PI * (i + 0.5)) / count; // upper half only
        return (
          <line
            key={i}
            x1={r1(cx + inner * Math.cos(a))}
            y1={r1(cy + inner * Math.sin(a))}
            x2={r1(cx + outer * Math.cos(a))}
            y2={r1(cy + outer * Math.sin(a))}
          />
        );
      })}
    </g>
  );
}

function Shadowed({ x, y, w, h, r = 14, children, rotate }: { x: number; y: number; w: number; h: number; r?: number; children?: React.ReactNode; rotate?: string }) {
  return (
    <g transform={rotate}>
      <rect x={x + 6} y={y + 12} width={w} height={h} rx={r} fill="#000" opacity="0.28" />
      <rect x={x} y={y} width={w} height={h} rx={r} fill={PAPER} />
      {children}
    </g>
  );
}

export function SignInStory({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 900" className={className} aria-hidden focusable="false" preserveAspectRatio="xMidYMax slice">
      <rect width="640" height="900" fill={NIGHT} />

      {/* The sunrise: halo rings, the logo's ray fan, a half sun on the horizon. */}
      <circle cx="320" cy="900" r="430" fill="none" stroke={GOLD_SOFT} strokeOpacity="0.07" strokeWidth="2" />
      <circle cx="320" cy="900" r="330" fill="none" stroke={GOLD_SOFT} strokeOpacity="0.1" strokeWidth="2" strokeDasharray="2 10" />
      <Rays cx={320} cy={900} inner={250} outer={520} />
      <circle cx="320" cy="900" r="240" fill={GOLD} opacity="0.12" />
      <circle cx="320" cy="900" r="200" fill={GOLD} />
      <path d="M0 899 H640" stroke={GOLD_SOFT} strokeOpacity="0.55" strokeWidth="2" />

      {/* 1 · Your bill: a thermal spot-bill receipt with the units picked out. */}
      <Shadowed x={58} y={452} w={150} h={236} r={6} rotate="rotate(-9 133 570)">
        <path d="M58 682 l12.5 10 12.5 -10 12.5 10 12.5 -10 12.5 10 12.5 -10 12.5 10 12.5 -10 12.5 10 12.5 -10 12.5 10 12.5 -10 v-6 h-150 z" fill={PAPER} />
        <rect x={78} y={474} width={84} height={9} rx={4.5} fill={TEAL} />
        <g fill={LINE}>
          <rect x={78} y={496} width={110} height={6} rx={3} />
          <rect x={78} y={512} width={92} height={6} rx={3} />
          <rect x={78} y={528} width={104} height={6} rx={3} />
          <rect x={78} y={612} width={110} height={6} rx={3} />
          <rect x={78} y={628} width={80} height={6} rx={3} />
          <rect x={78} y={644} width={98} height={6} rx={3} />
        </g>
        <rect x={70} y={550} width={126} height={44} rx={8} fill={GOLD_SOFT} />
        <text x={80} y={570} fontSize="12" fontWeight="600" fill={INK} letterSpacing="1">UNITS</text>
        <text x={80} y={588} fontSize="17" fontWeight="700" fill={INK}>340 kWh</text>
      </Shadowed>

      {/* 2 · Your roof: a flat RCC roof with tilted panels and a water tank, under a small sun. */}
      <Shadowed x={226} y={392} w={190} h={226}>
        <rect x={238} y={404} width={166} height={150} rx={9} fill="#E3EFED" />
        <circle cx={378} cy={432} r={13} fill={GOLD} />
        <rect x={258} y={492} width={128} height={62} fill="#FFFFFF" stroke={TEAL} strokeWidth="2.5" />
        <path d="M250 492 H394" stroke={TEAL} strokeWidth="3" strokeLinecap="round" />
        <rect x={362} y={468} width={20} height={24} rx={3} fill={TEAL} opacity="0.85" />
        <g fill={TEAL} stroke="#E3EFED" strokeWidth="1.5">
          <path d="M264 488 L300 488 L308 466 L272 466 Z" />
          <path d="M304 488 L340 488 L348 466 L312 466 Z" />
        </g>
        <path d="M268 477 H340 M290 466 L282 488 M330 466 L322 488" stroke="#E3EFED" strokeWidth="1.2" opacity="0.7" />
        <rect x={282} y={516} width={22} height={38} fill={TEAL} opacity="0.2" />
        <rect x={334} y={512} width={30} height={20} rx={3} fill={GOLD_SOFT} />
        <rect x={244} y={570} width={96} height={8} rx={4} fill={INK} opacity="0.8" />
        <rect x={244} y={588} width={140} height={6} rx={3} fill={LINE} />
      </Shadowed>

      {/* 3 · Your quote: size, cost after subsidy, and payback filling up. */}
      <Shadowed x={434} y={470} w={160} h={200} rotate="rotate(8 514 570)">
        <rect x={452} y={490} width={60} height={7} rx={3.5} fill={LINE} />
        <text x={452} y={540} fontSize="36" fontWeight="700" fill={TEAL}>3 kW</text>
        <rect x={452} y={556} width={78} height={6} rx={3} fill={LINE} />
        <text x={452} y={590} fontSize="19" fontWeight="700" fill={INK}>₹1,02,000</text>
        <rect x={452} y={612} width={124} height={10} rx={5} fill="#E3EFED" />
        <rect x={452} y={612} width={80} height={10} rx={5} fill={GOLD} />
        <circle cx={566} cy={648} r={12} fill={GOLD} />
        <path d="M560 648 l4.5 4.5 l7.5 -8" fill="none" stroke={NIGHT} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </Shadowed>

      {/* The energy line joining bill → roof → quote. */}
      <path
        className="hf-flow"
        d="M196 650 C 228 724, 300 724, 321 640 S 416 690, 446 640"
        fill="none"
        stroke={GOLD}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeDasharray="2 12"
      />
      <circle cx={196} cy={650} r={6} fill={GOLD} />
      <circle cx={446} cy={640} r={6} fill={GOLD} />
    </svg>
  );
}

/** Phone header band: the same sunrise, without the cards. */
export function SignInSunrise({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 260" className={className} aria-hidden focusable="false" preserveAspectRatio="xMidYMax slice">
      <rect width="640" height="260" fill={NIGHT} />
      <circle cx="430" cy="300" r="250" fill="none" stroke={GOLD_SOFT} strokeOpacity="0.1" strokeWidth="2" strokeDasharray="2 10" />
      <Rays cx={430} cy={300} inner={170} outer={380} count={11} />
      <circle cx="430" cy="300" r="150" fill={GOLD} opacity="0.12" />
      <circle cx="430" cy="300" r="122" fill={GOLD} />
      <path d="M0 259 H640" stroke={GOLD_SOFT} strokeOpacity="0.55" strokeWidth="2" />
    </svg>
  );
}
