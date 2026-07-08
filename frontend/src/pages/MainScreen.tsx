import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { Upload, FileSpreadsheet, Eye, Clock, Trash2, ChevronDown, CheckCircle, AlertTriangle } from 'lucide-react'
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

  // Fetch past batches list
  const { data: batches = [], refetch: refetchBatches } = useQuery({
    queryKey: ['batches-list'],
    queryFn: () => listBatches(0, 100),
  })

  // Fetch current batch details
  const { data: batch } = useQuery({
    queryKey: ['batch', selectedBatchId],
    queryFn: () => getBatch(selectedBatchId!),
    enabled: !!selectedBatchId,
    refetchInterval: (b) => (b?.state?.data?.status === 'PROCESSING' ? 3000 : false),
  })

  // Fetch batch progress
  const { data: progress } = useQuery({
    queryKey: ['batch-progress', selectedBatchId],
    queryFn: () => getBatchProgress(selectedBatchId!),
    enabled: !!selectedBatchId && batch?.status === 'PROCESSING',
    refetchInterval: 3000,
  })

  // Fetch results table
  const { data: results, isLoading: resultsLoading } = useQuery({
    queryKey: ['batch-results', selectedBatchId],
    queryFn: () => getBatchResults(selectedBatchId!, { skip: 0, limit: 1000 }),
    enabled: !!selectedBatchId,
    refetchInterval: (r) => (batch?.status === 'PROCESSING' ? 5000 : false),
  })

  // Save selected batch to localStorage
  useEffect(() => {
    if (selectedBatchId) {
      localStorage.setItem('last_batch_id', selectedBatchId)
    } else {
      localStorage.removeItem('last_batch_id')
    }
  }, [selectedBatchId])

  // Select the latest batch automatically if none selected and batches exist
  useEffect(() => {
    if (!selectedBatchId && batches.length > 0) {
      setSelectedBatchId(batches[0].id)
    }
  }, [batches, selectedBatchId])

  const onDrop = useCallback(async (accepted: File[], rejected: File[]) => {
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

            {/* Download Spreadsheet Button */}
            {docs.length > 0 && (
              <a
                href={exportXlsx(selectedBatchId)}
                className="btn btn-primary btn-sm"
                download
                style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
              >
                <FileSpreadsheet size={15} /> Download Excel
              </a>
            )}
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
                    const eligibilityStatus = doc.eligibility?.status || doc.status
                    return (
                      <tr key={doc.id}>
                        <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {doc.candidate?.name || <span className="text-muted">Unknown</span>}
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
