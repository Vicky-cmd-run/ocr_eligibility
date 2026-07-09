import { Routes, Route, Link } from 'react-router-dom'
import MainScreen from './pages/MainScreen'
import ReviewPage from './pages/ReviewPage'

export default function App() {
  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-base)' }}>
      <div className="glow-accent" />

      {/* Header */}
      <header style={{
        background: '#ffffff',
        borderBottom: '1px solid var(--border)',
        padding: '16px 40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 10,
        boxShadow: '0 1px 3px rgba(0,0,0,0.01)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(139, 92, 246, 0.3)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                border: '1px solid rgba(255, 255, 255, 0.25)',
                borderRadius: '12px',
                pointerEvents: 'none'
              }} />
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#ffffff', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }}>
                <path d="M4 4.5L12 20L20 4.5" />
              </svg>
            </div>
            <div>
              <h1 style={{
                fontSize: '17px',
                fontWeight: 800,
                color: 'var(--text-primary)',
                letterSpacing: '-0.3px',
                lineHeight: 1.2
              }}>
                OCR Screening System
              </h1>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600 }}>12th Marksheet Eligibility Checker</span>
            </div>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main style={{ flex: 1, position: 'relative', zIndex: 1, padding: '32px 0' }}>
        <Routes>
          <Route path="/" element={<MainScreen />} />
          <Route path="/documents/:documentId/review" element={<ReviewPage />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer style={{
        background: '#ffffff',
        borderTop: '1px solid var(--border)',
        padding: '24px 40px',
        textAlign: 'center',
        color: 'var(--text-secondary)',
        fontSize: '13px'
      }}>
        <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px', letterSpacing: '-0.1px' }}>
          Viggu - Lazy but Smart
        </div>
        <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
          © {new Date().getFullYear()} VIGGU. All Rights Reserved.
        </div>
      </footer>
    </div>
  )
}
