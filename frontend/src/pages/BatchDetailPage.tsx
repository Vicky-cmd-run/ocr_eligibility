import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Download, RefreshCw, Eye, AlertTriangle } from 'lucide-react'
import { getBatch, getBatchProgress, getBatchResults, exportCsv, exportXlsx } from '../api/client'
import type { DocumentRow } from '../types'
import DocumentStatusBadge from '../components/DocumentStatusBadge'
import BatchProgressBar from '../components/BatchProgressBar'
import ConfidenceBar from '../components/ConfidenceBar'
import { formatDistanceToNow, fmtPct } from '../utils'

const STATUS_TABS = ['ALL', 'ELIGIBLE', 'NOT_ELIGIBLE', 'REVIEW_REQUIRED', 'FAILED', 'QUEUED', 'PROCESSING']

export default function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('ALL')
  const [page, setPage] = useState(0)
  const limit = 50

  const { data: batch } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => getBatch(batchId!),
    refetchInterval: 4000,
    enabled: !!batchId,
  })

  const { data: progress } = useQuery({
    queryKey: ['batch-progress', batchId],
    queryFn: () => getBatchProgress(batchId!),
    refetchInterval: 3000,
    enabled: !!batchId,
  })

  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ['batch-results', batchId, activeTab, page],
    queryFn: () => getBatchResults(batchId!, {
      status: activeTab === 'ALL' ? undefined : activeTab,
      skip: page * limit,
      limit,
    }),
    refetchInterval: 5000,
    enabled: !!batchId,
  })

  if (!batch) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div className="spinner" />
      </div>
    )
  }

  const docs: DocumentRow[] = results?.documents || []
  const total = results?.total || 0
  const totalPages = Math.ceil(total / limit)

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <Link to="/" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '13px' }}>← Batches</Link>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <h2 style={{ margin: 0 }}>{batch.name || `Batch ${batch.id.slice(0, 8)}`}</h2>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <p style={{ margin: 0 }}>
            Created {formatDistanceToNow(batch.created_at)} •
            Formula: <strong>{batch.cutoff_formula === 'pcm_average' ? 'PCM Average' : 'Engineering 200'}</strong> •
            Threshold: <strong>&gt;{batch.eligibility_threshold}%</strong>
          </p>
          <div className="flex gap-2 ml-auto">
            <a href={exportCsv(batchId!)} className="btn btn-secondary btn-sm" download>
              <Download size={13} /> CSV
            </a>
            <a href={exportXlsx(batchId!)} className="btn btn-secondary btn-sm" download>
              <Download size={13} /> Excel
            </a>
          </div>
        </div>
      </div>

      {/* Progress */}
      {progress && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <BatchProgressBar progress={progress} />
        </div>
      )}

      {/* Results table */}
      <div className="card">
        {/* Tabs */}
        <div className="tabs">
          {STATUS_TABS.map(tab => (
            <button
              key={tab}
              className={`tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => { setActiveTab(tab); setPage(0) }}
            >
              {tab.replace('_', ' ')}
              {tab !== 'ALL' && progress && (
                <span style={{ marginLeft: '5px', opacity: 0.6, fontSize: '11px' }}>
                  ({getCount(progress, tab)})
                </span>
              )}
            </button>
          ))}
        </div>

        {resultsLoading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" /></div>
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <h3>No documents</h3>
            <p>No documents match the selected filter.</p>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Candidate</th>
                    <th>Reg. No.</th>
                    <th>Physics %</th>
                    <th>Chemistry %</th>
                    <th>Maths %</th>
                    <th>PCM Cutoff</th>
                    <th>Overall %</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map(doc => (
                    <tr key={doc.id}>
                      <td>
                        <span className="truncate" title={doc.original_filename}>
                          {doc.original_filename}
                        </span>
                        {doc.error_message && (
                          <div className="text-sm" style={{ color: 'var(--not-eligible)', marginTop: '2px' }}>
                            {doc.error_message.slice(0, 60)}
                          </div>
                        )}
                      </td>
                      <td>{doc.candidate?.name || <span className="text-muted">—</span>}</td>
                      <td>{doc.candidate?.register_number || <span className="text-muted">—</span>}</td>
                      <td><PctCell value={doc.extraction?.physics_percentage} passed={doc.eligibility?.physics_passed} /></td>
                      <td><PctCell value={doc.extraction?.chemistry_percentage} passed={doc.eligibility?.chemistry_passed} /></td>
                      <td><PctCell value={doc.extraction?.mathematics_percentage} passed={doc.eligibility?.mathematics_passed} /></td>
                      <td>{fmtPct(doc.extraction?.pcm_cutoff)}</td>
                      <td><PctCell value={doc.extraction?.overall_percentage} passed={doc.eligibility?.overall_passed} /></td>
                      <td style={{ minWidth: '110px' }}>
                        <ConfidenceBar value={doc.extraction?.combined_confidence ?? null} />
                      </td>
                      <td><DocumentStatusBadge status={doc.status} /></td>
                      <td>
                        <div className="flex gap-2">
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => navigate(`/documents/${doc.id}/review`)}
                          >
                            <Eye size={12} /> Review
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center gap-2" style={{ marginTop: '16px', justifyContent: 'center' }}>
                <button className="btn btn-secondary btn-sm" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
                <span className="text-muted text-sm">Page {page + 1} of {totalPages} ({total} total)</span>
                <button className="btn btn-secondary btn-sm" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

function PctCell({ value, passed }: { value: number | null | undefined; passed: boolean | null | undefined }) {
  if (value == null) return <span className="text-muted">—</span>
  const color = passed === true ? 'var(--eligible)' : passed === false ? 'var(--not-eligible)' : 'var(--text-secondary)'
  return <span style={{ color, fontWeight: 600 }}>{value.toFixed(1)}%</span>
}

function getCount(progress: any, tab: string): number {
  const map: Record<string, string> = {
    ELIGIBLE: 'eligible', NOT_ELIGIBLE: 'not_eligible',
    REVIEW_REQUIRED: 'review_required', FAILED: 'failed',
    QUEUED: 'queued', PROCESSING: 'processing',
  }
  return progress[map[tab]] ?? 0
}
