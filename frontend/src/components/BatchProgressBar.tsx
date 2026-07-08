import type { BatchProgress } from '../types'
import DocumentStatusBadge from './DocumentStatusBadge'

export default function BatchProgressBar({ progress }: { progress: BatchProgress }) {
  const { total, eligible, not_eligible, review_required, failed, processing, queued, progress_percent } = progress

  return (
    <div>
      <div className="flex items-center gap-3" style={{ marginBottom: '12px' }}>
        <span style={{ fontWeight: 700, fontSize: '15px' }}>{progress_percent}% complete</span>
        <DocumentStatusBadge status={progress.status} />
        <span className="text-muted text-sm ml-auto">{total} total documents</span>
      </div>

      {/* Main progress bar */}
      <div style={{ height: '8px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden', display: 'flex', marginBottom: '16px' }}>
        {total > 0 && (
          <>
            <div style={{ width: `${(eligible / total) * 100}%`, background: 'var(--eligible)', transition: 'width 0.5s ease' }} />
            <div style={{ width: `${(not_eligible / total) * 100}%`, background: 'var(--not-eligible)', transition: 'width 0.5s ease' }} />
            <div style={{ width: `${(review_required / total) * 100}%`, background: 'var(--review)', transition: 'width 0.5s ease' }} />
            <div style={{ width: `${(failed / total) * 100}%`, background: 'var(--failed)', transition: 'width 0.5s ease' }} />
            <div style={{ width: `${(processing / total) * 100}%`, background: 'var(--processing)', transition: 'width 0.5s ease' }} />
          </>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        {[
          { label: 'Eligible', count: eligible, color: 'var(--eligible)' },
          { label: 'Not Eligible', count: not_eligible, color: 'var(--not-eligible)' },
          { label: 'Review', count: review_required, color: 'var(--review)' },
          { label: 'Processing', count: processing, color: 'var(--processing)' },
          { label: 'Queued', count: queued, color: 'var(--queued)' },
          { label: 'Failed', count: failed, color: 'var(--failed)' },
        ].map(item => (
          <div key={item.label} className="flex items-center gap-2">
            <div style={{ width: 10, height: 10, background: item.color, borderRadius: '50%', flexShrink: 0 }} />
            <span style={{ fontSize: '12.5px', color: 'var(--text-secondary)' }}>{item.label}: </span>
            <span style={{ fontSize: '12.5px', fontWeight: 700, color: item.color }}>{item.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
