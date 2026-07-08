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
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent), #7c3aed)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontSize: '20px',
              fontWeight: 900,
              boxShadow: '0 4px 10px rgba(37, 99, 235, 0.2)'
            }}>
              V
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
          Academic Screening Authority • Department of Eligibility & Cutoff Calculations • All Rights Reserved
        </div>
      </footer>
    </div>
  )
}
