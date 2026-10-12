/** A decorative mineral cut; geometry never represents a measured deposit. */
export function MineralCrystal() {
  return (
    <div className="mineral-crystal" aria-hidden="true">
      <svg viewBox="0 0 120 160">
        <defs>
          <linearGradient id="crystal-facet" x1="0" x2="1" y1="0" y2="1">
            <stop stopColor="var(--gold)" stopOpacity=".65" />
            <stop offset="1" stopColor="var(--accent)" stopOpacity=".05" />
          </linearGradient>
        </defs>
        <path
          d="M60 7 99 45 93 113 60 151 23 112 19 47Z"
          fill="url(#crystal-facet)"
          stroke="var(--gold)"
          strokeWidth=".7"
        />
        <path
          d="M60 7 43 53 60 116 79 54ZM19 47 43 53 23 112 60 116 93 113 79 54 99 45M43 53 79 54M60 116 60 151"
          fill="none"
          stroke="var(--gold)"
          strokeWidth=".7"
          opacity=".85"
        />
        <path
          d="M60 7 79 54 99 45M43 53 60 116 23 112"
          fill="var(--gold)"
          opacity=".12"
        />
      </svg>
      <span />
    </div>
  );
}
