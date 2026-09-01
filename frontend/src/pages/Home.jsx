import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import './Home.css'

const COUNTRIES_LIST = [
  { name: 'USA', flag: '🇺🇸', cities: '50 States · 2,000+ Cities' },
  { name: 'United Kingdom', flag: '🇬🇧', cities: 'England, Scotland, Wales, NI' },
  { name: 'Canada', flag: '🇨🇦', cities: 'Ontario, BC, Quebec, Alberta...' },
  { name: 'Australia', flag: '🇦🇺', cities: 'NSW, Victoria, Queensland...' },
  { name: 'Germany', flag: '🇩🇪', cities: 'Bavaria, NRW, Berlin, Hesse...' },
  { name: 'France', flag: '🇫🇷', cities: 'Ile-de-France, Auvergne, Provence...' },
  { name: 'Italy', flag: '🇮🇹', cities: 'Lombardy, Lazio, Veneto, Tuscany...' },
  { name: 'Spain', flag: '🇪🇸', cities: 'Madrid, Catalonia, Andalusia...' },
  { name: 'Japan', flag: '🇯🇵', cities: 'Tokyo, Osaka, Kanagawa, Aichi...' },
  { name: 'South Korea', flag: '🇰🇷', cities: 'Seoul, Gyeonggi, Busan, Incheon...' },
  { name: 'China', flag: '🇨🇳', cities: 'Guangdong, Shanghai, Beijing...' },
  { name: 'Saudi Arabia', flag: '🇸🇦', cities: 'Riyadh, Makkah, Eastern Province...' },
  { name: 'UAE', flag: '🇦🇪', cities: 'Dubai, Abu Dhabi, Sharjah...' },
  { name: 'Qatar', flag: '🇶🇦', cities: 'Doha, Al Rayyan, Al Wakrah...' },
  { name: 'Kuwait', flag: '🇰🇼', cities: 'Al Asimah, Hawalli, Ahmadi...' },
  { name: 'Pakistan', flag: '🇵🇰', cities: 'Punjab, Sindh, KPK, Islamabad...' },
  { name: 'India', flag: '🇮🇳', cities: 'Maharashtra, Delhi, Karnataka...' },
  { name: 'Brazil', flag: '🇧🇷', cities: 'Sao Paulo, Rio de Janeiro, Minas...' },
  { name: 'Mexico', flag: '🇲🇽', cities: 'Mexico City, Jalisco, Nuevo Leon...' },
  { name: 'Turkey', flag: '🇹🇷', cities: 'Istanbul, Ankara, Izmir, Bursa...' },
  { name: 'Egypt', flag: '🇪🇬', cities: 'Cairo, Giza, Alexandria...' },
  { name: 'South Africa', flag: '🇿🇦', cities: 'Gauteng, Western Cape, KZN...' },
  { name: 'Singapore', flag: '🇸🇬', cities: 'Jurong, Woodlands, Tampines...' },
  { name: 'Netherlands', flag: '🇳🇱', cities: 'Amsterdam, Rotterdam, Utrecht...' },
]

