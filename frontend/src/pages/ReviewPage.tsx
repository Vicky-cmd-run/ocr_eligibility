import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Save, RefreshCw, ArrowLeft, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { getDocumentReview, submitReview, reprocessDocument, getOcrTokens } from '../api/client'
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

  const { data: ocrTokens = [] } = useQuery({
    queryKey: ['ocr-tokens', documentId],
    queryFn: () => getOcrTokens(documentId!),
    enabled: !!documentId,
  })

  const [corrections, setCorrections] = useState<Record<string, { obtained: string; maximum: string }>>({})
  const [overrideStatus, setOverrideStatus] = useState('')
  const [reviewNotes, setReviewNotes] = useState('')
  
  const [hoveredSubjectId, setHoveredSubjectId] = useState<string | null>(null)
  const [hoveredName, setHoveredName] = useState(false)
  const [imgSize, setImgSize] = useState({ width: 0, height: 0, naturalWidth: 0, naturalHeight: 0 })

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget
    setImgSize({
      width: img.clientWidth,
      height: img.clientHeight,
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
    })
  }

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

  const cleanPath = doc.file_path.replace(/^backend\//, '').replace(/^uploads\//, '')
  const filePreviewUrl = `/uploads/${cleanPath}`

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
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
        <div className="review-preview" style={{ position: 'relative' }}>
          {doc.original_filename?.toLowerCase().endsWith('.pdf') || doc.document_type?.toLowerCase().includes('pdf') ? (
            <object data={filePreviewUrl} type="application/pdf" style={{ width: '100%', height: '100%', minHeight: '600px' }}>
              <p style={{ padding: 20, color: 'var(--text-muted)' }}>PDF preview not available. <a href={filePreviewUrl} target="_blank" rel="noreferrer">Open file</a></p>
            </object>
          ) : (
            <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%' }}>
              <img
                src={filePreviewUrl}
                alt="Document preview"
                onLoad={handleImageLoad}
                style={{ display: 'block', maxWidth: '100%', height: 'auto', borderRadius: '8px' }}
              />
              {/* Highlight overlays */}
              {imgSize.naturalWidth > 0 && imgSize.naturalHeight > 0 && ocrTokens.map((token: any, idx: number) => {
                const scaleX = imgSize.width / imgSize.naturalWidth
                const scaleY = imgSize.height / imgSize.naturalHeight

                const left = token.x_min * scaleX
                const top = token.y_min * scaleY
                const width = (token.x_max - token.x_min) * scaleX
                const height = (token.y_max - token.y_min) * scaleY

                // Check matches
                const isNameMatch = candidate?.name && 
                  candidate.name.toLowerCase().includes(token.text.toLowerCase()) && 
                  token.text.length > 2

                let isSubjectMatch = false
                let isMarkMatch = false
                let isCurrentHovered = false

                for (const sm of marks) {
                  const tokenText = token.text.trim().toLowerCase()
                  const subjRaw = sm.raw_subject_name.trim().toLowerCase()
                  const subjNorm = sm.normalized_subject.trim().toLowerCase()

                  const matchesSubj = (subjRaw.includes(tokenText) || tokenText.includes(subjRaw) || subjNorm.includes(tokenText)) && tokenText.length > 2
                  const matchesObtained = sm.raw_obtained_text && (sm.raw_obtained_text.toLowerCase() === tokenText || sm.raw_obtained_text.toLowerCase().replace(/^0+/, '') === tokenText)
                  const matchesMax = sm.raw_maximum_text && (sm.raw_maximum_text.toLowerCase() === tokenText)

                  if (matchesSubj) {
                    isSubjectMatch = true
                    if (hoveredSubjectId === sm.id) {
                      isCurrentHovered = true
                    }
                  }
                  if (matchesObtained || matchesMax) {
                    isMarkMatch = true
                    if (hoveredSubjectId === sm.id) {
                      isCurrentHovered = true
                    }
                  }
                }

                let bg = 'transparent'
                let border = '1px solid transparent'
                let zIndex = 1

                if (isNameMatch) {
                  bg = hoveredName ? 'rgba(236, 72, 153, 0.35)' : 'rgba(236, 72, 153, 0.15)'
                  border = hoveredName ? '2px solid rgb(236, 72, 153)' : '1px dashed rgba(236, 72, 153, 0.6)'
                  zIndex = 10
                } else if (isCurrentHovered) {
                  bg = isSubjectMatch ? 'rgba(59, 130, 246, 0.45)' : 'rgba(34, 197, 94, 0.45)'
                  border = isSubjectMatch ? '2px solid rgb(59, 130, 246)' : '2px solid rgb(34, 197, 94)'
                  zIndex = 20
                } else if (isSubjectMatch) {
                  bg = 'rgba(59, 130, 246, 0.12)'
                  border = '1px dashed rgba(59, 130, 246, 0.5)'
                } else if (isMarkMatch) {
                  bg = 'rgba(34, 197, 94, 0.12)'
                  border = '1px dashed rgba(34, 197, 94, 0.5)'
                } else {
                  return null
                }

                return (
                  <div
                    key={idx}
                    style={{
                      position: 'absolute',
                      left: `${left}px`,
                      top: `${top}px`,
                      width: `${width}px`,
                      height: `${height}px`,
                      backgroundColor: bg,
                      border: border,
                      pointerEvents: 'none',
                      borderRadius: '3px',
                      zIndex: zIndex,
                      transition: 'all 0.12s ease-in-out',
                    }}
                    title={token.text}
                  />
                )
              })}
            </div>
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
                { label: 'OCR Confidence', value: fmtConf(doc.overall_ocr_confidence) },
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
              <div
                className="review-field"
                onMouseEnter={() => setHoveredName(true)}
                onMouseLeave={() => setHoveredName(false)}
                style={{ cursor: 'help' }}
              >
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
                  <div
                    key={sm.id}
                    className={`review-field ${isSuspicious ? 'suspicious' : ''}`}
                    onMouseEnter={() => setHoveredSubjectId(sm.id)}
                    onMouseLeave={() => setHoveredSubjectId(null)}
                    style={{ background: 'var(--bg-surface)', borderRadius: '10px', padding: '14px', transition: 'transform 0.15s ease' }}
                  >
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
    </div>
  )
}

function getConfColor(val: number | null | undefined): string {
  if (val == null) return 'var(--text-muted)'
  if (val >= 0.9) return 'var(--eligible)'
  if (val >= 0.75) return 'var(--review)'
  return 'var(--not-eligible)'
}
