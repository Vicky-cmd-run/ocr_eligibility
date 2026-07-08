export default function ConfidenceBar({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>—</span>

  const pct = Math.round(value * 100)
  const cls = pct >= 90 ? 'conf-high' : pct >= 75 ? 'conf-med' : 'conf-low'
  const color = pct >= 90 ? 'var(--eligible)' : pct >= 75 ? 'var(--review)' : 'var(--not-eligible)'

  return (
    <div className="confidence-bar">
      <span style={{ fontSize: '12px', fontWeight: 600, color, minWidth: '34px' }}>{pct}%</span>
      <div className="confidence-track">
        <div className={`confidence-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
