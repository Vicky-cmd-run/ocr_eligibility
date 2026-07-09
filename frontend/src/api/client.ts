import axios from 'axios'
import type {
  Batch, BatchProgress, BatchResultsResponse, BatchUploadResponse,
  ReviewData,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 60_000,
})

// ─── Batches ──────────────────────────────────────────────────────────────────

export const createBatch = (payload: {
  name?: string
  cutoff_formula?: string
  math_mode?: string
  eligibility_threshold?: number
  notes?: string
}): Promise<Batch> =>
  api.post('/batches', payload).then(r => r.data)

export const listBatches = (skip = 0, limit = 20): Promise<Batch[]> =>
  api.get('/batches', { params: { skip, limit } }).then(r => r.data)

export const getBatch = (id: string): Promise<Batch> =>
  api.get(`/batches/${id}`).then(r => r.data)

export const getBatchProgress = (id: string): Promise<BatchProgress> =>
  api.get(`/batches/${id}/progress`).then(r => r.data)

export const getBatchResults = (
  batchId: string,
  params: { status?: string; skip?: number; limit?: number }
): Promise<BatchResultsResponse> =>
  api.get(`/batches/${batchId}/results`, { params }).then(r => r.data)

export const uploadFiles = (batchId: string, files: File[]): Promise<BatchUploadResponse> => {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  return api.post(`/batches/${batchId}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300_000,
  }).then(r => r.data)
}

export const exportCsv = (batchId: string, status?: string, approvalMode?: string): string => {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  if (approvalMode) params.append('approval_mode', approvalMode)
  const qs = params.toString()
  return `/api/batches/${batchId}/export/csv${qs ? `?${qs}` : ''}`
}

export const exportXlsx = (batchId: string, status?: string, approvalMode?: string): string => {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  if (approvalMode) params.append('approval_mode', approvalMode)
  const qs = params.toString()
  return `/api/batches/${batchId}/export/xlsx${qs ? `?${qs}` : ''}`
}

// ─── Documents ────────────────────────────────────────────────────────────────

export const getDocumentReview = (documentId: string): Promise<ReviewData> =>
  api.get(`/documents/${documentId}/review`).then(r => r.data)

export const submitReview = (
  documentId: string,
  payload: {
    reviewer?: string
    subject_corrections?: { subject_mark_id: string; obtained_marks: number | null; maximum_marks: number | null }[]
    override_status?: string
    review_notes?: string
  }
) => api.put(`/documents/${documentId}/review`, payload).then(r => r.data)

export const reprocessDocument = (documentId: string) =>
  api.post(`/documents/${documentId}/reprocess`).then(r => r.data)

export const getOcrTokens = (documentId: string): Promise<any[]> =>
  api.get(`/documents/${documentId}/ocr`).then(r => r.data)
