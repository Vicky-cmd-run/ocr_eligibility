import { Routes, Route, NavLink } from 'react-router-dom'
import { LayoutDashboard, Upload, ClipboardList, Eye } from 'lucide-react'
import DashboardPage from './pages/DashboardPage'
import NewBatchPage from './pages/NewBatchPage'
import BatchDetailPage from './pages/BatchDetailPage'
import ReviewPage from './pages/ReviewPage'

export default function App() {
  return (
    <div className="layout">
      <div className="glow-accent" />

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>📄 OCR System</h1>
          <p>Marksheet Screening</p>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
            <LayoutDashboard size={16} /> Dashboard
          </NavLink>
          <NavLink to="/batches/new" className={({ isActive }) => isActive ? 'active' : ''}>
            <Upload size={16} /> Upload Batch
          </NavLink>
          <NavLink to="/batches" className={({ isActive }) => isActive ? 'active' : ''}>
            <ClipboardList size={16} /> All Batches
          </NavLink>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/batches/new" element={<NewBatchPage />} />
          <Route path="/batches" element={<DashboardPage />} />
          <Route path="/batches/:batchId" element={<BatchDetailPage />} />
          <Route path="/documents/:documentId/review" element={<ReviewPage />} />
        </Routes>
      </main>
    </div>
  )
}
