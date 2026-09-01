import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, downloadFile } from '../api/client.js'
import { useToast } from '../context/ToastContext.jsx'

export default function Jobs() {
  const toast = useToast()
  const navigate = useNavigate()
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)

  const loadJobs = useCallback(async () => {
    try {
      const res = await apiFetch('/api/jobs')
      const data = await res.json()
      setJobs(data)
      return data
    } catch { toast('Failed to load jobs', 'error') }
    finally { setLoading(false) }
  }, [toast])

  const timerRef = useRef(null)

  useEffect(() => {
    let mounted = true

    const isActive = j => ['running', 'pending', 'queued'].includes(j.status)
    async function tick() {
      const data = await loadJobs()
      if (!mounted) return
      const hasActive = Array.isArray(data) && data.some(isActive)
      if (hasActive && !timerRef.current) {
        timerRef.current = setInterval(async () => {
          const updated = await loadJobs()
          const stillActive = Array.isArray(updated) && updated.some(isActive)
          if (!stillActive) { clearInterval(timerRef.current); timerRef.current = null }
        }, 8000)
      }
    }
    tick()
    return () => {
      mounted = false
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
    }
  }, [loadJobs])

  async function stopJob(jobId, e) {
    e.stopPropagation()
    if (!confirm(`Stop job ${jobId}?`)) return
    try {
      await apiFetch(`/api/scrape/cancel/${jobId}`, { method: 'POST' })
      toast(`Job ${jobId} stopped`, 'info')
      loadJobs()
    } catch { toast('Failed to stop job', 'error') }
  }

  async function deleteJob(jobId, e) {
    e.stopPropagation()
    if (!confirm(`Delete job ${jobId} and all its results?`)) return
    try {
      await apiFetch(`/api/scrape/delete/${jobId}`, { method: 'DELETE' })
      toast(`Job ${jobId} deleted`, 'success')
      loadJobs()
    } catch { toast('Failed to delete job', 'error') }
  }

  function viewResults(jobId) {
    navigate(`/results?job=${jobId}`)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>My Jobs</h1>
          <p className="page-subtitle">Track and manage all your scraping jobs</p>
        </div>
        <button className="btn-secondary" onClick={loadJobs}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
            <path d="M21 3v5h-5"/>
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
            <path d="M8 16H3v5"/>
          </svg>
          Refresh
        </button>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Status</th>
              <th>State</th>
              <th>Cities</th>
              <th>Results</th>
              <th>Emails</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="empty-row">Loading...</td></tr>
            ) : !jobs.length ? (
              <tr><td colSpan={8} className="empty-row">No jobs yet — start a scrape to see results here</td></tr>
            ) : jobs.map(j => {
              const pct = j.total_tasks > 0
                ? Math.round(j.done_tasks * 100 / j.total_tasks)
                : (j.status === 'done' ? 100 : 0)
              return (
                <tr key={j.job_id}>
                  <td><code>{j.job_id}</code></td>
                  <td>
                    <span className={`status-badge status-${j.status}`}>{j.status}</span>
                    {j.status === 'running' && (
                      <div style={{marginTop:5}}>
                        <div style={{height:3,background:'var(--border)',borderRadius:99,overflow:'hidden'}}>
                          <div style={{height:'100%',width:`${pct}%`,background:'linear-gradient(90deg,var(--accent),var(--accent2))',borderRadius:99,transition:'width .5s'}}/>
                        </div>
                        <div style={{fontSize:10,color:'var(--muted)',marginTop:2}}>{j.done_tasks||0}/{j.total_tasks||0} · {pct}%</div>
                        <div style={{height:3,background:'var(--border)',borderRadius:99,overflow:'hidden',marginTop:5}}>
                          <div style={{height:'100%',width:`${j.email_progress||0}%`,background:'#34d399',borderRadius:99,transition:'width .5s'}}/>
                        </div>
                        <div style={{fontSize:10,color:'var(--muted)',marginTop:2}}>
                          Emails{j.emails_submitted ? ` ${j.emails_done||0}/${j.emails_submitted}` : ''} · {j.email_progress||0}%
                        </div>
                      </div>
                    )}
                    {j.status === 'done' && (
                      <div style={{fontSize:10,color:'var(--green)',marginTop:2}}>✓ {j.total_tasks||0} queries done</div>
                    )}
                  </td>
                  <td>{j.state || '—'}</td>
                  <td>{(j.cities_count || 0).toLocaleString()}</td>
                  <td>{(j.results_count || 0).toLocaleString()}</td>
                  <td>{(j.email_count || 0).toLocaleString()}</td>
                  <td style={{color:'var(--muted)',fontSize:12,whiteSpace:'nowrap'}}>
                    {j.created_at ? j.created_at.slice(0,19).replace('T',' ') : '—'}
                  </td>
                  <td>
                    <div className="gap-8">
                      <button className="btn-ghost" onClick={() => viewResults(j.job_id)}>View</button>
                      {j.results_count > 0 && <>
                        <button className="btn-ghost" onClick={() => downloadFile(`/api/download/${j.job_id}/csv`,  `leads_${j.job_id}.csv`).catch(() => toast('Download failed','error'))}>CSV</button>
                        <button className="btn-ghost" onClick={() => downloadFile(`/api/download/${j.job_id}/xlsx`, `leads_${j.job_id}.xlsx`).catch(() => toast('Download failed','error'))}>Excel</button>
                        <button className="btn-ghost" onClick={() => downloadFile(`/api/download/${j.job_id}/json`, `leads_${j.job_id}.json`).catch(() => toast('Download failed','error'))}>JSON</button>
                      </>}
                      {['running','pending','queued'].includes(j.status) && (
                        <button className="btn-ghost" style={{color:'var(--yellow)',borderColor:'var(--yellow)'}} onClick={e => stopJob(j.job_id, e)}>
                          ⏹ Stop
                        </button>
                      )}
                      <button className="btn-ghost danger" onClick={e => deleteJob(j.job_id, e)}>
                        🗑 Delete
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
