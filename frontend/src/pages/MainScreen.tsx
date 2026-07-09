import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { Upload, FileSpreadsheet, Eye, Clock, Trash2, ChevronDown, CheckCircle, AlertTriangle, X } from 'lucide-react'
import {
  createBatch, uploadFiles, getBatch, getBatchProgress,
  getBatchResults, listBatches, exportXlsx
} from '../api/client'
import type { DocumentRow, Batch } from '../types'
import DocumentStatusBadge from '../components/DocumentStatusBadge'
import BatchProgressBar from '../components/BatchProgressBar'
import { formatDistanceToNow, fmtPct } from '../utils'

const MAX_FILES = 1000
const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'application/zip': ['.zip'],
  'application/x-zip-compressed': ['.zip'],
}

export default function MainScreen() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(() => {
    return localStorage.getItem('last_batch_id')
  })
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [approvalMode, setApprovalMode] = useState<'auto' | 'manual'>('auto')
  const hasInitializedBatchRef = useRef(false)
  // Fetch past batches list
  const { data: batches = [], refetch: refetchBatches } = useQuery<Batch[]>({
    queryKey: ['batches'],
    queryFn: () => listBatches(0, 100),
  })

  // Fetch current batch details
  const { data: batch } = useQuery<Batch>({
    queryKey: ['batch', selectedBatchId],
    queryFn: () => getBatch(selectedBatchId!),
    enabled: !!selectedBatchId,
    refetchInterval: selectedBatchId ? 3000 : false,
  })

  // Fetch batch progress
  const { data: progress } = useQuery({
    queryKey: ['batch-progress', selectedBatchId],
    queryFn: () => getBatchProgress(selectedBatchId!),
    enabled: !!selectedBatchId && batch?.status === 'PROCESSING',
    refetchInterval: selectedBatchId ? 3000 : false,
  })

  // Fetch results table
  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ['batch-results', selectedBatchId],
    queryFn: () => getBatchResults(selectedBatchId!, { skip: 0, limit: 1000 }),
    enabled: !!selectedBatchId,
    refetchInterval: selectedBatchId ? 3000 : false,
  })

  // Save selected batch to localStorage
  useEffect(() => {
    if (selectedBatchId) {
      localStorage.setItem('last_batch_id', selectedBatchId)
    } else {
      localStorage.removeItem('last_batch_id')
    }
  }, [selectedBatchId])

  // Select the latest batch automatically on initial load if none saved
  useEffect(() => {
    if (!hasInitializedBatchRef.current && batches.length > 0) {
      hasInitializedBatchRef.current = true
      if (!selectedBatchId) {
        setSelectedBatchId(batches[0].id)
      }
    }
  }, [batches, selectedBatchId])

  const onDrop = useCallback(async (accepted: File[], rejected: any[]) => {
    if (rejected.length > 0) {
      toast.error(`${rejected.length} file(s) rejected — only PDF, JPG, PNG, ZIP allowed`)
    }
    if (accepted.length === 0) return
    if (accepted.length > MAX_FILES) {
      toast.error(`Maximum ${MAX_FILES} files allowed at once`)
      return
    }

    setUploading(true)
    setUploadProgress(0)

    try {
      // Auto-create batch
      const dateStr = new Date().toLocaleString()
      const newBatch = await createBatch({
        name: `Upload — ${dateStr}`,
        cutoff_formula: 'pcm_average',
        math_mode: 'combined',
        eligibility_threshold: 50.0,
      })

      // Chunked upload
      const chunkSize = 50
      const chunks: File[][] = []
      for (let i = 0; i < accepted.length; i += chunkSize) {
        chunks.push(accepted.slice(i, i + chunkSize))
      }

      for (let i = 0; i < chunks.length; i++) {
        await uploadFiles(newBatch.id, chunks[i])
        setUploadProgress(Math.round(((i + 1) / chunks.length) * 100))
      }

      toast.success(`Successfully uploaded and queued ${accepted.length} files!`)
      setSelectedBatchId(newBatch.id)
      refetchBatches()
      qc.invalidateQueries({ queryKey: ['batch', newBatch.id] })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }, [refetchBatches, qc])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  })

  const docs: DocumentRow[] = results?.documents || []

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '12px 24px' }}>
      
      {/* Upload Zone */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div className="card-title" style={{ margin: 0 }}><Upload size={16} /> Upload Marksheets</div>
          
          {/* History selector */}
          {batches.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="text-muted text-sm">View past uploads:</span>
              <select
                className="input"
                style={{ width: '220px', padding: '6px 12px', fontSize: '12.5px', height: 'auto' }}
                value={selectedBatchId || ''}
                onChange={(e) => setSelectedBatchId(e.target.value || null)}
              >
                <option value="">-- Start Fresh (New Batch) --</option>
                {batches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name || `Batch ${b.id.slice(0, 8)}`} ({b.total_documents} files)
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
          <input {...getInputProps()} />
          <div className="dropzone-icon">📥</div>
          <h3>{isDragActive ? 'Drop your files here...' : 'Upload PDF / ZIP / Image files'}</h3>
          <p>Drag and drop marksheets here, or click to choose files</p>
          <p className="text-muted text-sm mt-2">Supports PDFs, ZIP folders, and images (JPG, PNG) • Max size 50MB</p>
        </div>

        {uploading && (
          <div style={{ marginTop: '20px' }}>
            <div className="flex items-center gap-2" style={{ marginBottom: '8px' }}>
              <div className="spinner" />
              <span style={{ fontSize: '13.5px', fontWeight: 600 }}>Uploading & Unpacking Files... {uploadProgress}%</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* Progress Section */}
      {batch && batch.status === 'PROCESSING' && progress && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <BatchProgressBar progress={progress} />
        </div>
      )}

      {/* Results Table */}
      {selectedBatchId && (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Screening Results
              </h3>
              <p className="text-muted text-sm mt-2">
                Processed {docs.length} marksheets • Formula: PCM Average (&gt;50% threshold)
              </p>
            </div>

            {/* Action buttons (Toggle + Download Excel) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {/* Approval Mode Toggle */}
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--bg-secondary)', padding: '4px 10px', borderRadius: '16px', border: '1px solid var(--border-color)' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)' }}>Approval:</span>
                <button
                  type="button"
                  onClick={() => setApprovalMode(approvalMode === 'auto' ? 'manual' : 'auto')}
                  className="btn"
                  style={{
                    borderRadius: '12px',
                    padding: '2px 8px',
                    fontSize: '11px',
                    margin: 0,
                    height: 'auto',
                    background: approvalMode === 'auto' ? 'var(--btn-primary-bg)' : 'var(--btn-secondary-bg)',
                    color: approvalMode === 'auto' ? 'var(--btn-primary-text)' : 'var(--btn-secondary-text)',
                    border: 'none',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {approvalMode === 'auto' ? '⚡ Auto' : '👤 Manual'}
                </button>
              </div>

              {docs.length > 0 && (
                <a
                  href={exportXlsx(selectedBatchId, undefined, approvalMode)}
                  className="btn btn-primary btn-sm"
                  download
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                >
                  <FileSpreadsheet size={15} /> Download Excel
                </a>
              )}

              <button
                type="button"
                onClick={() => {
                  setSelectedBatchId(null)
                  localStorage.removeItem('last_batch_id')
                }}
                className="btn btn-secondary btn-sm"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', margin: 0 }}
                title="Close Results Panel"
              >
                <X size={15} /> Close
              </button>
            </div>
          </div>

          {resultsLoading ? (
            <div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" /></div>
          ) : docs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📄</div>
              <h3>No marksheets processed yet</h3>
              <p>Upload a PDF or ZIP file above to begin eligibility calculation.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Student's Name</th>
                    <th>Application Number</th>
                    <th>Percentage</th>
                    <th>Eligibility Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((doc) => {
                    const overallPct = doc.extraction?.overall_percentage
                    
                    // Resolve status based on approvalMode
                    const getResolvedStatus = () => {
                      const status = doc.eligibility?.status || doc.status
                      if (doc.eligibility?.is_manually_reviewed || doc.eligibility?.override_status) {
                        return doc.eligibility?.override_status || status
                      }
                      if (approvalMode === 'auto' && status === 'REVIEW_REQUIRED') {
                        const threshold = doc.eligibility?.eligibility_threshold ?? 50.0
                        if (overallPct != null) {
                          return overallPct > threshold ? 'ELIGIBLE' : 'NOT_ELIGIBLE'
                        }
                        return 'NOT_ELIGIBLE'
                      }
                      return status
                    }
                    
                    const eligibilityStatus = getResolvedStatus()
                    return (
                      <tr key={doc.id}>
                        <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {doc.candidate?.name || (
                            doc.status === 'FAILED' ? (
                              <span style={{ color: 'var(--not-eligible)', fontSize: '13.5px' }}>Upload Error</span>
                            ) : (
                              <span className="text-muted">Unknown</span>
                            )
                          )}
                          {doc.status === 'FAILED' && doc.error_message && (
                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 'normal', marginTop: '4px' }}>
                              {doc.error_message}
                            </div>
                          )}
                        </td>
                        <td>
                          {doc.candidate?.register_number || <span className="text-muted">N/A</span>}
                        </td>
                        <td style={{ fontWeight: 600 }}>
                          {overallPct != null ? `${overallPct.toFixed(2)}%` : <span className="text-muted">—</span>}
                        </td>
                        <td>
                          <DocumentStatusBadge status={eligibilityStatus} />
                        </td>
                        <td>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => navigate(`/documents/${doc.id}/review`)}
                            style={{ padding: '4px 10px', fontSize: '12px' }}
                          >
                            <Eye size={12} /> Review
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
