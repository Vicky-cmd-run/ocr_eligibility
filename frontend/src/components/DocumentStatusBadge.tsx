import type { DocumentStatus, BatchStatus, EligibilityStatus } from '../types'

type AnyStatus = DocumentStatus | BatchStatus | EligibilityStatus | string

function getStatusClass(status: AnyStatus): string {
  const map: Record<string, string> = {
    ELIGIBLE: 'badge-eligible',
    COMPLETED: 'badge-eligible',
    NOT_ELIGIBLE: 'badge-not-eligible',
    FAILED: 'badge-failed',
    REVIEW_REQUIRED: 'badge-review',
    PARTIALLY_FAILED: 'badge-review',
    QUEUED: 'badge-queued',
    PENDING: 'badge-queued',
    PROCESSING: 'badge-processing',
  }
  return map[status] || 'badge-queued'
}

function getStatusDot(status: AnyStatus): string {
  const animated = ['PROCESSING', 'QUEUED']
  return animated.includes(status) ? '●' : ''
}

export default function DocumentStatusBadge({ status }: { status: AnyStatus }) {
  return (
    <span className={`badge ${getStatusClass(status)}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
