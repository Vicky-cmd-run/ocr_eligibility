import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Save, RefreshCw, ArrowLeft, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { getDocumentReview, submitReview, reprocessDocument } from '../api/client'
import type { SubjectMark } from '../types'
import DocumentStatusBadge from '../components/DocumentStatusBadge'
import { fmtPct, fmtConf } from '../utils'

export default function ReviewPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['review', documentId],
    queryFn: () => getDocumentReview(documentId!),
    enabled: !!documentId,
  })

  const [corrections, setCorrections] = useState<Record<string, { obtained: string; maximum: string }>>({})
  const [overrideStatus, setOverrideStatus] = useState('')
  const [reviewNotes, setReviewNotes] = useState('')

  const submitMutation = useMutation({
    mutationFn: () => submitReview(documentId!, {
      reviewer: 'admin',
      subject_corrections: Object.entries(corrections).map(([id, c]) => ({
        subject_mark_id: id,
        obtained_marks: c.obtained !== '' ? Number(c.obtained) : null,
        maximum_marks: c.maximum !== '' ? Number(c.maximum) : null,
      })),
      override_status: overrideStatus || undefined,
      review_notes: reviewNotes || undefined,
    }),
    onSuccess: (res) => {
      toast.success(`Review saved! Status: ${res.recalculated_eligibility}`)
      qc.invalidateQueries({ queryKey: ['review', documentId] })
      setTimeout(() => navigate(-1), 1200)
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Review failed'),
  })

  const reprocessMutation = useMutation({
    mutationFn: () => reprocessDocument(documentId!),
    onSuccess: () => { toast.success('Requeued for reprocessing'); navigate(-1) },
    onError: (e: any) => toast.error(e?.message || 'Failed to reprocess'),
  })

  if (isLoading) return <div style={{ padding: 60, textAlign: 'center' }}><div className="spinner" /></div>
  if (error || !data) return <div className="empty-state"><p>Failed to load review data</p></div>

  const { document: doc, candidate, extraction_result: er, eligibility_result: el, review_actions } = data
  const marks: SubjectMark[] = candidate?.subject_marks || []

  const updateCorrection = (id: string, field: 'obtained' | 'maximum', value: string) => {
    setCorrections(prev => ({
      ...prev,
      [id]: { ...((prev[id]) || { obtained: '', maximum: '' }), [field]: value },
    }))
  }

  const filePreviewUrl = `/uploads/${doc.file_path.split('/uploads/').pop()}`

  return (
    <>
      <div className="page-header">
        <div className="flex items-center gap-3">
          <button className="btn btn-secondary btn-sm" onClick={() => navigate(-1)}>
            <ArrowLeft size={13} /> Back
          </button>
          <h2 style={{ margin: 0 }}>Manual Review</h2>
          <DocumentStatusBadge status={doc.status as any} />
        </div>
        <p style={{ marginTop: 6 }}>{doc.original_filename} — {doc.document_type} — {doc.page_count} page{doc.page_count !== 1 ? 's' : ''}</p>
      </div>

      <div className="review-layout">
        {/* Left: Document preview */}
        <div className="review-preview">
          {doc.mime_type === 'application/pdf' || doc.document_type?.startsWith('PDF') ? (
            <object data={filePreviewUrl} type="application/pdf" style={{ width: '100%', height: '100%', minHeight: '600px' }}>
              <p style={{ padding: 20, color: 'var(--text-muted)' }}>PDF preview not available. <a href={filePreviewUrl} target="_blank" rel="noreferrer">Open file</a></p>
            </object>
          ) : (
            <img src={filePreviewUrl} alt="Document preview" style={{ maxWidth: '100%', height: 'auto' }} />
          )}
        </div>

        {/* Right: Review panel */}
        <div className="review-panel" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* OCR Confidence */}
          <div className="card">
            <div className="card-title">🎯 OCR Quality</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {[
                { label: 'Combined Confidence', value: fmtConf(er?.combined_confidence) },
                { label: 'OCR Confidence', value: fmtConf(er?.ocr_confidence) },
              ].map(item => (
                <div key={item.label}>
                  <div className="review-field">
                    <label>{item.label}</label>
                    <div className="value" style={{ color: getConfColor(er?.combined_confidence) }}>{item.value}</div>
                  </div>
                </div>
              ))}
            </div>
            {doc.error_message && (
              <div style={{ marginTop: '12px', padding: '10px 14px', background: 'var(--not-eligible-bg)', borderRadius: '8px', color: 'var(--not-eligible)', fontSize: '13px' }}>
                <AlertTriangle size={13} style={{ display: 'inline', marginRight: '6px' }} />
                {doc.error_message}
              </div>
            )}
          </div>

          {/* Candidate info */}
          <div className="card">
            <div className="card-title">👤 Candidate</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div className="review-field">
                <label>Name</label>
                <div className="value">{candidate?.name || '—'}</div>
              </div>
              <div className="review-field">
                <label>Register No.</label>
                <div className="value">{candidate?.register_number || '—'}</div>
              </div>
            </div>
          </div>

          {/* Subject marks correction */}
          <div className="card">
            <div className="card-title">📊 Subject Marks</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {marks.length === 0 && <p className="text-muted">No subject marks extracted.</p>}
              {marks.map(sm => {
                const corr = corrections[sm.id]
                const isSuspicious = sm.is_suspicious
                return (
                  <div key={sm.id} className={`review-field ${isSuspicious ? 'suspicious' : ''}`}
                    style={{ background: 'var(--bg-surface)', borderRadius: '10px', padding: '14px' }}>
                    <div className="flex items-center gap-2" style={{ marginBottom: '10px' }}>
                      <span style={{ fontWeight: 700, fontSize: '13.5px' }}>{sm.normalized_subject}</span>
                      <span className="text-muted text-sm">({sm.raw_subject_name})</span>
                      {isSuspicious && <span style={{ color: 'var(--review)', fontSize: '11px', marginLeft: 'auto' }}>⚠ Suspicious</span>}
                      {sm.is_manually_corrected && <span style={{ color: 'var(--eligible)', fontSize: '11px', marginLeft: 'auto' }}>✓ Corrected</span>}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', alignItems: 'end' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                          Obtained (OCR: {sm.raw_obtained_text ?? '—'})
                        </label>
                        <input
                          className="input"
                          type="number"
                          placeholder={String(sm.obtained_marks ?? '')}
                          value={corr?.obtained ?? ''}
                          onChange={e => updateCorrection(sm.id, 'obtained', e.target.value)}
                          style={{ fontSize: '13px' }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                          Maximum (OCR: {sm.raw_maximum_text ?? '—'})
                        </label>
                        <input
                          className="input"
                          type="number"
                          placeholder={String(sm.maximum_marks ?? '')}
                          value={corr?.maximum ?? ''}
                          onChange={e => updateCorrection(sm.id, 'maximum', e.target.value)}
                          style={{ fontSize: '13px' }}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                          Percentage
                        </label>
                        <div style={{ padding: '9px 13px', background: 'var(--bg-card)', borderRadius: '8px', fontSize: '13px', fontWeight: 700, color: sm.percentage && sm.percentage > 50 ? 'var(--eligible)' : 'var(--not-eligible)' }}>
                          {fmtPct(sm.percentage)}
                        </div>
                      </div>
                    </div>
                    {sm.notes && (
                      <p className="text-sm text-muted" style={{ marginTop: '6px' }}>{sm.notes}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Calculated results */}
          {er && (
            <div className="card">
              <div className="card-title">🧮 Calculated Results</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                {[
                  ['Physics %', er.physics_percentage],
                  ['Chemistry %', er.chemistry_percentage],
                  ['Mathematics %', er.mathematics_percentage],
                  ['PCM Cutoff', er.pcm_cutoff],
                  ['Overall %', er.overall_percentage],
                ].map(([label, val]) => (
                  <div key={label as string} className="review-field">
                    <label>{label}</label>
                    <div className="value" style={{ fontSize: '18px', fontWeight: 700 }}>
                      {val != null ? `${(val as number).toFixed(2)}%` : '—'}
                    </div>
                  </div>
                ))}
              </div>
              {er.missing_subjects && er.missing_subjects.length > 0 && (
                <div style={{ marginTop: '12px', padding: '10px', background: 'var(--review-bg)', borderRadius: '8px', color: 'var(--review)', fontSize: '13px' }}>
                  Missing: {er.missing_subjects.join(', ')}
                </div>
              )}
            </div>
          )}

          {/* Eligibility */}
          {el && (
            <div className="card">
              <div className="card-title">⚖️ Eligibility</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                {[
                  ['Physics', el.physics_passed],
                  ['Chemistry', el.chemistry_passed],
                  ['Mathematics', el.mathematics_passed],
                  ['Overall', el.overall_passed],
                ].map(([label, passed]) => (
                  <div key={label as string} className="flex items-center gap-2">
                    {passed === true ? <CheckCircle size={14} color="var(--eligible)" /> :
                     passed === false ? <XCircle size={14} color="var(--not-eligible)" /> :
                     <AlertTriangle size={14} color="var(--review)" />}
                    <span style={{ fontSize: '13.5px' }}>{label}</span>
                    <span className="text-muted text-sm ml-auto">
                      {passed === true ? 'Passed' : passed === false ? 'Failed' : 'Missing'}
                    </span>
                  </div>
                ))}
              </div>
              {el.rejection_reasons && el.rejection_reasons.length > 0 && (
                <div style={{ padding: '10px', background: 'var(--not-eligible-bg)', borderRadius: '8px', color: 'var(--not-eligible)', fontSize: '12.5px' }}>
                  {el.rejection_reasons.map((r, i) => <div key={i}>• {r}</div>)}
                </div>
              )}
            </div>
          )}

          {/* Override + notes */}
          <div className="card">
            <div className="card-title">✏️ Override & Notes</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                  Force Status (optional)
                </label>
                <select className="input" value={overrideStatus} onChange={e => setOverrideStatus(e.target.value)}>
                  <option value="">Use calculated result</option>
                  <option value="ELIGIBLE">Force ELIGIBLE</option>
                  <option value="NOT_ELIGIBLE">Force NOT_ELIGIBLE</option>
                  <option value="REVIEW_REQUIRED">Keep as REVIEW_REQUIRED</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                  Review Notes
                </label>
                <textarea
                  className="input"
                  rows={3}
                  placeholder="Add notes about this review..."
                  value={reviewNotes}
                  onChange={e => setReviewNotes(e.target.value)}
                  style={{ resize: 'vertical' }}
                />
              </div>
              <div className="flex gap-2">
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, justifyContent: 'center' }}
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending}
                >
                  {submitMutation.isPending ? <div className="spinner" /> : <Save size={14} />}
                  Save Review
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => reprocessMutation.mutate()}
                  disabled={reprocessMutation.isPending}
                  title="Requeue for full reprocessing"
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Audit trail */}
          {review_actions && review_actions.length > 0 && (
            <div className="card">
              <div className="card-title">📋 Audit Trail</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {review_actions.map(action => (
                  <div key={action.id} style={{ padding: '10px', background: 'var(--bg-surface)', borderRadius: '8px', fontSize: '12.5px' }}>
                    <div className="flex items-center gap-2">
                      <strong>{action.action_type}</strong>
                      <span className="text-muted">by {action.reviewer || 'system'}</span>
                      <span className="text-muted ml-auto">{new Date(action.created_at).toLocaleString()}</span>
                    </div>
                    {action.notes && <p className="text-muted" style={{ marginTop: '4px' }}>{action.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function getConfColor(val: number | null | undefined): string {
  if (val == null) return 'var(--text-muted)'
  if (val >= 0.9) return 'var(--eligible)'
  if (val >= 0.75) return 'var(--review)'
  return 'var(--not-eligible)'
}
