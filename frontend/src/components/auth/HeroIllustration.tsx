/**
 * Login hero artwork: a glowing database whose data streams up into a floating analytics dashboard.
 * Pure SVG (no image download), so it stays sharp at any size and themes with the brand palette.
 */
const BARS = [52, 78, 64, 96, 72, 118, 88, 134]
const TREND = '0,70 34,58 68,62 102,40 136,46 170,24 204,30 238,10'

export function HeroIllustration() {
  return (
    <svg viewBox="0 0 800 720" className="h-full w-full" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <defs>
        <linearGradient id="cyl-body" x1="0" x2="1">
          <stop offset="0" stopColor="#312e81" />
          <stop offset="0.45" stopColor="#4f46e5" />
          <stop offset="1" stopColor="#1e1b4b" />
        </linearGradient>
        <linearGradient id="cyl-top" x1="0" x2="1">
          <stop offset="0" stopColor="#818cf8" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
        <radialGradient id="floor-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#818cf8" stopOpacity="0.55" />
          <stop offset="1" stopColor="#818cf8" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="beam" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="#a5b4fc" stopOpacity="0.55" />
          <stop offset="1" stopColor="#a5b4fc" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c4b5fd" />
          <stop offset="1" stopColor="#6366f1" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#38bdf8" stopOpacity="0.35" />
          <stop offset="1" stopColor="#38bdf8" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="grid-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a5b4fc" stopOpacity="0" />
          <stop offset="1" stopColor="#a5b4fc" stopOpacity="0.28" />
        </linearGradient>
        <filter id="soft-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>

      {/* perspective floor grid */}
      <g stroke="url(#grid-fade)" strokeWidth="1">
        {Array.from({ length: 13 }, (_, i) => (
          <line key={`v${i}`} x1={400 + (i - 6) * 26} y1={500} x2={400 + (i - 6) * 120} y2={720} />
        ))}
        {[520, 548, 584, 630, 690].map((y) => (
          <line key={`h${y}`} x1={0} y1={y} x2={800} y2={y} />
        ))}
      </g>
      <ellipse cx="400" cy="600" rx="230" ry="60" fill="url(#floor-glow)" />

      {/* orbit ring with data points */}
      <ellipse cx="400" cy="560" rx="250" ry="58" fill="none" stroke="#a5b4fc" strokeOpacity="0.3" strokeDasharray="3 7" />
      {[[160, 548], [640, 572], [300, 615], [530, 505]].map(([x, y]) => (
        <circle key={`${x}`} cx={x} cy={y} r="4" fill="#c4b5fd" />
      ))}

      {/* data streams rising into the dashboard */}
      <rect x="352" y="330" width="96" height="170" fill="url(#beam)" />
      {[[372, 470], [392, 420], [410, 452], [428, 395], [384, 365], [418, 345]].map(([x, y], i) => (
        <rect key={i} x={x} y={y} width="3" height={i % 2 ? 14 : 9} rx="1.5" fill="#e0e7ff" opacity={0.5 + (i % 3) * 0.15} />
      ))}

      {/* database: three stacked cylinders */}
      {[0, 1, 2].map((level) => {
        const y = 560 - level * 46
        return (
          <g key={level}>
            <path d={`M 310 ${y} L 310 ${y + 34} A 90 24 0 0 0 490 ${y + 34} L 490 ${y} Z`} fill="url(#cyl-body)" />
            <ellipse cx="400" cy={y} rx="90" ry="24" fill="url(#cyl-top)" opacity={level === 2 ? 1 : 0.85} />
            <ellipse cx="400" cy={y} rx="90" ry="24" fill="none" stroke="#e0e7ff" strokeOpacity="0.55" />
            <circle cx="462" cy={y + 22} r="3" fill="#a5f3fc" />
          </g>
        )
      })}
      <ellipse cx="400" cy="468" rx="70" ry="16" fill="#c7d2fe" opacity="0.5" filter="url(#soft-glow)" />

      {/* floating dashboard */}
      <g className="motion-safe:animate-[hero-float_7s_ease-in-out_infinite]">
        <rect x="190" y="70" width="420" height="260" rx="18" fill="#ffffff" fillOpacity="0.07" stroke="#e0e7ff" strokeOpacity="0.28" />
        <rect x="190" y="70" width="420" height="34" rx="18" fill="#ffffff" fillOpacity="0.06" />
        {[212, 228, 244].map((x) => <circle key={x} cx={x} cy="87" r="4.5" fill="#a5b4fc" opacity="0.55" />)}
        <rect x="270" y="82" width="120" height="10" rx="5" fill="#e0e7ff" opacity="0.25" />

        {/* KPI tiles */}
        {[0, 1, 2].map((i) => (
          <g key={i} transform={`translate(${212 + i * 132} 120)`}>
            <rect width="120" height="54" rx="10" fill="#ffffff" fillOpacity="0.06" stroke="#e0e7ff" strokeOpacity="0.15" />
            <rect x="12" y="12" width="46" height="6" rx="3" fill="#c7d2fe" opacity="0.45" />
            <rect x="12" y="26" width={[70, 58, 64][i]} height="14" rx="4" fill={['#c4b5fd', '#a5f3fc', '#a5b4fc'][i]} opacity="0.85" />
          </g>
        ))}

        {/* bar chart */}
        <g transform="translate(212 190)">
          <rect width="190" height="122" rx="10" fill="#ffffff" fillOpacity="0.05" />
          {BARS.map((h, i) => (
            <rect key={i} x={14 + i * 21} y={112 - h * 0.72} width="13" height={h * 0.72} rx="3" fill="url(#bar)" />
          ))}
        </g>

        {/* trend line */}
        <g transform="translate(414 190)">
          <rect width="174" height="122" rx="10" fill="#ffffff" fillOpacity="0.05" />
          <g transform="translate(14 22) scale(0.62 1)">
            <polygon points={`0,96 ${TREND} 238,96`} fill="url(#area)" />
            <polyline points={TREND} fill="none" stroke="#7dd3fc" strokeWidth="3" strokeLinejoin="round" />
          </g>
          <circle cx="161.5" cy="32" r="4.5" fill="#e0f2fe" />
        </g>
      </g>

      {/* side cards: donut and mini table */}
      <g className="motion-safe:animate-[hero-float_8s_ease-in-out_infinite_1s]">
        <rect x="58" y="300" width="132" height="132" rx="16" fill="#ffffff" fillOpacity="0.07" stroke="#e0e7ff" strokeOpacity="0.22" />
        <circle cx="124" cy="366" r="36" fill="none" stroke="#312e81" strokeWidth="14" />
        <circle cx="124" cy="366" r="36" fill="none" stroke="#a78bfa" strokeWidth="14" strokeDasharray="140 227" transform="rotate(-90 124 366)" />
        <circle cx="124" cy="366" r="36" fill="none" stroke="#38bdf8" strokeWidth="14" strokeDasharray="52 227" strokeDashoffset="-140" transform="rotate(-90 124 366)" />
      </g>
      <g className="motion-safe:animate-[hero-float_9s_ease-in-out_infinite_2s]">
        <rect x="612" y="250" width="150" height="128" rx="16" fill="#ffffff" fillOpacity="0.07" stroke="#e0e7ff" strokeOpacity="0.22" />
        {[0, 1, 2, 3, 4].map((r) => (
          <g key={r} transform={`translate(628 ${270 + r * 21})`}>
            <rect width="34" height="8" rx="4" fill="#c7d2fe" opacity={r === 0 ? 0.7 : 0.35} />
            <rect x="44" width="38" height="8" rx="4" fill="#c7d2fe" opacity={r === 0 ? 0.7 : 0.25} />
            <rect x="92" width={r === 0 ? 26 : 12 + r * 4} height="8" rx="4" fill={r === 0 ? '#c7d2fe' : '#a5f3fc'} opacity={r === 0 ? 0.7 : 0.55} />
          </g>
        ))}
      </g>
    </svg>
  )
}
