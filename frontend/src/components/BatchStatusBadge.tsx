import type { BatchStatus } from '../types'
import DocumentStatusBadge from './DocumentStatusBadge'

export default function BatchStatusBadge({ status }: { status: BatchStatus }) {
  return <DocumentStatusBadge status={status} />
}
