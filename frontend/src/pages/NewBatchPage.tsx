import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { Upload, FileText, X, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { createBatch, uploadFiles } from '../api/client'
import type { UploadFileResult } from '../types'

const MAX_FILES = 1000
const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
}

export default function NewBatchPage() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<File[]>([])
  const [batchName, setBatchName] = useState('')
  const [cutoffFormula, setCutoffFormula] = useState('pcm_average')
  const [mathMode, setMathMode] = useState('combined')
  const [threshold, setThreshold] = useState(50)
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<UploadFileResult[] | null>(null)
  const [progress, setProgress] = useState(0)

  const onDrop = useCallback((accepted: File[], rejected: File[]) => {
    if (rejected.length > 0) {
      toast.error(`${rejected.length} file(s) rejected — only PDF, JPG, PNG allowed`)
    }
    if (accepted.length + files.length > MAX_FILES) {
      toast.error(`Maximum ${MAX_FILES} files per batch`)
      return
    }
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      const newFiles = accepted.filter(f => !names.has(f.name))
      return [...prev, ...newFiles]
    })
  }, [files])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  })

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select files first')
      return
    }
    setUploading(true)
    setProgress(0)

    try {
      // Create batch
      const batch = await createBatch({
        name: batchName || undefined,
        cutoff_formula: cutoffFormula,
        math_mode: mathMode,
        eligibility_threshold: threshold,
      })

      // Upload in chunks of 50 files for better progress tracking
      const chunkSize = 50
      const chunks: File[][] = []
      for (let i = 0; i < files.length; i += chunkSize) {
        chunks.push(files.slice(i, i + chunkSize))
      }

      let allResults: UploadFileResult[] = []
      for (let i = 0; i < chunks.length; i++) {
        const response = await uploadFiles(batch.id, chunks[i])
        allResults = [...allResults, ...response.results]
        setProgress(Math.round(((i + 1) / chunks.length) * 100))
      }

      setResults(allResults)
      const queued = allResults.filter(r => r.status === 'queued').length
      const errors = allResults.filter(r => r.status === 'error').length
      const dupes = allResults.filter(r => r.status === 'duplicate').length

      toast.success(`Queued ${queued} files for processing!`)
      if (errors > 0) toast.error(`${errors} files had errors`)
      if (dupes > 0) toast(`${dupes} duplicates skipped`, { icon: 'ℹ️' })

      setTimeout(() => navigate(`/batches/${batch.id}`), 1500)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const totalSize = files.reduce((s, f) => s + f.size, 0)
  const fmtSize = (b: number) => b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`

  return (
    <>
      <div className="page-header">
        <h2>Upload New Batch</h2>
        <p>Upload 1–1000 marksheets for automated OCR processing and eligibility screening</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px', alignItems: 'start' }}>

        {/* Drop zone */}
        <div className="card">
          <div className="card-title"><Upload size={16} /> Select Files</div>

          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
            <input {...getInputProps()} />
            <div className="dropzone-icon">📄</div>
            <h3>{isDragActive ? 'Drop files here...' : 'Drag & Drop Marksheets'}</h3>
            <p>or click to browse files</p>
            <p className="text-muted text-sm mt-2">PDF, JPG, JPEG, PNG — up to 50 MB each — max {MAX_FILES} files</p>
          </div>

          {files.length > 0 && (
            <div style={{ marginTop: '20px' }}>
              <div className="flex items-center gap-2" style={{ marginBottom: '12px' }}>
                <span style={{ fontWeight: 600, fontSize: '14px' }}>{files.length} file{files.length !== 1 ? 's' : ''} selected</span>
                <span className="text-muted text-sm">({fmtSize(totalSize)} total)</span>
                <button className="btn btn-danger btn-sm ml-auto" onClick={() => setFiles([])}>Clear All</button>
              </div>
              <div style={{ maxHeight: '280px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {files.slice(0, 100).map((file, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '8px 12px', background: 'var(--bg-surface)',
                    borderRadius: '8px', fontSize: '13px',
                  }}>
                    <FileText size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                    <span className="truncate" style={{ flex: 1 }}>{file.name}</span>
                    <span className="text-muted text-sm">{fmtSize(file.size)}</span>
                    <button onClick={() => removeFile(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '2px' }}>
                      <X size={14} />
                    </button>
                  </div>
                ))}
                {files.length > 100 && (
                  <p className="text-muted text-sm text-center" style={{ padding: '8px' }}>
                    +{files.length - 100} more files not shown
                  </p>
                )}
              </div>
            </div>
          )}

          {uploading && (
            <div style={{ marginTop: '16px' }}>
              <div className="flex items-center gap-2" style={{ marginBottom: '8px' }}>
                <div className="spinner" />
                <span style={{ fontSize: '13.5px' }}>Uploading and queuing... {progress}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          {results && (
            <div style={{ marginTop: '16px' }}>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {[
                  { label: 'Queued', count: results.filter(r => r.status === 'queued').length, icon: <Clock size={14} />, color: 'var(--accent)' },
                  { label: 'Duplicates', count: results.filter(r => r.status === 'duplicate').length, icon: <CheckCircle size={14} />, color: 'var(--review)' },
                  { label: 'Errors', count: results.filter(r => r.status === 'error').length, icon: <AlertCircle size={14} />, color: 'var(--not-eligible)' },
                ].map(item => (
                  <div key={item.label} style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '8px 14px', background: 'var(--bg-surface)',
                    borderRadius: '8px', color: item.color, fontWeight: 600, fontSize: '13px',
                  }}>
                    {item.icon} {item.count} {item.label}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Settings panel */}
        <div className="card" style={{ position: 'sticky', top: '20px' }}>
          <div className="card-title">⚙️ Batch Settings</div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                Batch Name (optional)
              </label>
              <input
                className="input"
                placeholder="e.g. Class XII 2025 Batch"
                value={batchName}
                onChange={e => setBatchName(e.target.value)}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                PCM Cutoff Formula
              </label>
              <select className="input" value={cutoffFormula} onChange={e => setCutoffFormula(e.target.value)}>
                <option value="pcm_average">PCM Average ((P+C+M)/3)</option>
                <option value="engineering_200">Engineering 200 (M + P/2 + C/2)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                Mathematics Mode
              </label>
              <select className="input" value={mathMode} onChange={e => setMathMode(e.target.value)}>
                <option value="combined">Combined A+B Weighted %</option>
                <option value="simple_average">Simple Average (A+B)/2</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                Eligibility Threshold (strict &gt;)
              </label>
              <input
                className="input"
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={threshold}
                onChange={e => setThreshold(Number(e.target.value))}
              />
              <p className="text-muted text-sm mt-2">Candidate must score strictly above {threshold}% in all PCM subjects and overall</p>
            </div>

            <button
              className="btn btn-primary w-full"
              onClick={handleUpload}
              disabled={uploading || files.length === 0}
              style={{ marginTop: '8px', justifyContent: 'center' }}
            >
              {uploading ? <><div className="spinner" /> Processing...</> : <><Upload size={15} /> Upload & Process {files.length > 0 ? `(${files.length})` : ''}</>}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
