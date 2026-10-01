/**
 * A compact circular readiness gauge (0–100%). The arc uses the tenant accent;
 * the track is a neutral tint of it so the ring reads on any brand colour.
 */
interface ReadinessRingProps {
  value: number
}

export function ReadinessRing({ value }: ReadinessRingProps) {
  const pct = Math.max(0, Math.min(100, value))
  return (
    <div
      className="grid place-items-center rounded-full"
      style={{
        width: 72,
        height: 72,
        background: `conic-gradient(var(--tenant-accent) ${pct * 3.6}deg, color-mix(in srgb, var(--tenant-accent) 14%, white) 0deg)`,
      }}
      role="img"
      aria-label={`Readiness ${pct} percent`}
    >
      <div className="grid h-14 w-14 place-items-center rounded-full bg-white">
        <div className="text-center leading-none">
          <div className="text-lg font-bold text-ink">
            {pct}
            <span className="text-[10px] text-ink-soft">%</span>
          </div>
          <div className="mt-0.5 font-mono text-[7px] tracking-[0.12em] text-ink-soft">READY</div>
        </div>
      </div>
    </div>
  )
}
