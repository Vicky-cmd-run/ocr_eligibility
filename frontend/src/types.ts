// TypeScript types matching the backend API schemas

export type BatchStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'PARTIALLY_FAILED' | 'FAILED'
export type DocumentStatus = 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'ELIGIBLE' | 'NOT_ELIGIBLE' | 'REVIEW_REQUIRED' | 'FAILED'
export type EligibilityStatus = 'ELIGIBLE' | 'NOT_ELIGIBLE' | 'REVIEW_REQUIRED' | 'PENDING'
export type NormalizedSubject = 'PHYSICS' | 'CHEMISTRY' | 'MATHEMATICS' | 'MATHS_A' | 'MATHS_B' | 'OTHER' | 'UNKNOWN'

export interface Batch {
  id: string
  name: string | null
  status: BatchStatus
  total_documents: number
  queued_count: number
  processing_count: number
  completed_count: number
  failed_count: number
  eligible_count: number
  not_eligible_count: number
  review_required_count: number
  cutoff_formula: string
  math_mode: string
  eligibility_threshold: number
  notes: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface BatchProgress {
  batch_id: string
  status: BatchStatus
  total: number
  queued: number
  processing: number
  completed: number
  failed: number
  eligible: number
  not_eligible: number
  review_required: number
  progress_percent: number
}

export interface SubjectMark {
  id: string
  raw_subject_name: string
  normalized_subject: NormalizedSubject
  mark_type: string
  obtained_marks: number | null
  maximum_marks: number | null
  percentage: number | null
  subject_match_confidence: number | null
  marks_ocr_confidence: number | null
  raw_obtained_text: string | null
  raw_maximum_text: string | null
  is_suspicious: boolean
  is_manually_corrected: boolean
  notes: string | null
}

export interface CandidateSummary {
  name: string | null
  register_number: string | null
}

export interface ExtractionSummary {
  physics_percentage: number | null
  chemistry_percentage: number | null
  mathematics_percentage: number | null
  maths_a_percentage: number | null
  maths_b_percentage: number | null
  pcm_cutoff: number | null
  overall_percentage: number | null
  combined_confidence: number | null
  cutoff_formula_used: string | null
  has_missing_subjects: boolean
  missing_subjects: string[] | null
  validation_warnings: { field: string; message: string; severity: string }[] | null
}

export interface EligibilitySummary {
  status: EligibilityStatus | null
  physics_passed: boolean | null
  chemistry_passed: boolean | null
  mathematics_passed: boolean | null
  overall_passed: boolean | null
  rejection_reasons: string[]
  is_manually_reviewed: boolean
  review_notes: string | null
}

export interface DocumentRow {
  id: string
  original_filename: string
  status: DocumentStatus
  document_type: string
  page_count: number
  overall_ocr_confidence: number | null
  requires_review: boolean
  is_duplicate: boolean
  error_message: string | null
  processed_at: string | null
  created_at: string
  candidate: CandidateSummary | null
  extraction: ExtractionSummary | null
  eligibility: EligibilitySummary | null
}

export interface BatchResultsResponse {
  batch_id: string
  total: number
  skip: number
  limit: number
  documents: DocumentRow[]
}

export interface ReviewData {
  document: {
    id: string
    original_filename: string
    file_path: string
    status: string
    document_type: string
    page_count: number
    overall_ocr_confidence: number | null
    requires_review: boolean
    error_message: string | null
  }
  candidate: {
    name: string | null
    register_number: string | null
    subject_marks: SubjectMark[]
  } | null
  extraction_result: ExtractionSummary | null
  eligibility_result: EligibilitySummary | null
  review_actions: {
    id: string
    action_type: string
    reviewer: string | null
    before_state: Record<string, unknown>
    after_state: Record<string, unknown>
    notes: string | null
    created_at: string
  }[]
}

export interface UploadFileResult {
  filename: string
  document_id: string | null
  status: 'queued' | 'duplicate' | 'error'
  message: string | null
}

export interface BatchUploadResponse {
  batch_id: string
  total_uploaded: number
  queued: number
  duplicates: number
  errors: number
  results: UploadFileResult[]
}
