// Central API client — attaches JWT token to every request.
// In production the frontend (Vercel) and backend (Railway) are on different
// origins, so set VITE_API_URL to the backend URL. In dev it's empty and Vite
// proxies /api to localhost:8000.
const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export function apiUrl(path) {
  return API_BASE + path
}

export function getToken() {
  return localStorage.getItem('cl_token')
}

export function setToken(token) {
  localStorage.setItem('cl_token', token)
}

export function clearToken() {
  localStorage.removeItem('cl_token')
}

export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }
  const res = await fetch(API_BASE + path, { ...options, headers })
  // Don't auto-redirect on auth endpoints — let the caller handle the error
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    clearToken()
    // Send admins back to the admin entrance, everyone else to the user login.
    const onAdmin = window.location.pathname.startsWith('/admin')
    window.location.href = onAdmin ? '/admin-login' : '/login'
    throw new Error('Session expired')
  }
  return res
}

// Secure file download — uses Authorization header (not query param) to avoid token leaking into URLs/logs
export async function downloadFile(path, filename) {
  const token = getToken()
  const res = await fetch(API_BASE + path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('Download failed')
  // Prefer the server-provided filename (has country/region), sent in
  // Content-Disposition; fall back to the passed name.
  let serverName = ''
  const cd = res.headers.get('Content-Disposition') || ''
  const m = cd.match(/filename\*?=(?:UTF-8'')?["']?([^"';]+)/i)
  if (m) { try { serverName = decodeURIComponent(m[1]) } catch (e) { serverName = m[1] } }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = serverName || filename || path.split('/').pop()
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
