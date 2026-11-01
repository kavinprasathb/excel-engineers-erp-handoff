/**
 * The sign-in artwork: a centrifugal pump set and a gate valve drawn as an
 * engineering blueprint. Water runs through the pipework and the impeller
 * turns; both stop for people who ask for reduced motion.
 */
export function PumpScene({ className = "" }: { className?: string }) {
  const vanes = Array.from({ length: 6 }, (_, i) => i * 60);
  return (
    <svg viewBox="0 0 640 440" className={className} role="img" aria-label="Centrifugal pump set and gate valve, drawn as a blueprint">
      <defs>
        <linearGradient id="ps-metal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9cc4ff" stopOpacity="0.22" />
          <stop offset="1" stopColor="#9cc4ff" stopOpacity="0.04" />
        </linearGradient>
        <radialGradient id="ps-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#5ee0ff" stopOpacity="0.35" />
          <stop offset="1" stopColor="#5ee0ff" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g fill="none" stroke="#9cc4ff" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
        {/* Suction pipe, flanged into the pump eye */}
        <path d="M0 282H158M0 318H158" />
        <rect x="150" y="272" width="12" height="56" rx="2" fill="url(#ps-metal)" />
        <rect x="164" y="272" width="12" height="56" rx="2" fill="url(#ps-metal)" />

        {/* Volute casing with its discharge nozzle */}
        <path
          d="M262 175c52 0 92 38 92 88s-40 90-92 90-92-40-92-90c0-40 26-72 62-84V120h56v58"
          fill="url(#ps-metal)"
        />
        <rect x="222" y="108" width="76" height="12" rx="2" fill="url(#ps-metal)" />
        <circle cx="262" cy="265" r="70" fill="url(#ps-glow)" stroke="none" />

        {/* Impeller */}
        <g className="ps-spin" style={{ transformOrigin: "262px 265px" }}>
          <circle cx="262" cy="265" r="54" strokeOpacity="0.55" />
          {vanes.map((a) => (
            <path key={a} d="M262 265c10-14 26-22 44-24" transform={`rotate(${a} 262 265)`} stroke="#cfe2ff" />
          ))}
          <circle cx="262" cy="265" r="12" fill="#0f2a5c" stroke="#cfe2ff" />
        </g>

        {/* Coupling guard and motor */}
        <rect x="354" y="238" width="30" height="54" rx="4" fill="url(#ps-metal)" />
        <rect x="384" y="208" width="150" height="114" rx="14" fill="url(#ps-metal)" />
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <path key={i} d={`M${402 + i * 19} 214v102`} strokeOpacity="0.4" />
        ))}
        <rect x="440" y="188" width="44" height="20" rx="3" fill="url(#ps-metal)" />
        <path d="M534 250h14v30h-14" />

        {/* Base plate and feet */}
        <path d="M190 352h14v20M320 352h-14v20M404 322v50M514 322v50" />
        <rect x="150" y="372" width="400" height="16" rx="3" fill="url(#ps-metal)" />
        <path d="M130 396h440" strokeOpacity="0.4" strokeDasharray="2 6" />

        {/* Discharge riser, bend and header */}
        <path d="M236 108V70a24 24 0 0 1 24-24h120M288 108V92a10 10 0 0 1 10-10h82" />
        <rect x="380" y="36" width="12" height="56" rx="2" fill="url(#ps-metal)" />
        <rect x="486" y="36" width="12" height="56" rx="2" fill="url(#ps-metal)" />
        <path d="M498 46H640M498 82H640" />

        {/* Gate valve: body, bonnet, stem and handwheel */}
        <path d="M392 46h22l25-18 25 18h22v36h-22l-25 18-25-18h-22z" fill="url(#ps-metal)" />
        <rect x="427" y="0" width="24" height="28" rx="3" fill="url(#ps-metal)" transform="translate(0 0)" />
        <path d="M439 0v-6" />
        <g className="ps-wheel" style={{ transformOrigin: "439px 64px" }}>
          <circle cx="439" cy="64" r="11" strokeOpacity="0.8" />
          <path d="M428 64h22M439 53v22" strokeOpacity="0.6" />
        </g>
      </g>

      {/* Water moving through the pipework */}
      <g fill="none" stroke="#5ee0ff" strokeWidth="2.4" strokeLinecap="round" className="ps-flow">
        <path d="M0 300H150" />
        <path d="M262 180V78a18 18 0 0 1 18-18h100M392 64h94M498 64H640" />
      </g>

      {/* Dimension marks, as on a drawing sheet */}
      <g fill="#9cc4ff" fillOpacity="0.55" fontFamily="ui-monospace, Consolas, monospace" fontSize="11">
        <path d="M170 410h184" stroke="#9cc4ff" strokeOpacity="0.4" />
        <path d="M170 404v12M354 404v12" stroke="#9cc4ff" strokeOpacity="0.4" />
        <text x="262" y="430" textAnchor="middle">DN 100 · 2900 rpm</text>
        <text x="4" y="270">SUCTION</text>
        <text x="560" y="34" textAnchor="end">DISCHARGE</text>
      </g>
    </svg>
  );
}
