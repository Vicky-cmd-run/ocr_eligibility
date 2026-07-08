/** Format a number as percentage string, e.g. 75.23 → "75.23%" */
export function fmtPct(val: number | null | undefined): string {
  if (val == null) return '—'
  return `${val.toFixed(2)}%`
}

/** Format a confidence 0–1 float as e.g. "0.92" or "N/A" */
export function fmtConf(val: number | null | undefined): string {
  if (val == null) return 'N/A'
  return `${Math.round(val * 100)}%`
}

/** Human-readable relative time, e.g. "3 minutes ago" */
export function formatDistanceToNow(dateStr: string): string {
  const date = new Date(dateStr)
  const diff = Date.now() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

/** Format bytes to KB/MB */
export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
