import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiFetch, downloadFile } from '../api/client.js'
import { useToast } from '../context/ToastContext.jsx'

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    const done = () => { setCopied(true); setTimeout(() => setCopied(false), 1500) }
    // navigator.clipboard needs HTTPS/localhost; fall back to execCommand on plain HTTP.
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done))
    } else {
      fallbackCopy(text, done)
    }
  }
  function fallbackCopy(value, done) {
    try {
      const ta = document.createElement('textarea')
      ta.value = value
      ta.style.position = 'fixed'; ta.style.opacity = '0'
      document.body.appendChild(ta); ta.focus(); ta.select()
      document.execCommand('copy')
      ta.remove(); done()
    } catch { /* ignore */ }
  }
  return (
    <button className="copy-btn" title="Copy" onClick={copy}>
      {copied
        ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
        : <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      }
    </button>
  )
}

export default function Results() {
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const autoJobId = searchParams.get('job')

  const [jobs, setJobs] = useState([])
  const [selectedJobId, setSelectedJobId] = useState(autoJobId || '')
  const [allResults, setAllResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('all') // 'all', 'email', 'dm', 'tier1', 'phone'
  const [roleFilter, setRoleFilter] = useState('all') // 'all', 'c-level', 'marketing', 'operations'
  const autoRefreshRef = useRef(null)

  useEffect(() => {
    apiFetch('/api/jobs').then(r => r.json()).then(data => {
      setJobs(data)
      if (autoJobId) setSelectedJobId(autoJobId)
    }).catch(() => {})
  }, [autoJobId])

  const allResultsRef = useRef(allResults)
  allResultsRef.current = allResults

  const loadResults = useCallback(async (jobId, silent = false) => {
    if (!jobId) return
    if (!silent) setLoading(true)
    try {
      const res = await apiFetch(`/api/scrape/results/${jobId}`)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      if (!silent) {
        setAllResults(data.results || [])
        setFilterType('all')
        setRoleFilter('all')
        setSearch('')
      } else {
        if ((data.results || []).length !== allResultsRef.current.length) {
          setAllResults(data.results || [])
        }
      }
    } catch (e) {
      if (!silent) toast('Failed to load results', 'error')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    if (selectedJobId) loadResults(selectedJobId)
  }, [selectedJobId, loadResults])

  // Auto-refresh for running jobs
  useEffect(() => {
    if (autoRefreshRef.current) clearInterval(autoRefreshRef.current)
    if (!selectedJobId) return
    autoRefreshRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/scrape/status/${selectedJobId}`)
        const j = await res.json()
        if (['running', 'pending', 'queued'].includes(j.status)) {
          loadResults(selectedJobId, true)
        } else {
          clearInterval(autoRefreshRef.current)
        }
      } catch {}
    }, 5000)
    return () => clearInterval(autoRefreshRef.current)
  }, [selectedJobId, loadResults])

  const [page, setPage] = useState(1)
  const pageSize = 50

  const filtered = allResults.filter(r => {
    // Quality Filter
    if (filterType === 'email' && !r.email) return false
    if (filterType === 'dm' && !r.decision_makers) return false
    if (filterType === 'phone' && !r.phone) return false
    if (filterType === 'tier1' && (!r.email || !r.decision_makers || !r.phone)) return false

    // Role Filter
    if (roleFilter !== 'all') {
      const dms = (r.decision_makers || '').toLowerCase()
      if (roleFilter === 'c-level' && !/(ceo|founder|owner|president|managing director|principal|coo|cto)/i.test(dms)) return false
      if (roleFilter === 'marketing' && !/(marketing|sales|cmo|growth|business development)/i.test(dms)) return false
      if (roleFilter === 'operations' && !/(general manager|operations|plant|warehouse|facility|logistics)/i.test(dms)) return false
    }

    if (!search) return true
    const q = search.toLowerCase()
    return (
      (r.name            || '').toLowerCase().includes(q) ||
      (r.decision_makers || '').toLowerCase().includes(q) ||
      (r.email           || '').toLowerCase().includes(q) ||
      (r.city            || '').toLowerCase().includes(q) ||
      (r.phone           || '').toLowerCase().includes(q) ||
      (r.address         || '').toLowerCase().includes(q) ||
      (r.category        || '').toLowerCase().includes(q)
    )
  })

  const totalPages = Math.ceil(filtered.length / pageSize) || 1
  const startIndex = (page - 1) * pageSize
  const paginated = filtered.slice(startIndex, startIndex + pageSize)
  const withEmail = filtered.filter(r => r.email).length
  const withDm = filtered.filter(r => r.decision_makers).length

  function handleSearchChange(e) {
    setSearch(e.target.value)
    setPage(1)
  }

  function handleJobChange(e) {
    setSelectedJobId(e.target.value)
    setPage(1)
  }

  function copyAllEmails() {
    const emails = Array.from(new Set(
      filtered.flatMap(r => (r.email || '').split(',').map(e => e.trim()).filter(Boolean))
    ))
    if (!emails.length) return toast('No emails in current view', 'info')
    const text = emails.join(', ')
    navigator.clipboard?.writeText(text)
    toast(`Copied ${emails.length.toLocaleString()} unique emails!`, 'success')
  }

  function copyAllPhones() {
    const phones = Array.from(new Set(
      filtered.map(r => (r.phone || '').trim()).filter(Boolean)
    ))
    if (!phones.length) return toast('No phone numbers in current view', 'info')
    navigator.clipboard?.writeText(phones.join(', '))
    toast(`Copied ${phones.length.toLocaleString()} phone numbers!`, 'success')
  }

  function copyAllDms() {
    const dms = Array.from(new Set(
      filtered.flatMap(r => (r.decision_makers || '').split(';').map(d => d.trim()).filter(Boolean))
    ))
    if (!dms.length) return toast('No decision makers in current view', 'info')
    navigator.clipboard?.writeText(dms.join('\n'))
    toast(`Copied ${dms.length.toLocaleString()} decision makers!`, 'success')
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Results & Leads Explorer</h1>
          <p className="page-subtitle">Verified decision makers, emails, phone numbers & multi-format export</p>
        </div>
        <div className="results-controls">
          <div className="search-input-wrap">
            <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input type="text" value={search} onChange={handleSearchChange} placeholder="Search name, decision makers, email, city..." />
          </div>
          <select
            value={selectedJobId}
            onChange={handleJobChange}
            style={{width: 220}}
          >
            <option value="">Select job...</option>
            {jobs.map(j => (
              <option key={j.job_id} value={j.job_id}>
                Job {j.job_id} · {j.state || '?'} · {j.status} · {j.results_count} results
              </option>
            ))}
          </select>
          {selectedJobId && allResults.length > 0 && (
            <div className="gap-8">
              <button className="btn-export" onClick={() => downloadFile(`/api/download/${selectedJobId}/csv`,  `leads_${selectedJobId}.csv`).catch(() => toast('Download failed','error'))}>CSV</button>
              <button className="btn-export" onClick={() => downloadFile(`/api/download/${selectedJobId}/xlsx`, `leads_${selectedJobId}.xlsx`).catch(() => toast('Download failed','error'))}>Excel</button>
              <button className="btn-export" onClick={() => downloadFile(`/api/download/${selectedJobId}/json`, `leads_${selectedJobId}.json`).catch(() => toast('Download failed','error'))}>JSON</button>
            </div>
          )}
        </div>
      </div>

      {allResults.length > 0 && (
        <div style={{display:'flex',flexDirection:'column',gap:10,marginBottom:16,background:'var(--surface)',padding:'12px 16px',borderRadius:10,border:'1px solid var(--border)'}}>
          {/* Filter Pills */}
          <div style={{display:'flex',justifyContent:'space-between',flexWrap:'wrap',alignItems:'center',gap:10}}>
            <div style={{display:'flex',flexWrap:'wrap',gap:6,alignItems:'center'}}>
              <span style={{fontSize:11,color:'var(--muted)',fontWeight:600,textTransform:'uppercase'}}>Lead Filters:</span>
              {[
                { key: 'all', label: `All (${allResults.length})` },
                { key: 'tier1', label: `🔥 Tier-1 Hot Leads` },
                { key: 'dm', label: `👔 Has Decision Maker (${withDm})` },
                { key: 'email', label: `✉️ Has Email (${withEmail})` },
                { key: 'phone', label: `📞 Has Phone` },
              ].map(f => (
                <button
                  key={f.key}
                  className={`btn-ghost${filterType === f.key ? ' active' : ''}`}
                  style={{fontSize:11,padding:'4px 9px'}}
                  onClick={() => { setFilterType(f.key); setPage(1); }}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Bulk Copy & Outreach Actions */}
            <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
              <button
                className="btn-primary"
                style={{fontSize:11,padding:'4px 10px',background:'linear-gradient(135deg,#0284c7,#6366f1)',color:'#fff'}}
                onClick={() => navigate('/outreach')}
                title="Launch Cold Email Campaign with these leads"
              >
                🚀 Send Cold Outreach
              </button>
              <button className="btn-ghost" style={{fontSize:11,padding:'4px 9px',borderColor:'rgba(56,189,248,0.4)',color:'#38bdf8'}} onClick={copyAllEmails} title="Copy all filtered emails">
                📋 Copy All Emails
              </button>
              <button className="btn-ghost" style={{fontSize:11,padding:'4px 9px'}} onClick={copyAllPhones} title="Copy all filtered phone numbers">
                📋 Copy Phones
              </button>
              <button className="btn-ghost" style={{fontSize:11,padding:'4px 9px'}} onClick={copyAllDms} title="Copy all filtered decision makers">
                📋 Copy Decision Makers
              </button>
            </div>
          </div>

          {/* Role Filter Pills */}
          <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap',paddingTop:6,borderTop:'1px solid rgba(255,255,255,0.06)'}}>
            <span style={{fontSize:11,color:'var(--muted)',fontWeight:600,textTransform:'uppercase'}}>DM Role:</span>
            {[
              { key: 'all', label: 'All Roles' },
              { key: 'c-level', label: '👑 CEO / Founder / Owner / President' },
              { key: 'marketing', label: '📈 Marketing & Sales Director' },
              { key: 'operations', label: '⚙️ General Manager / Operations' },
            ].map(r => (
              <button
                key={r.key}
                className={`btn-ghost${roleFilter === r.key ? ' active' : ''}`}
                style={{fontSize:11,padding:'3px 8px'}}
                onClick={() => { setRoleFilter(r.key); setPage(1); }}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {allResults.length > 0 && (
        <div className="results-meta" style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div>
            <strong>{filtered.length.toLocaleString()}</strong> leads showing &nbsp;·&nbsp;
            <strong>{withEmail.toLocaleString()}</strong> with email &nbsp;·&nbsp;
            <strong>{withDm.toLocaleString()}</strong> with decision makers
          </div>
          {filtered.length > pageSize && (
            <div style={{fontSize:12,color:'var(--muted)'}}>
              Page {page} of {totalPages}
            </div>
          )}
        </div>
      )}

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Company</th>
              <th>Decision Makers</th>
              <th>Category</th>
              <th>Number</th>
              <th>Email</th>
              <th>Website</th>
              <th>Social</th>
              <th>City</th>
              <th>State</th>
              <th>Rating</th>
            </tr>
          </thead>
          <tbody>
            {!selectedJobId ? (
              <tr><td colSpan={11} className="empty-row">Select a job to view results</td></tr>
            ) : loading ? (
              <tr><td colSpan={11} className="empty-row">Loading results...</td></tr>
            ) : !filtered.length ? (
              <tr><td colSpan={11} className="empty-row">No results match your filter</td></tr>
            ) : paginated.map((r, i) => (
              <tr key={r.id || startIndex + i}>
                <td style={{color:'var(--muted)',fontSize:12}}>{startIndex + i + 1}</td>
                <td style={{maxWidth:220}}>
                  <div style={{display:'flex',alignItems:'center',gap:4}}>
                    <span style={{fontWeight:600,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={r.name}>
                      {r.name || '—'}
                    </span>
                    {r.email && r.decision_makers && r.phone ? (
                      <span title="Tier 1 Lead: Decision Maker + Email + Phone" style={{padding:'2px 5px',borderRadius:4,fontSize:10,background:'rgba(239,68,68,0.25)',color:'#f87171',fontWeight:700,flexShrink:0}}>
                        🔥 HOT
                      </span>
                    ) : (r.email || r.decision_makers) ? (
                      <span title="Tier 2 Lead: Email or Decision Maker" style={{padding:'2px 5px',borderRadius:4,fontSize:10,background:'rgba(245,158,11,0.25)',color:'#fbbf24',fontWeight:600,flexShrink:0}}>
                        ⚡ WARM
                      </span>
                    ) : null}
                  </div>
                </td>
                <td style={{maxWidth:240}}>
                  {r.decision_makers ? (
                    r.decision_makers.split(';').map(dm => dm.trim()).filter(Boolean).map(dm => (
                      <div key={dm} className="copy-wrap" style={{marginBottom:4,fontSize:12}}>
                        <span style={{color:'var(--accent-glow, #38bdf8)',fontWeight:500}}>👤 {dm}</span>
                        <CopyBtn text={dm}/>
                      </div>
                    ))
                  ) : <span style={{color:'var(--muted)'}}>—</span>}
                </td>
                <td style={{color:'var(--muted)',maxWidth:130,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={r.category}>{r.category || '—'}</td>
                <td className="phone-text">
                  {r.phone ? (
                    <div className="copy-wrap">{r.phone}<CopyBtn text={r.phone}/></div>
                  ) : <span style={{color:'var(--muted)'}}>—</span>}
                </td>
                <td>
                  {r.email ? (
                    r.email.split(',').map(e => e.trim()).filter(Boolean).map(em => (
                      <div key={em} className="copy-wrap">
                        <a href={`mailto:${em}`} className="email-link">{em}</a>
                        <CopyBtn text={em}/>
                      </div>
                    ))
                  ) : <span style={{color:'var(--muted)'}}>—</span>}
                </td>
                <td>
                  {r.website ? (
                    <a
                      href={r.website.startsWith('http') ? r.website : 'https://' + r.website}
                      target="_blank" rel="noopener noreferrer" className="email-link"
                      style={{maxWidth:140,display:'inline-block',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}
                    >{r.website}</a>
                  ) : <span style={{color:'var(--muted)'}}>—</span>}
                </td>
                <td>
                  {r.social ? (
                    r.social.split(',').map(u => u.trim()).filter(Boolean).map(u => {
                      const label = /linkedin/i.test(u) ? 'LinkedIn'
                        : /facebook|fb\.com/i.test(u) ? 'Facebook'
                        : /instagram/i.test(u) ? 'Instagram'
                        : /twitter|x\.com/i.test(u) ? 'X'
                        : /youtube/i.test(u) ? 'YouTube'
                        : /tiktok/i.test(u) ? 'TikTok'
                        : /t\.me/i.test(u) ? 'Telegram'
                        : /wa\.me/i.test(u) ? 'WhatsApp' : 'Link'
                      return <div key={u}><a href={u} target="_blank" rel="noopener noreferrer" className="email-link">{label}</a></div>
                    })
                  ) : <span style={{color:'var(--muted)'}}>—</span>}
                </td>
                <td>{r.city || '—'}</td>
                <td style={{color:'var(--muted)'}}>{r.state || '—'}</td>
                <td className="rating-text">{r.rating ? `★ ${r.rating}` : <span style={{color:'var(--muted)'}}>—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length > pageSize && (
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:16}}>
          <span style={{fontSize:13,color:'var(--muted)'}}>
            Showing {(startIndex + 1).toLocaleString()}–{Math.min(startIndex + pageSize, filtered.length).toLocaleString()} of {filtered.length.toLocaleString()} leads
          </span>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            <button
              className="btn-ghost"
              disabled={page === 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              ← Previous
            </button>
            <span style={{fontSize:13,color:'var(--muted)',padding:'0 4px'}}>
              Page {page} of {totalPages}
            </span>
            <button
              className="btn-ghost"
              disabled={page >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
