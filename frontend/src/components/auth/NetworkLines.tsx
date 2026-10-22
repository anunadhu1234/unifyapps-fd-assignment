/** Decorative flowing lines and connected points along the bottom of the login form. */
const WAVES = [
  'M0 120 C 180 60, 360 150, 560 95 S 900 40, 1200 110',
  'M0 135 C 200 80, 380 165, 580 110 S 920 60, 1200 125',
  'M0 150 C 220 100, 400 180, 600 125 S 940 80, 1200 140',
  'M0 165 C 240 120, 420 195, 620 140 S 960 100, 1200 155',
  'M0 180 C 260 140, 440 210, 640 155 S 980 120, 1200 170',
]

const POINTS: [number, number][] = [
  [60, 40], [130, 95], [210, 30], [270, 120], [90, 150],
  [930, 60], [1010, 20], [1080, 90], [1150, 45], [990, 140],
]
const EDGES: [number, number][] = [
  [0, 1], [1, 2], [1, 3], [0, 4], [1, 4],
  [5, 6], [6, 7], [7, 8], [5, 9], [7, 9],
]

export function NetworkLines() {
  return (
    <svg viewBox="0 0 1200 200" preserveAspectRatio="xMidYMax slice" className="pointer-events-none absolute inset-x-0 bottom-0 h-40 w-full"
      aria-hidden="true">
      <defs>
        <linearGradient id="wave" x1="0" x2="1">
          <stop offset="0" stopColor="#818cf8" />
          <stop offset="0.5" stopColor="#a78bfa" />
          <stop offset="1" stopColor="#38bdf8" />
        </linearGradient>
      </defs>
      {WAVES.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="url(#wave)" strokeWidth="1" opacity={0.18 + i * 0.05} />
      ))}
      {EDGES.map(([a, b], i) => (
        <line key={i} x1={POINTS[a][0]} y1={POINTS[a][1]} x2={POINTS[b][0]} y2={POINTS[b][1]} stroke="#a5b4fc"
          strokeWidth="0.8" opacity="0.45" />
      ))}
      {POINTS.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 3 : 2} fill={i % 2 ? '#818cf8' : '#a78bfa'} opacity="0.7" />
      ))}
    </svg>
  )
}
