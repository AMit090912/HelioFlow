/**
 * Sign-in: the "flow" in HelioFlow — energy travels from the sun, through a solar array,
 * to a home, along one animated gold line (the page's only motion; reduced-motion respected).
 * A different composition from the landing rooftop on purpose. Decorative (aria-hidden).
 */

const STARS: Array<[number, number, number]> = [
  [72, 96, 1.6], [150, 60, 1.2], [236, 128, 1.4], [520, 70, 1.2], [560, 300, 1.4],
  [96, 260, 1.2], [300, 52, 1.6], [470, 380, 1.1], [44, 420, 1.3],
];

export function SunFlowHome({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 600 720" className={className} aria-hidden focusable="false" preserveAspectRatio="xMidYMid slice">
      <rect width="600" height="720" fill="#012E2B" />
      <g fill="#F6DFA8">
        {STARS.map(([x, y, r]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={r} opacity="0.45" />
        ))}
      </g>

      {/* Sun with soft rings (rings here, rays on the landing page) */}
      <circle cx="430" cy="168" r="150" fill="none" stroke="#E5B257" strokeWidth="1" opacity="0.18" />
      <circle cx="430" cy="168" r="116" fill="none" stroke="#E5B257" strokeWidth="1.5" strokeDasharray="2 9" opacity="0.4" />
      <circle cx="430" cy="168" r="96" fill="#E5B257" opacity="0.12" />
      <circle cx="430" cy="168" r="66" fill="#F0C46C" />

      {/* Solar array in perspective */}
      <g>
        <path d="M96 470 L470 470 L536 316 L176 316 Z" fill="#13303A" stroke="#A9BDB9" strokeWidth="3" strokeLinejoin="round" />
        <g stroke="#2F5865" strokeWidth="2">
          {[1, 2, 3, 4, 5].map((i) => {
            const t = i / 6;
            const bx = 96 + (470 - 96) * t;
            const tx = 176 + (536 - 176) * t;
            return <path key={i} d={`M${bx} 470 L${tx} 316`} />;
          })}
          <path d="M122.7 418.7 H493.3" />
          <path d="M149.3 367.3 H514.7" />
        </g>
        <path d="M300 470 L360 470 L420 316 L360 316 Z" fill="#F6DFA8" opacity="0.16" />
        <path d="M150 470 V520 M420 470 V520 M200 316 L214 520 M500 316 L478 520" stroke="#9FB3B0" strokeWidth="4" strokeLinecap="round" opacity="0.9" />
      </g>

      {/* Ground */}
      <rect x="0" y="600" width="600" height="120" fill="#0A403C" />
      <rect x="0" y="600" width="600" height="3" fill="#E5B257" opacity="0.45" />

      {/* Home (bottom right, so the brand text can sit bottom left) */}
      <g transform="translate(330 0)">
        <rect x="70" y="534" width="150" height="66" fill="#F4EDE1" />
        <rect x="62" y="524" width="166" height="14" fill="#E8DCCB" />
        <rect x="92" y="552" width="40" height="30" rx="2" fill="#F6DFA8" />
        <rect x="156" y="552" width="40" height="30" rx="2" fill="#F6DFA8" />
        <path d="M112 552 V582 M176 552 V582" stroke="#D6C6AE" strokeWidth="3" />
        <path d="M84 524 L132 524 L140 506 L92 506 Z" fill="#13303A" stroke="#A9BDB9" strokeWidth="1.5" />
        <rect x="172" y="500" width="30" height="24" rx="5" fill="#1D2B2A" />
      </g>

      {/* The flow: sun → array → home */}
      <path
        d="M402 230 C 360 300, 340 360, 312 410 S 420 470, 450 500"
        fill="none"
        stroke="#E5B257"
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray="2 14"
        className="hf-flow"
      />
      <circle cx="312" cy="410" r="7" fill="#E5B257" />
      <circle cx="312" cy="410" r="14" fill="#E5B257" opacity="0.25" />
      <circle cx="450" cy="500" r="6" fill="#E5B257" />
    </svg>
  );
}