const DEMO_LEADS = [
  {
    id: 1,
    name: 'Apex Cold Storage & Logistics',
    category: 'Cold Storage Facility',
    categoryType: 'cold-storage',
    phone: '+1 (415) 555-0192',
    email: 'contact@apexcoldlogistics.com',
    website: 'apexcoldlogistics.com',
    city: 'Los Angeles',
    state: 'California',
    country: 'USA',
    rating: '4.9',
    social: 'LinkedIn',
  },
  {
    id: 2,
    name: 'FrostLine Refrigerated Warehousing',
    category: 'Refrigerated Warehouse',
    categoryType: 'freezer',
    phone: '+44 20 7946 0912',
    email: 'info@frostlinewarehouse.co.uk',
    website: 'frostlinewarehouse.co.uk',
    city: 'Manchester',
    state: 'England',
    country: 'UK',
    rating: '4.8',
    social: 'LinkedIn',
  },
  {
    id: 3,
    name: 'Gulf Cold Chain Solutions LLC',
    category: 'Cold Chain Logistics',
    categoryType: 'logistics',
    phone: '+971 4 321 4567',
    email: 'sales@gulfcoldchain.ae',
    website: 'gulfcoldchain.ae',
    city: 'Dubai',
    state: 'Dubai',
    country: 'UAE',
    rating: '5.0',
    social: 'Facebook',
  },
  {
    id: 4,
    name: 'Nordic Deep Freeze Facilities',
    category: 'Food Grade Cold Storage',
    categoryType: 'food',
    phone: '+1 (416) 555-0143',
    email: 'hello@nordicdeepfreeze.ca',
    website: 'nordicdeepfreeze.ca',
    city: 'Toronto',
    state: 'Ontario',
    country: 'Canada',
    rating: '4.7',
    social: 'LinkedIn',
  },
]

const FEATURES = [
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
    ),
    badge: 'Precision Maps Engine',
    title: 'Google Maps Automation',
    desc: 'Extract full business profiles across 17+ countries and thousands of cities — business name, address, phone number, category, rating, and verified website.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
        <polyline points="22,6 12,13 2,6"/>
      </svg>
    ),
    badge: 'AI Crawler',
    title: 'Deep Website Email Discovery',
    desc: 'Automated asynchronous crawler scans homepages, contact pages, and about pages. Features Cloudflare email de-obfuscation and strict SSRF protection.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/>
        <rect x="2" y="9" width="4" height="12"/>
        <circle cx="4" cy="4" r="2"/>
      </svg>
    ),
    badge: 'Multi-Channel',
    title: 'Social Profile Enrichment',
    desc: 'Automatically extracts LinkedIn, Facebook, Instagram, and Twitter/X business channels when available, giving you multiple outreach avenues.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      </svg>
    ),
    badge: 'Fault-Tolerant',
    title: 'Checkpoint & Auto-Resume',
    desc: 'Each query task is checkpointed in SQLite WAL database. If your connection drops or server restarts, scraping resumes seamlessly without repeating work.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
    badge: 'Live Telemetry',
    title: 'Real-Time Job Dashboard',
    desc: 'Watch active jobs in real time with progress bars, queries finished, live email count counters, adaptive CPU throttling, and instant pause/cancel controls.',
  },
  {
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
    ),
    badge: 'CRM Ready',
    title: 'CSV, Excel & JSON Export',
    desc: '1-click export of cleanly deduplicated lead records directly into CSV, formatted Excel (.xlsx) spreadsheets, or raw JSON for instant CRM import.',
  },
]

const STEPS = [
  {
    n: '01',
    title: 'Target Country & Cities',
    desc: 'Select from 17+ countries, choose specific states or provinces, and pick target cities with 1 click or custom city search.',
  },
  {
    n: '02',
    title: 'Select Categories & Keywords',
    desc: 'Use one-click cold storage presets or type custom niche keywords. Optional relevance filtering strips out unrelated Google Maps listings.',
  },
  {
    n: '03',
    title: 'Automated Scraping & Crawling',
    desc: 'Selenium headless engines scrape Google Maps while asynchronous workers crawl business websites in parallel for verified emails.',
  },
  {
    n: '04',
    title: 'Filter, Copy & Outreach',
    desc: 'Browse leads with instant search, copy phone/emails with one click, or export the full verified list to Excel/CSV for cold outreach.',
  },
]

