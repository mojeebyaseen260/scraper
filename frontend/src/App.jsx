import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext.jsx'
import { ToastProvider } from './context/ToastContext.jsx'
import Layout from './components/Layout.jsx'
import Home from './pages/Home.jsx'
import Login from './pages/Login.jsx'
import AdminLogin from './pages/AdminLogin.jsx'
import Register from './pages/Register.jsx'
import Scraper from './pages/Scraper.jsx'
import Jobs from './pages/Jobs.jsx'
import Results from './pages/Results.jsx'
import Outreach from './pages/Outreach.jsx'
import Admin from './pages/Admin.jsx'

function ProtectedRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin') return <Navigate to="/scraper" replace />
  return children
}

function PublicRoute({ children }) {
  const { user } = useAuth()
  return user ? <Navigate to="/scraper" replace /> : children
}

// Admin entrance: already-signed-in admins skip straight to the panel.
function AdminLoginRoute({ children }) {
  const { user } = useAuth()
  if (user && user.role === 'admin') return <Navigate to="/admin" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/"         element={<Home />} />
            <Route path="/login"    element={<PublicRoute><Login /></PublicRoute>} />
            <Route path="/admin-login" element={<AdminLoginRoute><AdminLogin /></AdminLoginRoute>} />
            <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
            <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              <Route path="/scraper"  element={<Scraper />} />
              <Route path="/jobs"     element={<Jobs />} />
              <Route path="/results"  element={<Results />} />
              <Route path="/outreach" element={<Outreach />} />
              <Route path="/admin"    element={<AdminRoute><Admin /></AdminRoute>} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
