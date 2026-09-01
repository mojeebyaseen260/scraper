import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useToast } from '../context/ToastContext.jsx'

export default function Outreach() {
  const { authFetch, user } = useAuth()
  const { showToast } = useToast()

  const [tab, setTab] = useState('campaign') // 'campaign' | 'settings' | 'history'

  // SMTP Settings State
  const [smtpSettings, setSmtpSettings] = useState({
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_user: '',
    smtp_pass: '',
    from_name: '',
    use_tls: true,
    daily_limit: 500,
    delay_sec: 3.0,
    configured: false,
    has_pass: false,
  })
  const [smtpLoading, setSmtpLoading] = useState(false)
  const [testEmail, setTestEmail] = useState('')
  const [testingSmtp, setTestingSmtp] = useState(false)

  // Campaign State
  const [templates, setTemplates] = useState([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [jobs, setJobs] = useState([])
  const [selectedJobId, setSelectedJobId] = useState('')
  const [jobLeads, setJobLeads] = useState([])
  const [selectedLeads, setSelectedLeads] = useState([])
  const [filterHotOnly, setFilterHotOnly] = useState(false)
  const [sending, setSending] = useState(false)
  const [campaignProgress, setCampaignProgress] = useState(null)

  // History State
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Load Initial Data
  useEffect(() => {
    fetchSmtpSettings()
    fetchTemplates()
    fetchJobs()
    fetchHistory()
  }, [])

  async function fetchSmtpSettings() {
    try {
      const res = await authFetch('/api/smtp/settings')
      if (res.ok) {
        const data = await res.json()
        setSmtpSettings(prev => ({
          ...prev,
          ...data,
          smtp_pass: data.has_pass ? '••••••••••••••••' : '',
        }))
        if (data.smtp_user && !testEmail) {
          setTestEmail(data.smtp_user)
        }
      }
    } catch (err) {
      console.error('Failed to load SMTP settings:', err)
    }
  }

  async function fetchTemplates() {
    try {
      const res = await authFetch('/api/outreach/templates')
      if (res.ok) {
        const data = await res.json()
        setTemplates(data)
        if (data.length > 0) {
          setSelectedTemplate(data[0].id)
          setSubject(data[0].subject)
          setBody(data[0].body)
        }
      }
    } catch (err) {
      console.error('Failed to load templates:', err)
    }
  }

  async function fetchJobs() {
    try {
      const res = await authFetch('/api/scrape/jobs')
      if (res.ok) {
        const data = await res.json()
        setJobs(data)
        if (data.length > 0) {
          setSelectedJobId(data[0].job_id)
          loadJobLeads(data[0].job_id)
        }
      }
    } catch (err) {
      console.error('Failed to load jobs:', err)
    }
  }

  async function loadJobLeads(jobId) {
    if (!jobId) return
    try {
      const res = await authFetch(`/api/scrape/results/${jobId}`)
      if (res.ok) {
        const data = await res.json()
        const leads = (data.results || []).filter(r => r.email && r.email.includes('@'))
        setJobLeads(leads)
        setSelectedLeads(leads.map(l => l.id))
      }
    } catch (err) {
      console.error('Failed to load job leads:', err)
    }
  }

  async function fetchHistory() {
    setHistoryLoading(true)
    try {
      const res = await authFetch('/api/outreach/history')
      if (res.ok) {
        const data = await res.json()
        setHistory(data)
      }
    } catch (err) {
      console.error('Failed to load outreach history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }

  function handleTemplateChange(templateId) {
    setSelectedTemplate(templateId)
    const tpl = templates.find(t => t.id === templateId)
    if (tpl) {
      setSubject(tpl.subject)
      setBody(tpl.body)
    }
  }

  function insertTag(tag) {
    setBody(prev => prev + ` ${tag}`)
  }

  async function handleSaveSmtp(e) {
    e.preventDefault()
    setSmtpLoading(true)
    try {
      const payload = {
        ...smtpSettings,
        smtp_port: parseInt(smtpSettings.smtp_port, 10),
        daily_limit: parseInt(smtpSettings.daily_limit, 10),
        delay_sec: parseFloat(smtpSettings.delay_sec),
        // If password is still masked, don't overwrite with dots
        smtp_pass: smtpSettings.smtp_pass.includes('••') ? '' : smtpSettings.smtp_pass,
      }
      const res = await authFetch('/api/smtp/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (res.ok) {
        showToast('SMTP Settings saved successfully!', 'success')
        fetchSmtpSettings()
      } else {
        showToast(data.detail || 'Failed to save SMTP settings', 'error')
      }
    } catch (err) {
      showToast('Network error while saving SMTP settings', 'error')
    } finally {
      setSmtpLoading(false)
    }
  }

  async function handleTestSmtp() {
    if (!testEmail || !testEmail.includes('@')) {
      showToast('Please enter a valid recipient email for testing', 'warning')
      return
    }
    setTestingSmtp(true)
    try {
      const payload = {
        to_email: testEmail,
        smtp_host: smtpSettings.smtp_host,
        smtp_port: parseInt(smtpSettings.smtp_port, 10),
        smtp_user: smtpSettings.smtp_user,
        smtp_pass: smtpSettings.smtp_pass.includes('••') ? '' : smtpSettings.smtp_pass,
        use_tls: smtpSettings.use_tls,
      }
      const res = await authFetch('/api/smtp/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (res.ok) {
        showToast(data.message || 'Test email sent successfully!', 'success')
      } else {
        showToast(data.detail || 'SMTP test failed', 'error')
      }
    } catch (err) {
      showToast('Error testing SMTP connection', 'error')
    } finally {
      setTestingSmtp(false)
    }
  }

  async function handleSendCampaign() {
    if (!smtpSettings.configured && !smtpSettings.has_pass) {
      showToast('Please configure your SMTP Email settings first in the Settings tab.', 'warning')
      setTab('settings')
      return
    }

    const filtered = jobLeads.filter(l => selectedLeads.includes(l.id))
    if (filtered.length === 0) {
      showToast('No leads selected for outreach campaign', 'warning')
      return
    }

    if (!subject.trim() || !body.trim()) {
      showToast('Please enter an email subject and body', 'warning')
      return
    }

    if (!confirm(`Are you sure you want to send cold emails to ${filtered.length} selected leads?`)) {
      return
    }

    setSending(true)
    setCampaignProgress({ total: filtered.length, sent: 0, failed: 0 })

    try {
      const res = await authFetch('/api/outreach/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          leads: filtered,
          subject,
          body,
          job_id: selectedJobId,
          delay_sec: smtpSettings.delay_sec,
        }),
      })
      const data = await res.json()
      if (res.ok) {
        showToast(data.message || 'Campaign finished successfully!', 'success')
        fetchHistory()
      } else {
        showToast(data.detail || 'Campaign failed', 'error')
      }
    } catch (err) {
      showToast('Error running outreach campaign', 'error')
    } finally {
      setSending(false)
      setCampaignProgress(null)
    }
  }

  const displayedLeads = filterHotOnly
    ? jobLeads.filter(l => l.decision_makers && l.email)
    : jobLeads

  return (
    <div className="outreach-page" style={{ maxWidth: 1200, margin: '0 auto', paddingBottom: 40 }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span>✉️</span> B2B Cold Outreach & Email Campaigns
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: '4px 0 0' }}>
            Send automated, personalized cold emails to scraped decision makers with built-in SMTP delivery.
          </p>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: 'flex', gap: 6, background: 'var(--bg-card)', padding: 4, borderRadius: 8, border: '1px solid var(--border)' }}>
          <button
            onClick={() => setTab('campaign')}
            className={`btn btn-sm ${tab === 'campaign' ? 'btn-primary' : 'btn-glass'}`}
          >
            🚀 Launch Campaign
          </button>
          <button
            onClick={() => setTab('settings')}
            className={`btn btn-sm ${tab === 'settings' ? 'btn-primary' : 'btn-glass'}`}
          >
            ⚙️ SMTP Settings
          </button>
          <button
            onClick={() => { setTab('history'); fetchHistory() }}
            className={`btn btn-sm ${tab === 'history' ? 'btn-primary' : 'btn-glass'}`}
          >
            📋 Sent History
          </button>
        </div>
      </div>

      {/* TAB 1: CAMPAIGN LAUNCHER */}
      {tab === 'campaign' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 24 }}>
          {/* Left Column: Composer */}
          <div className="card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>✍️</span> Email Composer & Templates
            </h3>

            {/* Template Selector */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Choose Outreach Template
              </label>
              <select
                value={selectedTemplate}
                onChange={e => handleTemplateChange(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
              >
                {templates.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* Dynamic Tags Toolbar */}
            <div style={{ marginBottom: 16 }}>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Insert Dynamic Lead Placeholders:
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {['{Decision_Maker}', '{Company}', '{City}', '{Category}', '{From_Name}'].map(tag => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => insertTag(tag)}
                    style={{ fontSize: 11, padding: '3px 8px', background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: 4, cursor: 'pointer' }}
                  >
                    + {tag}
                  </button>
                ))}
              </div>
            </div>

            {/* Subject */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Email Subject Line
              </label>
              <input
                type="text"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                placeholder="e.g. Quick question regarding {Company}"
                style={{ width: '100%', padding: '10px 12px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
              />
            </div>

            {/* Body */}
            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Email Message Body (Plain text & HTML auto-formatted)
              </label>
              <textarea
                rows={10}
                value={body}
                onChange={e => setBody(e.target.value)}
                style={{ width: '100%', padding: '12px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, lineHeight: 1.5, fontFamily: 'inherit' }}
              />
            </div>

            {/* Launch Action */}
            <button
              onClick={handleSendCampaign}
              disabled={sending || displayedLeads.length === 0}
              className="btn btn-primary"
              style={{ width: '100%', padding: '14px', fontSize: 15, fontWeight: 700 }}
            >
              {sending ? '⏳ Sending Campaign...' : `🚀 Send Campaign to ${selectedLeads.length} Selected Leads`}
            </button>
          </div>

          {/* Right Column: Lead Target Selection */}
          <div className="card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>🎯 Target Leads ({displayedLeads.length})</span>
              <label style={{ fontSize: 12, fontWeight: 400, color: '#f87171', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={filterHotOnly}
                  onChange={e => setFilterHotOnly(e.target.checked)}
                />
                🔥 Decision Makers Only
              </label>
            </h3>

            {/* Scrape Job Picker */}
            <div style={{ marginBottom: 14 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                Select Scrape Job
              </label>
              <select
                value={selectedJobId}
                onChange={e => {
                  setSelectedJobId(e.target.value)
                  loadJobLeads(e.target.value)
                }}
                style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
              >
                {jobs.map(j => (
                  <option key={j.job_id} value={j.job_id}>
                    {j.keywords || 'Scrape Job'} — {j.country} ({j.job_id.slice(0, 8)})
                  </option>
                ))}
              </select>
            </div>

            {/* Leads List Box */}
            <div style={{ flex: 1, maxHeight: 400, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 6, background: 'var(--bg-dark)', padding: 8 }}>
              {displayedLeads.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)', fontSize: 13 }}>
                  No leads with valid email addresses found in this job.
                </div>
              ) : (
                displayedLeads.map(lead => {
                  const isChecked = selectedLeads.includes(lead.id)
                  return (
                    <div
                      key={lead.id}
                      onClick={() => {
                        setSelectedLeads(prev =>
                          prev.includes(lead.id) ? prev.filter(id => id !== lead.id) : [...prev, lead.id]
                        )
                      }}
                      style={{
                        padding: '8px 10px',
                        marginBottom: 6,
                        background: isChecked ? 'rgba(2, 132, 199, 0.15)' : 'rgba(255,255,255,0.02)',
                        border: `1px solid ${isChecked ? 'rgba(56, 189, 248, 0.4)' : 'var(--border)'}`,
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 12,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                      }}
                    >
                      <input type="checkbox" checked={isChecked} readOnly />
                      <div style={{ flex: 1, overflow: 'hidden' }}>
                        <div style={{ fontWeight: 600, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {lead.name}
                        </div>
                        <div style={{ color: '#38bdf8', fontSize: 11, fontFamily: 'monospace' }}>
                          {lead.email}
                        </div>
                        {lead.decision_makers && (
                          <div style={{ color: '#fbbf24', fontSize: 10, marginTop: 2 }}>
                            👑 {lead.decision_makers}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
              <button
                type="button"
                onClick={() => setSelectedLeads(displayedLeads.map(l => l.id))}
                style={{ background: 'none', border: 'none', color: '#38bdf8', cursor: 'pointer' }}
              >
                Select All
              </button>
              <button
                type="button"
                onClick={() => setSelectedLeads([])}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                Deselect All
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: SMTP SETTINGS */}
      {tab === 'settings' && (
        <div style={{ maxWidth: 700, margin: '0 auto', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 30 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>⚙️ SMTP Sender Configuration</h3>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
                Connect your Gmail App Password or custom SMTP server to send cold emails.
              </p>
            </div>
            <span style={{
              fontSize: 12,
              padding: '4px 10px',
              borderRadius: 20,
              background: smtpSettings.configured ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
              color: smtpSettings.configured ? '#4ade80' : '#f87171',
              fontWeight: 600,
            }}>
              {smtpSettings.configured ? '● Connected' : '○ Not Configured'}
            </span>
          </div>

          {/* Quick Gmail Notice */}
          <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.2)', borderRadius: 8, padding: 14, marginBottom: 20, fontSize: 13, color: '#e0f2fe' }}>
            💡 <strong>Using Gmail?</strong> Use your normal Gmail address and generate a 16-character <strong>Google App Password</strong> (from Google Account &gt; Security &gt; 2-Step Verification &gt; App passwords).
          </div>

          <form onSubmit={handleSaveSmtp}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  SMTP Host Server
                </label>
                <input
                  type="text"
                  value={smtpSettings.smtp_host}
                  onChange={e => setSmtpSettings({ ...smtpSettings, smtp_host: e.target.value })}
                  placeholder="smtp.gmail.com"
                  required
                  style={{ width: '100%', padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Port
                </label>
                <input
                  type="number"
                  value={smtpSettings.smtp_port}
                  onChange={e => setSmtpSettings({ ...smtpSettings, smtp_port: e.target.value })}
                  placeholder="587"
                  required
                  style={{ width: '100%', padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Sender Email (Username)
                </label>
                <input
                  type="email"
                  value={smtpSettings.smtp_user}
                  onChange={e => setSmtpSettings({ ...smtpSettings, smtp_user: e.target.value })}
                  placeholder="your-email@gmail.com"
                  required
                  style={{ width: '100%', padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  App Password / SMTP Password
                </label>
                <input
                  type="password"
                  value={smtpSettings.smtp_pass}
                  onChange={e => setSmtpSettings({ ...smtpSettings, smtp_pass: e.target.value })}
                  placeholder="16-character App Password (e.g. njbd rjtd rvrz scuh)"
                  required={!smtpSettings.has_pass}
                  style={{ width: '100%', padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  From Name (Display in Inbox)
                </label>
                <input
                  type="text"
                  value={smtpSettings.from_name}
                  onChange={e => setSmtpSettings({ ...smtpSettings, from_name: e.target.value })}
                  placeholder="e.g. John Doe / ColdLeads Outreach"
                  style={{ width: '100%', padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Throttle Delay (Seconds between emails)
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="1"
                  max="30"
                  value={smtpSettings.delay_sec}
                  onChange={e => setSmtpSettings({ ...smtpSettings, delay_sec: e.target.value })}
                  style={{ width: '100%', padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12 }}>
              <button
                type="submit"
                disabled={smtpLoading}
                className="btn btn-primary"
                style={{ flex: 1, padding: '12px' }}
              >
                {smtpLoading ? 'Saving...' : '💾 Save SMTP Settings'}
              </button>
            </div>
          </form>

          {/* Test Connection Section */}
          <div style={{ marginTop: 30, paddingTop: 20, borderTop: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>🧪 Test Connection & Send Verification Email</h4>
            <div style={{ display: 'flex', gap: 10 }}>
              <input
                type="email"
                value={testEmail}
                onChange={e => setTestEmail(e.target.value)}
                placeholder="recipient@example.com"
                style={{ flex: 1, padding: '10px', background: 'var(--bg-dark)', color: '#fff', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}
              />
              <button
                type="button"
                onClick={handleTestSmtp}
                disabled={testingSmtp}
                className="btn btn-glass"
                style={{ padding: '10px 18px', whiteSpace: 'nowrap' }}
              >
                {testingSmtp ? 'Testing...' : 'Send Test Email'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: OUTREACH HISTORY */}
      {tab === 'history' && (
        <div className="card" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>📋 Sent Outreach Log History ({history.length})</h3>
            <button onClick={fetchHistory} className="btn btn-glass btn-sm">🔄 Refresh Logs</button>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '10px 12px' }}>Status</th>
                  <th style={{ padding: '10px 12px' }}>Recipient Email</th>
                  <th style={{ padding: '10px 12px' }}>Company</th>
                  <th style={{ padding: '10px 12px' }}>Decision Maker</th>
                  <th style={{ padding: '10px 12px' }}>Subject</th>
                  <th style={{ padding: '10px 12px' }}>Sent At</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)' }}>
                      No outreach emails sent yet.
                    </td>
                  </tr>
                ) : (
                  history.map(item => (
                    <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '10px 12px' }}>
                        <span style={{
                          padding: '3px 8px',
                          borderRadius: 4,
                          fontSize: 11,
                          fontWeight: 700,
                          background: item.status === 'sent' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                          color: item.status === 'sent' ? '#4ade80' : '#f87171',
                        }}>
                          {item.status === 'sent' ? '✓ SENT' : '✕ FAILED'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 12px', color: '#38bdf8', fontFamily: 'monospace' }}>{item.recipient_email}</td>
                      <td style={{ padding: '10px 12px', fontWeight: 600 }}>{item.company_name || '—'}</td>
                      <td style={{ padding: '10px 12px', color: '#fbbf24' }}>{item.decision_maker || '—'}</td>
                      <td style={{ padding: '10px 12px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.subject}</td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 11 }}>
                        {item.sent_at ? new Date(item.sent_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