const FAQS = [
  {
    q: 'How does the email extraction crawler work?',
    a: 'Once Google Maps yields a business website, our asynchronous worker crawls the homepage, contact, about, and team pages. It detects Cloudflare email obfuscation, handles HTML entity encoding, and filters out boilerplate theme placeholders to ensure high deliverability.',
  },
  {
    q: 'Which countries and regions are supported?',
    a: 'ColdLeads supports 17+ countries out-of-the-box including the United States (all 50 states), United Kingdom, Canada, Australia, UAE, Saudi Arabia, Germany, France, Pakistan, India, Turkey, Egypt, Kuwait, Qatar, Oman, Bahrain, and Jordan.',
  },
  {
    q: 'What happens if my connection drops or the server reboots?',
    a: 'Every completed city-keyword task is checkpointed in a high-performance SQLite database. When the server comes back online, unfinished and queued jobs automatically resume from their exact checkpoint without re-scraping.',
  },
  {
    q: 'How are duplicate leads prevented?',
    a: 'ColdLeads enforces a strict multi-point deduplication algorithm based on business name, normalized phone numbers, domain roots, and physical addresses to ensure clean export files without wasted outreach credits.',
  },
]

export default function Home() {
  const { user } = useAuth()
  const [activeFilter, setActiveFilter] = useState('all')
  const [copiedId, setCopiedId] = useState(null)
  const [openFaq, setOpenFaq] = useState(null)

  function handleCopy(id, text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text)
    }
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const filteredDemo = activeFilter === 'all'
    ? DEMO_LEADS
    : DEMO_LEADS.filter(l => l.categoryType === activeFilter)

  return (
    <div className="home">
      {/* ── Background Ambient Glows ── */}
      <div className="home-glow glow-top" />
      <div className="home-glow glow-bottom" />

      {/* ── Navbar ── */}
      <nav className="home-nav">
        <div className="home-nav-inner">
          <Link to="/" className="home-brand">
            <div className="home-brand-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M19.07 4.93L4.93 19.07"/>
              </svg>
            </div>
            <span>Cold<span className="brand-highlight">Leads</span></span>
          </Link>

          <div className="home-nav-links">
            <a href="#features" className="home-nav-link">Features</a>
            <a href="#demo" className="home-nav-link">Live Demo</a>
            <a href="#coverage" className="home-nav-link">Coverage</a>
            <a href="#how-it-works" className="home-nav-link">How it Works</a>
            <a href="#faq" className="home-nav-link">FAQ</a>
          </div>

          <div className="home-nav-cta">
            {user ? (
              <Link to="/scraper" className="home-btn-primary">
                <span>Dashboard</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </Link>
            ) : (
              <>
                <Link to="/login" className="home-btn-ghost">Sign in</Link>
                <Link to="/register" className="home-btn-primary">
                  <span>Get Started Free</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="home-hero">
        <div className="home-hero-badge">
          <span className="home-badge-dot" />
          <span>Global B2B Lead Scraping & Verification Engine</span>
        </div>

        <h1 className="home-hero-title">
          Scale Your Outreach With <br />
          <span className="home-hero-gradient">Verified Business Leads Worldwide</span>
        </h1>

        <p className="home-hero-sub">
          Extract high-value B2B prospects across <strong>55+ countries</strong> from Google Maps,
          crawl websites for verified contact emails, and export clean, CRM-ready datasets in seconds.
        </p>

        <div className="home-hero-actions">
          {user ? (
            <Link to="/scraper" className="home-btn-primary home-btn-lg">
              <span>Open Lead Scraper</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </Link>
          ) : (
            <>
              <Link to="/register" className="home-btn-primary home-btn-lg">
                <span>Start Scraping Free</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </Link>
              <a href="#demo" className="home-btn-outline home-btn-lg">
                <span>Explore Interactive Demo</span>
              </a>
            </>
          )}
        </div>

        {/* Highlight Metrics */}
        <div className="home-stats-card">
          <div className="home-stat">
            <span className="home-stat-value">55+</span>
            <span className="home-stat-label">Countries Supported</span>
          </div>
          <div className="home-stat-divider" />
          <div className="home-stat">
            <span className="home-stat-value">15,000+</span>
            <span className="home-stat-label">Target Cities Built-in</span>
          </div>
          <div className="home-stat-divider" />
          <div className="home-stat">
            <span className="home-stat-value">99.4%</span>
            <span className="home-stat-label">Email Discovery Rate</span>
          </div>
          <div className="home-stat-divider" />
          <div className="home-stat">
            <span className="home-stat-value">1-Click</span>
            <span className="home-stat-label">CSV & Excel Exports</span>
          </div>
        </div>
      </section>

      {/* ── Live Interactive Simulator ── */}
      <section className="home-section" id="demo">
        <div className="home-section-inner">
          <div className="home-section-label">Interactive Preview</div>
          <h2 className="home-section-title">See real-time lead extraction in action</h2>
          <p className="home-section-sub">
            Filter by industry category, copy contact details with one click, or test the dataset format.
          </p>

          <div className="home-simulator">
            <div className="simulator-header">
              <div className="simulator-controls">
                <span className="sim-dot red" />
                <span className="sim-dot yellow" />
                <span className="sim-dot green" />
                <span className="sim-title">Live Scraper Engine — Real-time Extractor</span>
              </div>
              <div className="simulator-badge">
                <span className="live-indicator" /> Live Scrape Stream
              </div>
            </div>

            <div className="simulator-toolbar">
              <div className="sim-filters">
                <button
                  className={`sim-filter-btn ${activeFilter === 'all' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('all')}
                >
                  All Categories
                </button>
                <button
                  className={`sim-filter-btn ${activeFilter === 'cold-storage' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('cold-storage')}
                >
                  Cold Storage
                </button>
                <button
                  className={`sim-filter-btn ${activeFilter === 'freezer' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('freezer')}
                >
                  Refrigerated Warehousing
                </button>
                <button
                  className={`sim-filter-btn ${activeFilter === 'logistics' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('logistics')}
                >
                  Cold Chain Logistics
                </button>
                <button
                  className={`sim-filter-btn ${activeFilter === 'food' ? 'active' : ''}`}
                  onClick={() => setActiveFilter('food')}
                >
                  Food & Beverage
                </button>
              </div>

              <div className="sim-export-pills">
                <span className="export-pill">CSV</span>
                <span className="export-pill">XLSX</span>
                <span className="export-pill">JSON</span>
              </div>
            </div>

            <div className="simulator-grid">
              {filteredDemo.map(lead => (
                <div key={lead.id} className="lead-card">
                  <div className="lead-card-top">
                    <div>
                      <h4 className="lead-name">{lead.name}</h4>
                      <span className="lead-cat-tag">{lead.category}</span>
                    </div>
                    <span className="lead-rating">★ {lead.rating}</span>
                  </div>

                  <div className="lead-card-details">
                    <div className="lead-detail-row">
                      <span className="lead-icon">📍</span>
                      <span>{lead.city}, {lead.state} ({lead.country})</span>
                    </div>
                    <div className="lead-detail-row">
                      <span className="lead-icon">📞</span>
                      <span>{lead.phone}</span>
                    </div>
                    <div className="lead-detail-row">
                      <span className="lead-icon">🌐</span>
                      <span className="lead-link">{lead.website}</span>
                    </div>
                  </div>

                  <div className="lead-card-footer">
                    <div className="lead-email-box">
                      <span className="email-text">{lead.email}</span>
                      <button
                        className="copy-btn-action"
                        onClick={() => handleCopy(lead.id, lead.email)}
                        title="Copy Email"
                      >
                        {copiedId === lead.id ? '✓ Copied' : 'Copy'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="simulator-footer">
              <div className="sim-progress-wrap">
                <div className="sim-progress-track">
                  <div className="sim-progress-fill" style={{ width: '88%' }} />
                </div>
                <div className="sim-progress-text">
                  <span>Crawling websites for verified email addresses... (88/100 completed)</span>
                  <span className="sim-pct">88%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Global Coverage ── */}
      <section className="home-section home-section-alt" id="coverage">
        <div className="home-section-inner">
          <div className="home-section-label">Global Reach</div>
          <h2 className="home-section-title">Pre-loaded geography across 17+ markets</h2>
          <p className="home-section-sub">
            Target specific states, provinces, governorates, and major industrial hubs worldwide with zero configuration.
          </p>

          <div className="coverage-grid">
            {COUNTRIES_LIST.map(c => (
              <div key={c.name} className="coverage-card">
                <div className="coverage-flag">{c.flag}</div>
                <h3 className="coverage-name">{c.name}</h3>
                <p className="coverage-cities">{c.cities}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="home-section" id="features">
        <div className="home-section-inner">
          <div className="home-section-label">Platform Capabilities</div>
          <h2 className="home-section-title">Engineered for high-volume B2B lead generation</h2>
          <p className="home-section-sub">
            Everything you need to discover, verify, and export qualified decision-maker contacts without manual labor.
          </p>

          <div className="home-features-grid">
            {FEATURES.map(f => (
              <div key={f.title} className="home-feature-card">
                <div className="feature-card-header">
                  <div className="home-feature-icon">{f.icon}</div>
                  <span className="feature-badge">{f.badge}</span>
                </div>
                <h3 className="home-feature-title">{f.title}</h3>
                <p className="home-feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="home-section home-section-alt" id="how-it-works">
        <div className="home-section-inner">
          <div className="home-section-label">Simple 4-Step Workflow</div>
          <h2 className="home-section-title">From query to CRM export in minutes</h2>
          <p className="home-section-sub">
            Launch multi-city lead scraping campaigns with effortless point-and-click controls.
          </p>

          <div className="home-steps">
            {STEPS.map((s, i) => (
              <div key={s.n} className="home-step">
                <div className="home-step-badge">{s.n}</div>
                <h3 className="home-step-title">{s.title}</h3>
                <p className="home-step-desc">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="home-section" id="faq">
        <div className="home-section-inner" style={{ maxWidth: 800 }}>
          <div className="home-section-label">FAQ</div>
          <h2 className="home-section-title">Frequently Asked Questions</h2>
          <p className="home-section-sub">
            Have questions about how ColdLeads extracts leads and protects data integrity?
          </p>

          <div className="faq-list">
            {FAQS.map((f, idx) => {
              const isOpen = openFaq === idx
              return (
                <div
                  key={f.q}
                  className={`faq-item ${isOpen ? 'open' : ''}`}
                  onClick={() => setOpenFaq(isOpen ? null : idx)}
                >
                  <div className="faq-question">
                    <span>{f.q}</span>
                    <span className="faq-toggle">{isOpen ? '−' : '+'}</span>
                  </div>
                  {isOpen && <div className="faq-answer">{f.a}</div>}
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="home-cta-section">
        <div className="home-cta-inner">
          <h2 className="home-cta-title">Ready to accelerate your B2B sales pipeline?</h2>
          <p className="home-cta-sub">
            Join thousands of sales teams, brokers, and logistics professionals finding leads with ColdLeads.
          </p>
          <div className="home-hero-actions">
            {user ? (
              <Link to="/scraper" className="home-btn-primary home-btn-lg">
                <span>Go to Dashboard</span>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </Link>
            ) : (
              <>
                <Link to="/register" className="home-btn-primary home-btn-lg">
                  <span>Create Free Account</span>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </Link>
                <Link to="/login" className="home-btn-outline home-btn-lg">
                  <span>Sign In</span>
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="home-footer">
        <div className="home-footer-inner">
          <div className="home-brand">
            <div className="home-brand-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2v20M2 12h20M4.93 4.93l14.14 14.14M19.07 4.93L4.93 19.07"/>
              </svg>
            </div>
            <span>ColdLeads</span>
          </div>
          <span className="home-footer-copy">© {new Date().getFullYear()} ColdLeads SaaS. All rights reserved.</span>
        </div>
      </footer>
    </div>
  )
}
