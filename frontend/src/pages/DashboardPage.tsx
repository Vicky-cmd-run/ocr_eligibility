import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listBatches } from '../api/client'
import type { Batch } from '../types'
import { formatDistanceToNow } from '../utils'
import BatchStatusBadge from '../components/BatchStatusBadge'
import StatsGrid from '../components/StatsGrid'

export default function DashboardPage() {
  const { data: batches = [], isLoading } = useQuery({
    queryKey: ['batches'],
    queryFn: () => listBatches(0, 50),
    refetchInterval: 5000,
  })

  // Aggregate stats across all batches
  const stats = batches.reduce(
    (acc, b) => ({
      total: acc.total + b.total_documents,
      eligible: acc.eligible + b.eligible_count,
      not_eligible: acc.not_eligible + b.not_eligible_count,
      review: acc.review + b.review_required_count,
      failed: acc.failed + b.failed_count,
      processing: acc.processing + b.processing_count,
    }),
    { total: 0, eligible: 0, not_eligible: 0, review: 0, failed: 0, processing: 0 }
  )

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of all marksheet processing batches</p>
      </div>

      <StatsGrid
        items={[
          { label: 'Total Processed', value: stats.total, color: '#4f9eff' },
          { label: 'Eligible', value: stats.eligible, color: '#10b981' },
          { label: 'Not Eligible', value: stats.not_eligible, color: '#ef4444' },
          { label: 'Review Required', value: stats.review, color: '#f59e0b' },
          { label: 'Processing', value: stats.processing, color: '#06b6d4' },
          { label: 'Failed', value: stats.failed, color: '#6b7280' },
        ]}
      />

      <div className="card">
        <div className="card-title">
          Recent Batches
          <Link to="/batches/new" className="btn btn-primary btn-sm ml-auto">
            + New Batch
          </Link>
        </div>

        {isLoading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div className="spinner" />
          </div>
        ) : batches.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📂</div>
            <h3>No batches yet</h3>
            <p>Upload your first batch of marksheets to get started.</p>
            <Link to="/batches/new" className="btn btn-primary mt-4">
              Upload Marksheets
            </Link>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Batch Name</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Eligible</th>
                  <th>Not Eligible</th>
                  <th>Review</th>
                  <th>Failed</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((batch) => (
                  <tr key={batch.id}>
                    <td>
                      <Link to={`/batches/${batch.id}`} style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                        {batch.name || `Batch ${batch.id.slice(0, 8)}`}
                      </Link>
                    </td>
                    <td><BatchStatusBadge status={batch.status} /></td>
                    <td>{batch.total_documents}</td>
                    <td style={{ color: 'var(--eligible)' }}>{batch.eligible_count}</td>
                    <td style={{ color: 'var(--not-eligible)' }}>{batch.not_eligible_count}</td>
                    <td style={{ color: 'var(--review)' }}>{batch.review_required_count}</td>
                    <td style={{ color: 'var(--failed)' }}>{batch.failed_count}</td>
                    <td className="text-muted text-sm">{formatDistanceToNow(batch.created_at)}</td>
                    <td>
                      <Link to={`/batches/${batch.id}`} className="btn btn-secondary btn-sm">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
