import { useState, useEffect, useCallback } from 'react'
import { apiFetch, downloadFile } from '../api/client.js'
import { useToast } from '../context/ToastContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'

// ── Results drawer for a specific job ─────────────────────
function JobResultsDrawer({ jobId, onClose }) {
  const toast = useToast()
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiFetch(`/api/scrape/results/${jobId}`)
      .then(r => r.json())
      .then(d => setResults(d.results || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [jobId])

  const filtered = results.filter(r => {
    if (!search) return true
    const q = search.toLowerCase()
    return (r.name||'').toLowerCase().includes(q) || (r.email||'').toLowerCase().includes(q) || (r.city||'').toLowerCase().includes(q)
  })

  return (
    <div style={{
      position:'fixed',inset:0,background:'rgba(0,0,0,0.7)',zIndex:1000,
      display:'flex',alignItems:'center',justifyContent:'center',padding:20
    }}>
      <div style={{
        background:'var(--surface)',border:'1px solid var(--border)',
        borderRadius:'var(--radius)',width:'min(900px,95vw)',maxHeight:'85vh',
        display:'flex',flexDirection:'column',overflow:'hidden'
      }}>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'16px 20px',borderBottom:'1px solid var(--border)'}}>
          <div>
            <h2 style={{fontSize:15,fontWeight:600}}>Results — Job <code>{jobId}</code></h2>
            <p style={{fontSize:12,color:'var(--muted)',marginTop:2}}>{results.length} total · {results.filter(r=>r.email).length} with email</p>
          </div>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            {results.length > 0 && (
              <>
                <button className="btn-ghost" onClick={() => downloadFile(`/api/download/${jobId}/csv`,  `leads_${jobId}.csv`).catch(() => toast('Download failed', 'error'))}>CSV</button>
                <button className="btn-ghost" onClick={() => downloadFile(`/api/download/${jobId}/xlsx`, `leads_${jobId}.xlsx`).catch(() => toast('Download failed', 'error'))}>Excel</button>
              </>
            )}
            <button className="btn-ghost" onClick={onClose}>✕ Close</button>
          </div>
        </div>

        <div style={{padding:'12px 20px',borderBottom:'1px solid var(--border)'}}>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, email, city..." style={{maxWidth:320}} />
        </div>

        <div style={{overflow:'auto',flex:1}}>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th><th>Name</th><th>City</th><th>Phone</th><th>Email</th><th>Website</th><th>Rating</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="empty-row">Loading...</td></tr>
              ) : !filtered.length ? (
                <tr><td colSpan={7} className="empty-row">No results</td></tr>
              ) : filtered.map((r, i) => (
                <tr key={r.id || i}>
                  <td style={{color:'var(--muted)',fontSize:12}}>{i+1}</td>
                  <td style={{fontWeight:500,maxWidth:180,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.name||'—'}</td>
                  <td>{r.city||'—'}</td>
                  <td style={{color:'var(--muted2)',fontSize:12}}>{r.phone||'—'}</td>
                  <td>
                    {r.email
                      ? r.email.split(',').map(e=>e.trim()).filter(Boolean).map(em=>(
                        <div key={em}><a href={`mailto:${em}`} className="email-link">{em}</a></div>
                      ))
                      : <span style={{color:'var(--muted)'}}>—</span>
                    }
                  </td>
                  <td>
                    {r.website
                      ? <a href={r.website.startsWith('http')?r.website:'https://'+r.website} target="_blank" rel="noopener" className="email-link" style={{maxWidth:120,display:'inline-block',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.website}</a>
                      : <span style={{color:'var(--muted)'}}>—</span>
                    }
                  </td>
                  <td style={{color:'var(--yellow)'}}>{r.rating ? `★ ${r.rating}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── User row with expandable jobs ─────────────────────────
function UserRow({ user, currentAdminId, onRefresh }) {
  const toast = useToast()
  const [expanded, setExpanded] = useState(false)
  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(false)
  const [viewJobId, setViewJobId] = useState(null)

  async function loadJobs() {
    setJobsLoading(true)
    try {
      const res = await apiFetch(`/api/admin/users/${user.id}/jobs`)
      setJobs(await res.json())
    } catch { toast('Failed to load jobs', 'error') }
    finally { setJobsLoading(false) }
  }

  function toggle() {
    if (!expanded) loadJobs()
    setExpanded(v => !v)
  }

  async function changeRole(newRole) {
    if (!confirm(`Change ${user.email} role to ${newRole}?`)) return
    try {
      await apiFetch(`/api/admin/users/${user.id}/role`, {
        method: 'PUT',
        body: JSON.stringify({ role: newRole }),
      })
      toast('Role updated', 'success')
      onRefresh()
    } catch { toast('Failed to change role', 'error') }
  }

  async function deleteUser() {
    if (!confirm(`Delete user ${user.email} and ALL their data? This cannot be undone.`)) return
    try {
      await apiFetch(`/api/admin/users/${user.id}`, { method: 'DELETE' })
      toast(`User ${user.email} deleted`, 'success')
      onRefresh()
    } catch { toast('Failed to delete user', 'error') }
  }

  const isSelf = user.id === currentAdminId

  return (
    <>
      <tr className="admin-user-row" onClick={toggle} style={{cursor:'pointer'}}>
        <td>
          <span className={`expand-icon${expanded ? ' open' : ''}`} style={{marginRight:8,display:'inline-block',color:'var(--muted)'}}>▶</span>
          {user.id}
        </td>
        <td style={{fontWeight:500}}>{user.email}</td>
        <td>
          <span className={`role-badge role-${user.role}`}>{user.role}</span>
        </td>
        <td>{user.job_count || 0}</td>
        <td>{(user.result_count || 0).toLocaleString()}</td>
        <td>{(user.email_count || 0).toLocaleString()}</td>
        <td style={{color:'var(--muted)',fontSize:12}}>{user.created_at ? user.created_at.slice(0,10) : '—'}</td>
        <td onClick={e => e.stopPropagation()}>
          <div className="gap-8">
            {!isSelf && user.role === 'user' && (
              <button className="btn-ghost" style={{fontSize:11}} onClick={() => changeRole('admin')}>Make Admin</button>
            )}
            {!isSelf && user.role === 'admin' && (
              <button className="btn-ghost" style={{fontSize:11}} onClick={() => changeRole('user')}>Remove Admin</button>
            )}
            {!isSelf && (
              <button className="btn-ghost danger" style={{fontSize:11}} onClick={deleteUser}>Delete</button>
            )}
            {isSelf && <span style={{fontSize:11,color:'var(--muted)'}}>You</span>}
          </div>
        </td>
      </tr>

      {/* Expanded: user's jobs */}
      {expanded && (
        <tr className="sub-row">
          <td colSpan={8} style={{padding:0}}>
            <div style={{padding:'12px 20px 12px 40px',background:'var(--surface2)'}}>
              {jobsLoading ? (
                <p style={{color:'var(--muted)',fontSize:13}}>Loading jobs...</p>
              ) : !jobs.length ? (
                <p style={{color:'var(--muted)',fontSize:13}}>No jobs yet</p>
              ) : (
                <table className="data-table" style={{fontSize:12}}>
                  <thead>
                    <tr>
                      <th>Job ID</th><th>Status</th><th>State</th><th>Cities</th><th>Results</th><th>Emails</th><th>Created</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map(j => (
                      <tr key={j.job_id}>
                        <td><code>{j.job_id}</code></td>
                        <td><span className={`status-badge status-${j.status}`}>{j.status}</span></td>
                        <td>{j.state||'—'}</td>
                        <td>{j.cities_count||0}</td>
                        <td>{(j.results_count||0).toLocaleString()}</td>
                        <td>{(j.email_count||0).toLocaleString()}</td>
                        <td style={{color:'var(--muted)'}}>{j.created_at ? j.created_at.slice(0,10) : '—'}</td>
                        <td>
                          <div className="gap-8">
                            <button className="btn-ghost" style={{fontSize:11}} onClick={() => setViewJobId(j.job_id)}>View Results</button>
                            {j.results_count > 0 && <>
                              <button className="btn-ghost" style={{fontSize:11}} onClick={() => downloadFile(`/api/download/${j.job_id}/csv`,  `leads_${j.job_id}.csv`).catch(() => toast('Download failed', 'error'))}>CSV</button>
                              <button className="btn-ghost" style={{fontSize:11}} onClick={() => downloadFile(`/api/download/${j.job_id}/xlsx`, `leads_${j.job_id}.xlsx`).catch(() => toast('Download failed', 'error'))}>Excel</button>
                            </>}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </td>
        </tr>
      )}

      {viewJobId && <JobResultsDrawer jobId={viewJobId} onClose={() => setViewJobId(null)} />}
    </>
  )
}

// ── Admin Main Page ────────────────────────────────────────
export default function Admin() {
  const toast = useToast()
  const { user: currentUser } = useAuth()
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('users')  // 'users' | 'jobs'
  const [allJobs, setAllJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(false)
  const [viewJobId, setViewJobId] = useState(null)
  const [jobSearch, setJobSearch] = useState('')

  const loadData = useCallback(async () => {
    try {
      const [statsRes, usersRes] = await Promise.all([
        apiFetch('/api/admin/stats'),
        apiFetch('/api/admin/users'),
      ])
      setStats(await statsRes.json())
      setUsers(await usersRes.json())
    } catch { toast('Failed to load admin data', 'error') }
    finally { setLoading(false) }
  }, [toast])

  useEffect(() => { loadData() }, [loadData])

  const loadAllJobs = useCallback(async () => {
    setJobsLoading(true)
    try {
      const res = await apiFetch('/api/admin/jobs')
      setAllJobs(await res.json())
    } catch { toast('Failed to load all jobs', 'error') }
    finally { setJobsLoading(false) }
  }, [toast])

  useEffect(() => {
    if (tab === 'jobs') loadAllJobs()
  }, [tab, loadAllJobs])

  const filteredJobs = allJobs.filter(j => {
    if (!jobSearch) return true
    const q = jobSearch.toLowerCase()
    return (j.job_id||'').toLowerCase().includes(q) ||
      (j.user_email||'').toLowerCase().includes(q) ||
      (j.state||'').toLowerCase().includes(q)
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Admin Panel</h1>
          <p className="page-subtitle">Manage users, view all jobs and results</p>
        </div>
        <button className="btn-secondary" onClick={() => { loadData(); if (tab === 'jobs') loadAllJobs() }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
            <path d="M21 3v5h-5"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="stats-grid">
          {[
            { label: 'Total Users',   val: stats.total_users,   color: 'var(--accent2)' },
            { label: 'Total Jobs',    val: stats.total_jobs,    color: 'var(--blue)' },
            { label: 'Total Results', val: stats.total_results.toLocaleString(), color: 'var(--green)' },
            { label: 'Emails Found',  val: stats.total_emails.toLocaleString(),  color: 'var(--yellow)' },
            { label: 'Active Jobs',   val: stats.active_jobs,   color: 'var(--red)' },
          ].map(s => (
            <div key={s.label} className="stat-card">
              <div className="stat-card-val" style={{color: s.color}}>{s.val}</div>
              <div className="stat-card-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tab switcher */}
      <div style={{display:'flex',gap:8,marginBottom:16}}>
        <button className={`btn-ghost${tab==='users'?' active':''}`} onClick={() => setTab('users')}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          Users ({users.length})
        </button>
        <button className={`btn-ghost${tab==='jobs'?' active':''}`} onClick={() => setTab('jobs')}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
          </svg>
          All Jobs
        </button>
      </div>

      {/* Users tab */}
      {tab === 'users' && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th><th>Email</th><th>Role</th><th>Jobs</th><th>Results</th><th>Emails</th><th>Joined</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} className="empty-row">Loading users...</td></tr>
              ) : !users.length ? (
                <tr><td colSpan={8} className="empty-row">No users found</td></tr>
              ) : users.map(u => (
                <UserRow
                  key={u.id}
                  user={u}
                  currentAdminId={currentUser?.id}
                  onRefresh={loadData}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* All Jobs tab */}
      {tab === 'jobs' && (
        <>
          <div style={{marginBottom:12}}>
            <input
              type="text" value={jobSearch} onChange={e => setJobSearch(e.target.value)}
              placeholder="Search by job ID, user email, state..."
              style={{maxWidth:380}}
            />
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th><th>User</th><th>Status</th><th>State</th><th>Cities</th><th>Results</th><th>Emails</th><th>Created</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobsLoading ? (
                  <tr><td colSpan={9} className="empty-row">Loading jobs...</td></tr>
                ) : !filteredJobs.length ? (
                  <tr><td colSpan={9} className="empty-row">No jobs found</td></tr>
                ) : filteredJobs.map(j => (
                  <tr key={j.job_id}>
                    <td><code>{j.job_id}</code></td>
                    <td style={{fontSize:12,color:'var(--muted2)'}}>{j.user_email || '—'}</td>
                    <td><span className={`status-badge status-${j.status}`}>{j.status}</span></td>
                    <td>{j.state||'—'}</td>
                    <td>{j.cities_count||0}</td>
                    <td>{(j.results_count||0).toLocaleString()}</td>
                    <td>{(j.email_count||0).toLocaleString()}</td>
                    <td style={{color:'var(--muted)',fontSize:12,whiteSpace:'nowrap'}}>
                      {j.created_at ? j.created_at.slice(0,16).replace('T',' ') : '—'}
                    </td>
                    <td>
                      <div className="gap-8">
                        <button className="btn-ghost" style={{fontSize:11}} onClick={() => setViewJobId(j.job_id)}>View</button>
                        {j.results_count > 0 && <>
                          <button className="btn-ghost" style={{fontSize:11}} onClick={() => downloadFile(`/api/download/${j.job_id}/csv`,  `leads_${j.job_id}.csv`).catch(() => toast('Download failed', 'error'))}>CSV</button>
                          <button className="btn-ghost" style={{fontSize:11}} onClick={() => downloadFile(`/api/download/${j.job_id}/xlsx`, `leads_${j.job_id}.xlsx`).catch(() => toast('Download failed', 'error'))}>Excel</button>
                        </>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {viewJobId && <JobResultsDrawer jobId={viewJobId} onClose={() => setViewJobId(null)} />}
    </div>
  )
}
