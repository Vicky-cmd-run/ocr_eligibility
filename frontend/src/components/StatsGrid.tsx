interface StatsItem {
  label: string
  value: number
  color: string
  sub?: string
}

export default function StatsGrid({ items }: { items: StatsItem[] }) {
  return (
    <div className="stats-grid">
      {items.map(item => (
        <div key={item.label} className="stat-card">
          <div className="stat-label">{item.label}</div>
          <div className="stat-value" style={{ color: item.color }}>{item.value.toLocaleString()}</div>
          {item.sub && <div className="stat-sub">{item.sub}</div>}
        </div>
      ))}
    </div>
  )
}
