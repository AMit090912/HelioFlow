/**
 * Landing hero: a Vidarbha rooftop at sunrise — flat RCC roof with parapet, the black
 * water tank on the stair room, a tilted solar array, a neem tree and a Sankranti kite.
 * The sun's ray fan echoes the client's logo. Decorative (aria-hidden), brand palette only.
 */

const SUN = { x: 430, y: 332 };

/** Thin wedges fanned across the upper half, like the logo's rays. */
function rayPaths(count = 25, inner = 104, outer = 252, halfWidthDeg = 2.1) {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const pt = (r: number, deg: number) =>
    `${(SUN.x + r * Math.cos(toRad(deg))).toFixed(1)},${(SUN.y + r * Math.sin(toRad(deg))).toFixed(1)}`;
  return Array.from({ length: count }, (_, i) => {
    const angle = 188 + (i * (352 - 188)) / (count - 1);
    const w = halfWidthDeg * (1 + 0.35 * Math.sin((i / (count - 1)) * Math.PI)); // wider at the top
    return `M${pt(inner, angle - w * 0.4)} L${pt(outer, angle - w)} L${pt(outer, angle + w)} L${pt(inner, angle + w * 0.4)} Z`;
  });
}

const RAYS = rayPaths();

export function RooftopSunrise({ className }: { className?: string }) {
  return (
    // overflow visible: the ground runs past the viewBox to the page edges (parent clips).
    <svg viewBox="0 0 720 540" className={className} style={{ overflow: "visible" }} aria-hidden focusable="false">
      {/* Sun glow, rays and disc */}
      <circle cx={SUN.x} cy={SUN.y} r="236" fill="#E5B257" opacity="0.07" />
      <circle cx={SUN.x} cy={SUN.y} r="168" fill="#E5B257" opacity="0.08" />
      <g fill="#E5B257" opacity="0.92">
        {RAYS.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
      <circle cx={SUN.x} cy={SUN.y} r="84" fill="#F0C46C" />

      {/* Kite with its string (Nagpur's Sankranti skies) */}
      <g transform="translate(150 118) rotate(-12)">
        <path d="M0 -30 L22 0 L0 34 L-22 0 Z" fill="#F6DFA8" />
        <path d="M0 -30 L0 34 M-22 0 L22 0" stroke="#012E2B" strokeWidth="1.5" opacity="0.35" />
        <path d="M0 34 L-6 46 L6 46 Z" fill="#E5B257" />
      </g>
      <path d="M146 152 C 170 230, 120 300, 190 380" fill="none" stroke="#F6DFA8" strokeWidth="1.2" opacity="0.5" />

      {/* Birds */}
      <g fill="none" stroke="#F6DFA8" strokeWidth="2" strokeLinecap="round" opacity="0.7">
        <path d="M560 176 q7 -7 14 0 q7 -7 14 0" />
        <path d="M604 150 q5 -5 10 0 q5 -5 10 0" />
        <path d="M528 206 q4 -4 8 0 q4 -4 8 0" />
      </g>

      {/* Distant skyline with rooftop water tanks */}
      <g fill="#0B4D48">
        <rect x="0" y="352" width="74" height="118" />
        <rect x="62" y="318" width="54" height="152" />
        <rect x="108" y="372" width="70" height="98" />
        <rect x="548" y="330" width="62" height="140" />
        <rect x="602" y="372" width="48" height="98" />
        <rect x="642" y="300" width="78" height="170" />
      </g>
      <g fill="#083E3A">
        <rect x="76" y="300" width="20" height="18" rx="3" />
        <rect x="660" y="282" width="22" height="18" rx="3" />
        <rect x="562" y="314" width="18" height="16" rx="3" />
      </g>

      {/* Ground */}
      <rect x="-2400" y="468" width="5520" height="72" fill="#0A403C" />
      <rect x="-2400" y="468" width="5520" height="3" fill="#E5B257" opacity="0.5" />

      {/* Neem tree */}
      <rect x="606" y="384" width="14" height="86" rx="4" fill="#5B3E2E" />
      <circle cx="612" cy="362" r="50" fill="#1F7A5F" />
      <circle cx="576" cy="390" r="34" fill="#1F7A5F" />
      <circle cx="648" cy="392" r="36" fill="#1F7A5F" />
      <circle cx="598" cy="346" r="22" fill="#2C8C6C" />
      <circle cx="632" cy="374" r="16" fill="#2C8C6C" />

      {/* House */}
      <rect x="132" y="338" width="340" height="132" fill="#F4EDE1" />
      <rect x="432" y="338" width="40" height="132" fill="#E6DCCB" />
      <rect x="122" y="324" width="360" height="18" fill="#E8DCCB" />
      <rect x="122" y="324" width="360" height="4" fill="#D6C6AE" />
      {/* Windows: one lit with morning light */}
      <rect x="168" y="368" width="70" height="60" rx="3" fill="#F6DFA8" />
      <rect x="282" y="368" width="70" height="60" rx="3" fill="#0E4F4A" />
      <path d="M203 368 V428 M168 398 H238 M317 368 V428 M282 398 H352" stroke="#D6C6AE" strokeWidth="4" />
      <rect x="164" y="428" width="78" height="6" rx="2" fill="#D6C6AE" />
      <rect x="278" y="428" width="78" height="6" rx="2" fill="#D6C6AE" />
      {/* Door */}
      <rect x="386" y="384" width="44" height="86" rx="3" fill="#0E4F4A" />
      <circle cx="420" cy="430" r="3" fill="#E5B257" />

      {/* Stair room (mumty) with the black water tank */}
      <rect x="378" y="270" width="86" height="56" fill="#EADFCE" />
      <rect x="372" y="264" width="98" height="10" fill="#D6C6AE" />
      <rect x="392" y="290" width="26" height="36" rx="2" fill="#0E4F4A" />
      <rect x="400" y="226" width="54" height="40" rx="7" fill="#1D2B2A" />
      <ellipse cx="427" cy="227" rx="27" ry="6" fill="#2E3E3D" />
      <path d="M400 240 H454 M400 252 H454" stroke="#2E3E3D" strokeWidth="2" />

      {/* Solar array: two tilted panels on steel legs */}
      <g stroke="#9FB3B0" strokeWidth="3" strokeLinecap="round">
        <path d="M150 300 V326 M240 300 V326 M168 262 L176 326 M256 262 L248 326" />
        <path d="M262 300 V326 M352 300 V326 M280 262 L288 326 M368 262 L360 326" />
      </g>
      {[0, 112].map((dx) => (
        <g key={dx} transform={`translate(${dx} 0)`}>
          <path d="M138 300 L244 300 L262 260 L156 260 Z" fill="#13303A" stroke="#A9BDB9" strokeWidth="2" />
          <path
            d="M164.5 300 L182.5 260 M191 300 L209 260 M217.5 300 L235.5 260 M147 280 H253"
            stroke="#2F5865"
            strokeWidth="1.6"
          />
          <path d="M180 300 L196 300 L214 260 L198 260 Z" fill="#F6DFA8" opacity="0.28" />
        </g>
      ))}

      {/* Tulsi pot on the parapet */}
      <path d="M96 470 V430 H122 V470 Z" fill="#B07A47" />
      <circle cx="109" cy="420" r="14" fill="#2C8C6C" />
      <circle cx="100" cy="428" r="8" fill="#1F7A5F" />
      <circle cx="119" cy="428" r="8" fill="#1F7A5F" />
    </svg>
  );
}
