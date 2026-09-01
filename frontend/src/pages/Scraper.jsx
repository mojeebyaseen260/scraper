import { useState, useEffect, useRef, useCallback } from 'react'
import { apiFetch, downloadFile } from '../api/client.js'
import { useToast } from '../context/ToastContext.jsx'

export default function Scraper() {
  const toast = useToast()
  const pollRef = useRef(null)

  const [countries, setCountries] = useState([])
  const [selectedCountry, setSelectedCountry] = useState('')
  const [regions, setRegions] = useState([])
  const [selectedRegion, setSelectedRegion] = useState('')
  const [allCities, setAllCities] = useState([])
  const [selectedCities, setSelectedCities] = useState(new Set())
  const [citySearch, setCitySearch] = useState('')
  const [customCity, setCustomCity] = useState('')

  const [keywords, setKeywords] = useState('')
  const [maxEmails, setMaxEmails] = useState(5)
  const [relevantOnly, setRelevantOnly] = useState(true)
  const [categories, setCategories] = useState('')
  const [presetCategories, setPresetCategories] = useState({})

  const [activeJobId, setActiveJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [liveResults, setLiveResults] = useState([])
  const [selectedIndustry, setSelectedIndustry] = useState('')

  useEffect(() => {
    apiFetch('/api/countries').then(r => r.json()).then(setCountries).catch(() => {})
    apiFetch('/api/keyword-categories').then(r => r.json()).then(setPresetCategories).catch(() => {})
  }, [])

  async function onCountryChange(country) {
    setSelectedCountry(country)
    setSelectedRegion('')
    setAllCities([])
    setSelectedCities(new Set())
    setCitySearch('')
    if (!country) { setRegions([]); return }
    try {
      const res = await apiFetch(`/api/states/${encodeURIComponent(country)}`)
      setRegions(await res.json())
    } catch { toast('Failed to load regions', 'error') }
  }

  async function onRegionChange(region) {
    setSelectedRegion(region)
    setAllCities([])
    setSelectedCities(new Set())
    setCitySearch('')
    if (!region) return
    try {
      const res = await apiFetch(`/api/cities/${encodeURIComponent(selectedCountry)}/${encodeURIComponent(region)}`)
      const cities = await res.json()
      setAllCities(cities)
      toast(`Loaded ${cities.length.toLocaleString()} cities`, 'success')
    } catch { toast('Failed to load cities', 'error') }
  }

  function toggleCity(city) {
    setSelectedCities(prev => {
      const next = new Set(prev)
      next.has(city) ? next.delete(city) : next.add(city)
      return next
    })
  }

  function addCustomCity() {
    const city = customCity.trim()
    if (!city) return
    if (!allCities.includes(city)) setAllCities(prev => [city, ...prev])
    setSelectedCities(prev => new Set([...prev, city]))
    setCustomCity('')
  }

  const filteredCities = citySearch
    ? allCities.filter(c => c.toLowerCase().includes(citySearch.toLowerCase()))
    : allCities

  const kwList = keywords.split('\n').map(k => k.trim()).filter(Boolean)
  const catList = categories.split('\n').map(k => k.trim()).filter(Boolean)
  const queries = selectedCities.size * kwList.length

  async function startScrape() {
    if (!selectedCountry)         return toast('Select a country first', 'error')
    if (!selectedRegion)          return toast('Select a region first', 'error')
    if (!selectedCities.size)     return toast('Select at least one city', 'error')
    if (!kwList.length)           return toast('Add at least one keyword', 'error')

    try {
      const res = await apiFetch('/api/scrape/start', {
        method: 'POST',
        body: JSON.stringify({
          country: selectedCountry,
          state: selectedRegion,
          cities: [...selectedCities],
          keywords: kwList,
          max_emails: maxEmails,
          relevant_only: relevantOnly,
          categories: relevantOnly ? catList : [],
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Start failed')
      setActiveJobId(data.job_id)
      setLiveResults([])
      const queued = data.status === 'queued'
      setJobStatus({
        status: queued ? 'queued' : 'pending', progress: 0, results_count: 0, email_count: 0,
        message: queued ? (data.message || 'Queued — will start automatically.') : 'Starting...',
        done_tasks: 0, total_tasks: 0,
      })
      startPolling(data.job_id)
      toast(queued
        ? `Job queued — will start when current job finishes`
        : `Job started — scraping ${selectedCities.size} cities`,
        queued ? 'info' : 'success'
      )
    } catch (e) {
      toast('Failed to start: ' + e.message, 'error')
    }
  }

  const startPolling = useCallback((jobId) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/scrape/status/${jobId}`)
        const j = await res.json()
        setJobStatus(j)
        if (j.results_count > 0) {
          try {
            const rRes = await apiFetch(`/api/scrape/results/${jobId}`)
            const rData = await rRes.json()
            if (rData.results) {
              setLiveResults(rData.results.slice(-8).reverse())
            }
          } catch {}
        }
        if (['done', 'cancelled', 'error'].includes(j.status)) {
          clearInterval(pollRef.current)
          pollRef.current = null
          if (j.status === 'done') toast(`Done! ${j.results_count} places, ${j.email_count} emails`, 'success')
          else if (j.status === 'error') toast('Job error: ' + j.message, 'error')
        }
      } catch {}
    }, 2000)
  }, [toast])

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  async function pauseJob() {
    if (!activeJobId) return
    try {
      await apiFetch(`/api/scrape/pause/${activeJobId}`, { method: 'POST' })
      setJobStatus(prev => prev ? { ...prev, status: 'paused', message: 'Paused by user' } : prev)
      toast('Job paused', 'info')
    } catch { toast('Failed to pause job', 'error') }
  }

  async function resumeJob() {
    if (!activeJobId) return
    try {
      await apiFetch(`/api/scrape/resume/${activeJobId}`, { method: 'POST' })
      setJobStatus(prev => prev ? { ...prev, status: 'running', message: 'Scraping in progress...' } : prev)
      startPolling(activeJobId)
      toast('Job resumed', 'success')
    } catch { toast('Failed to resume job', 'error') }
  }

  async function cancelJob() {
    if (!activeJobId) return
    try {
      await apiFetch(`/api/scrape/cancel/${activeJobId}`, { method: 'POST' })
      clearInterval(pollRef.current)
      pollRef.current = null
      setJobStatus(prev => prev ? { ...prev, status: 'cancelled' } : prev)
      toast('Cancellation requested', 'info')
    } catch { toast('Failed to cancel job', 'error') }
  }

  const isRunning = jobStatus && ['running', 'pending'].includes(jobStatus.status)
  const isPaused = jobStatus && jobStatus.status === 'paused'

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Lead Scraper</h1>
          <p className="page-subtitle">Find businesses across 55+ countries — extract decision makers, verified emails & phone numbers</p>
        </div>
        <div className="header-stats">
          <div className="hstat">
            <span className="hstat-val">{selectedCities.size.toLocaleString()}</span>
            <span className="hstat-label">Cities</span>
          </div>
          <div className="hstat-divider"/>
          <div className="hstat">
            <span className="hstat-val">{kwList.length.toLocaleString()}</span>
            <span className="hstat-label">Keywords</span>
          </div>
          <div className="hstat-divider"/>
          <div className="hstat">
            <span className="hstat-val">{queries.toLocaleString()}</span>
            <span className="hstat-label">Queries</span>
          </div>
        </div>
      </div>

      <div className="scraper-layout">
        {/* Step 1: Location */}
        <section className="panel">
          <div className="panel-header">
            <div className="step-badge">1</div>
            <div><h2>Location</h2><p>Select country, region, and cities to target</p></div>
          </div>

          {/* Country */}
          <div className="form-group">
            <label>Country</label>
            <select value={selectedCountry} onChange={e => onCountryChange(e.target.value)}>
              <option value="">Select a country...</option>
              {countries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Region / State */}
          <div className="form-group">
            <label>Region / State</label>
            <select value={selectedRegion} onChange={e => onRegionChange(e.target.value)} disabled={!regions.length}>
              <option value="">{regions.length ? 'Select a region...' : '— select country first —'}</option>
              {regions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>

          {/* Cities */}
          <div className="form-group">
            <div className="label-row">
              <label>Cities</label>
              <span className="count-badge">{selectedCities.size.toLocaleString()} selected</span>
            </div>

            {/* Custom city input */}
            <div className="city-toolbar" style={{marginBottom: 6}}>
              <input
                type="text"
                value={customCity}
                onChange={e => setCustomCity(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addCustomCity()}
                placeholder="Type a custom city and press Enter..."
                style={{flex:1, fontSize:13}}
              />
              <button className="btn-ghost" onClick={addCustomCity} style={{whiteSpace:'nowrap'}}>+ Add</button>
            </div>

            <div className="city-toolbar">
              <div className="search-input-wrap">
                <svg className="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <input
                  type="text" value={citySearch}
                  onChange={e => setCitySearch(e.target.value)}
                  placeholder="Search cities..."
                />
              </div>
              <button className="btn-ghost" onClick={() => setSelectedCities(new Set(allCities))}>All</button>
              <button className="btn-ghost" onClick={() => setSelectedCities(new Set())}>Clear</button>
            </div>

            <div className="city-list">
              {!allCities.length && <div className="city-empty">
                {selectedRegion ? 'No cities found' : 'Select a region to see cities'}
              </div>}
              {filteredCities.map(c => (
                <div
                  key={c}
                  className={`city-chip${selectedCities.has(c) ? ' selected' : ''}`}
                  onClick={() => toggleCity(c)}
                >{c}</div>
              ))}
            </div>
          </div>
        </section>

        {/* Step 2: Keywords */}
        <section className="panel">
          <div className="panel-header">
            <div className="step-badge">2</div>
            <div><h2>Keywords</h2><p>Enter your search terms (one per line)</p></div>
          </div>

          <div className="form-group">
            <div className="label-row">
              <label>Keywords <small style={{color:'var(--muted)'}}>one per line</small></label>
              <div className="kw-actions">
                <span className="count-badge">{kwList.length}</span>
                <button className="btn-ghost" style={{fontSize:11,padding:'3px 8px'}} onClick={() => setKeywords('')}>Clear</button>
              </div>
            </div>

            {Object.keys(presetCategories).length > 0 && (
              <div style={{marginBottom: 10}}>
                <div style={{fontSize: 11, color: 'var(--muted)', marginBottom: 6}}>Quick keyword presets:</div>
                <div style={{display: 'flex', flexWrap: 'wrap', gap: 6}}>
                  <button
                    type="button"
                    className="btn-ghost"
                    style={{fontSize: 11, padding: '3px 8px'}}
                    onClick={() => {
                      const allKws = Object.values(presetCategories).flat()
                      setKeywords(allKws.join('\n'))
                    }}
                  >
                    + All Cold Storage
                  </button>
                  {Object.entries(presetCategories).map(([catName, kws]) => (
                    <button
                      key={catName}
                      type="button"
                      className="btn-ghost"
                      style={{fontSize: 11, padding: '3px 8px'}}
                      onClick={() => {
                        const existing = keywords ? keywords.trim().split('\n').map(k => k.trim()).filter(Boolean) : []
                        const merged = Array.from(new Set([...existing, ...kws]))
                        setKeywords(merged.join('\n'))
                      }}
                    >
                      + {catName}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <textarea
              rows={12}
              value={keywords}
              onChange={e => setKeywords(e.target.value)}
              placeholder={"cold storage\nfreezer room\ncold room\nrefrigerated warehouse\n..."}
            />
          </div>

          <div className="form-group">
            <label>Max emails per business</label>
            <div className="number-input-wrap">
              <button className="num-btn" onClick={() => setMaxEmails(v => Math.max(1, v - 1))}>−</button>
              <input
                type="number" value={maxEmails} min={1} max={10}
                onChange={e => setMaxEmails(Math.min(10, Math.max(1, parseInt(e.target.value) || 1)))}
              />
              <button className="num-btn" onClick={() => setMaxEmails(v => Math.min(10, v + 1))}>+</button>
            </div>
          </div>

          <div className="form-group">
            <label style={{display:'flex',alignItems:'center',gap:8,cursor:'pointer'}}>
              <input
                type="checkbox"
                checked={relevantOnly}
                onChange={e => setRelevantOnly(e.target.checked)}
                style={{width:16,height:16,cursor:'pointer'}}
              />
              <span>Only relevant categories</span>
            </label>
            <p style={{fontSize:12,color:'var(--muted)',margin:'4px 0 0 24px'}}>
              Keeps only businesses whose category matches your keywords — drops Google's
              unrelated padding (museums, hotels, restaurants…).
            </p>

            {relevantOnly && (
              <div style={{margin:'12px 0 0 24px'}}>
                <div className="label-row">
                  <label>Relevant categories <small style={{color:'var(--muted)'}}>optional · one per line</small></label>
                  <div className="kw-actions">
                    <span className="count-badge">{catList.length}</span>
                    {catList.length > 0 &&
                      <button className="btn-ghost" style={{fontSize:11,padding:'3px 8px'}} onClick={() => setCategories('')}>Clear</button>}
                  </div>
                </div>
                <textarea
                  rows={6}
                  value={categories}
                  onChange={e => setCategories(e.target.value)}
                  placeholder={"Architect\nArchitecture firm\nStructural engineer\nGeneral contractor"}
                />
                <p style={{fontSize:12,color:'var(--muted)',margin:'4px 0 0 0'}}>
                  Fill this to keep ONLY these Google Maps categories (exact whitelist).
                  Leave empty to auto-filter from your keywords.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Step 3: Launch */}
        <section className="panel">
          <div className="panel-header">
            <div className="step-badge">3</div>
            <div><h2>Launch</h2><p>Review and start your scrape job</p></div>
          </div>

          <div className="summary-grid">
            <div className="summary-card">
              <div className="summary-icon">🌍</div>
              <div className="summary-val" style={{fontSize: selectedCountry ? 14 : 20}}>{selectedCountry || '—'}</div>
              <div className="summary-label">Country</div>
            </div>
            <div className="summary-card">
              <div className="summary-icon">🏙️</div>
              <div className="summary-val">{selectedCities.size.toLocaleString()}</div>
              <div className="summary-label">Cities</div>
            </div>
            <div className="summary-card">
              <div className="summary-icon">🔑</div>
              <div className="summary-val">{kwList.length.toLocaleString()}</div>
              <div className="summary-label">Keywords</div>
            </div>
            <div className="summary-card">
              <div className="summary-icon">🔍</div>
              <div className="summary-val">{queries.toLocaleString()}</div>
              <div className="summary-label">Queries</div>
            </div>
          </div>

          <button className="btn-primary" onClick={startScrape} disabled={isRunning} style={{width:'100%',justifyContent:'center'}}>
            {isRunning ? (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                Running...
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                Start Scraping
              </>
            )}
          </button>

          {jobStatus && (
            <div className="job-panel">
              <div className="job-panel-header">
                <div className="job-id-wrap">
                  <span className="job-label">Job</span>
                  <code className="job-id">{activeJobId}</code>
                  <span className={`status-dot${jobStatus.status === 'running' ? ' running' : jobStatus.status === 'paused' ? ' paused' : jobStatus.status === 'done' ? ' done' : jobStatus.status === 'error' ? ' error' : ''}`}/>
                </div>
                <div style={{display:'flex',gap:8,alignItems:'center'}}>
                  {isRunning && (
                    <button className="btn-ghost" style={{fontSize:12,padding:'4px 10px'}} onClick={pauseJob}>
                      ⏸️ Pause
                    </button>
                  )}
                  {isPaused && (
                    <button className="btn-ghost" style={{fontSize:12,padding:'4px 10px',color:'#38bdf8',borderColor:'#38bdf8'}} onClick={resumeJob}>
                      ▶️ Resume
                    </button>
                  )}
                  {(isRunning || isPaused) && (
                    <button className="btn-cancel" onClick={cancelJob}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M18 6 6 18M6 6l12 12"/>
                      </svg>
                      Cancel
                    </button>
                  )}
                </div>
              </div>

              <div className="progress-track">
                <div className="progress-fill" style={{width: `${jobStatus.progress}%`}}/>
              </div>
              <div className="progress-label-row">
                <span style={{fontSize:12,color:'var(--muted)'}}>{jobStatus.message}</span>
                <span className="progress-pct">{jobStatus.progress}%</span>
              </div>

              <div className="progress-track" style={{marginTop:10}}>
                <div className="progress-fill" style={{width: `${jobStatus.email_progress ?? 0}%`, background:'#34d399'}}/>
              </div>
              <div className="progress-label-row">
                <span style={{fontSize:12,color:'var(--muted)'}}>
                  Emails{jobStatus.emails_submitted ? ` · ${jobStatus.emails_done}/${jobStatus.emails_submitted} sites` : ''}
                </span>
                <span className="progress-pct">{jobStatus.email_progress ?? 0}%</span>
              </div>

              <div className="job-metrics">
                <div className="metric">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
                  </svg>
                  {jobStatus.results_count.toLocaleString()} places
                </div>
                <div className="metric">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>
                  </svg>
                  {jobStatus.email_count.toLocaleString()} emails
                </div>
                {jobStatus.total_tasks > 0 && (
                  <div className="metric" style={{color:'var(--muted)'}}>
                    {jobStatus.done_tasks}/{jobStatus.total_tasks} queries
                  </div>
                )}
              </div>

              {/* Live Streaming Results */}
              {liveResults.length > 0 && (
                <div className="live-stream-panel" style={{marginTop: 16, background:'rgba(15,23,42,0.6)', border:'1px solid var(--border)', borderRadius:8, padding:10}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                    <span style={{fontSize:12,fontWeight:600,color:'#38bdf8',display:'flex',alignItems:'center',gap:6}}>
                      <span style={{display:'inline-block',width:8,height:8,borderRadius:'50%',background:'#22c55e',animation:'pulse 1.5s infinite'}}/>
                      Live Leads Stream ({liveResults.length} recent)
                    </span>
                    <span style={{fontSize:11,color:'var(--muted)'}}>Real-time updates</span>
                  </div>
                  <div className="table-wrap" style={{maxHeight: 200, overflowY: 'auto'}}>
                    <table className="data-table" style={{fontSize: 11}}>
                      <thead>
                        <tr>
                          <th>Company</th>
                          <th>Decision Makers</th>
                          <th>Phone</th>
                          <th>Email</th>
                          <th>City</th>
                        </tr>
                      </thead>
                      <tbody>
                        {liveResults.map((r, i) => (
                          <tr key={(r.name || '') + i}>
                            <td style={{fontWeight:500,maxWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.name || '—'}</td>
                            <td style={{color:'#38bdf8',maxWidth:160,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={r.decision_makers}>{r.decision_makers || '—'}</td>
                            <td style={{whiteSpace:'nowrap'}}>{r.phone || '—'}</td>
                            <td style={{maxWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                              {r.email ? <a href={`mailto:${r.email.split(',')[0]}`} className="email-link">{r.email.split(',')[0]}</a> : <span style={{color:'var(--muted)'}}>—</span>}
                            </td>
                            <td>{r.city || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {jobStatus.status === 'done' && jobStatus.results_count > 0 && (
                <div className="download-section">
                  <div className="download-label">Export results</div>
                  <div className="download-btns">
                    {['csv','xlsx','json'].map(fmt => (
                      <button key={fmt} className="btn-export"
                        onClick={() => downloadFile(`/api/download/${activeJobId}/${fmt}`, `leads_${activeJobId}.${fmt}`).catch(() => toast('Download failed', 'error'))}>
                        {fmt.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
