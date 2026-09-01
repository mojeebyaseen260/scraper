// ColdLeads Desktop v2.0 — Landing Page Interactive Scripts

document.addEventListener('DOMContentLoaded', () => {

  // 1. FAQ Accordion Toggle
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    question.addEventListener('click', () => {
      const isActive = item.classList.contains('active');
      faqItems.forEach(f => f.classList.remove('active'));
      if (!isActive) {
        item.classList.add('active');
      }
    });
  });

  // Open first FAQ by default
  if (faqItems.length > 0) {
    faqItems[0].classList.add('active');
  }

  // 2. Interactive Lead Scraper Simulator Data
  const sampleLeads = {
    cold_storage: [
      {
        tier: 'HOT',
        company: 'Polaris Arctic Logistics Ltd',
        dm: 'Alexander Hayes (Managing Director)',
        email: 'alex.hayes@polarislogistic.com',
        phone: '+1 312-555-0192',
        city: 'Chicago, IL',
        rating: '4.9 ★ (128)'
      },
      {
        tier: 'HOT',
        company: 'Apex Freeze & Cold Vault Co',
        dm: 'Marcus Vance (Chief Executive Officer)',
        email: 'm.vance@apexfreezestorage.com',
        phone: '+1 213-555-4819',
        city: 'Los Angeles, CA',
        rating: '4.8 ★ (94)'
      },
      {
        tier: 'WARM',
        company: 'Glacier Temperature Chain Ltd',
        dm: 'Sarah Jenkins (Marketing Director)',
        email: 'contact@glacierchains.co.uk',
        phone: '+44 20 7946 0912',
        city: 'London, UK',
        rating: '4.7 ★ (62)'
      },
      {
        tier: 'HOT',
        company: 'Nordic Chill Solutions GmbH',
        dm: 'Klaus Schmidt (General Manager)',
        email: 'klaus.schmidt@nordicchill.de',
        phone: '+49 89 2018 9910',
        city: 'Munich, Germany',
        rating: '5.0 ★ (45)'
      },
    ],
    digital_marketing: [
      {
        tier: 'HOT',
        company: 'Nexus Digital Growth Partners',
        dm: 'Elena Rostova (Founder & CEO)',
        email: 'elena@nexusgrowth.io',
        phone: '+1 415-555-0821',
        city: 'San Francisco, CA',
        rating: '4.9 ★ (210)'
      },
      {
        tier: 'HOT',
        company: 'OmniChannel B2B Media Group',
        dm: 'David Miller (Head of Marketing)',
        email: 'david@omnichannelb2b.com',
        phone: '+1 212-555-9301',
        city: 'New York, NY',
        rating: '4.8 ★ (115)'
      },
      {
        tier: 'WARM',
        company: 'Pulse SEO & Web Performance',
        dm: 'Liam Davies (Operations Manager)',
        email: 'info@pulsemarketing.co.uk',
        phone: '+44 161 496 0182',
        city: 'Manchester, UK',
        rating: '4.6 ★ (88)'
      }
    ],
    healthcare: [
      {
        tier: 'HOT',
        company: 'St. Jude Specialty Care Clinic',
        dm: 'Dr. Arthur Bennett (Chief Medical Officer)',
        email: 'dr.bennett@stjudecare.org',
        phone: '+1 617-555-3210',
        city: 'Boston, MA',
        rating: '5.0 ★ (340)'
      },
      {
        tier: 'HOT',
        company: 'Bavaria Diagnostic & Wellness Center',
        dm: 'Hans Weber (Managing Director)',
        email: 'h.weber@bavariamed.de',
        phone: '+49 30 5519 2201',
        city: 'Berlin, Germany',
        rating: '4.9 ★ (190)'
      }
    ],
    real_estate: [
      {
        tier: 'HOT',
        company: 'Vanguard Commercial Real Estate',
        dm: 'Robert King (Principal Broker)',
        email: 'r.king@vanguardproperties.com',
        phone: '+1 713-555-8821',
        city: 'Houston, TX',
        rating: '4.8 ★ (155)'
      },
      {
        tier: 'WARM',
        company: 'Horizon Property Management Ltd',
        dm: 'Victoria Sterling (Director of Operations)',
        email: 'victoria@horizonprop.co.uk',
        phone: '+44 121 496 0341',
        city: 'Birmingham, UK',
        rating: '4.7 ★ (78)'
      }
    ],
    solar: [
      {
        tier: 'HOT',
        company: 'SunPower Commercial Solar Systems',
        dm: 'Jack Thompson (VP of Commercial Sales)',
        email: 'j.thompson@sunpowersys.com',
        phone: '+1 602-555-7740',
        city: 'Phoenix, AZ',
        rating: '4.9 ★ (220)'
      },
      {
        tier: 'HOT',
        company: 'Helios Clean Energy Contractors',
        dm: 'Lucas Moreno (General Manager)',
        email: 'lucas@helioscontractors.com',
        phone: '+1 305-555-6619',
        city: 'Miami, FL',
        rating: '4.8 ★ (98)'
      }
    ]
  };

  const simTableBody = document.getElementById('simTableBody');
  const simIndustry = document.getElementById('simIndustry');
  const simScrapeBtn = document.getElementById('simScrapeBtn');

  function renderTable(industryKey) {
    if (!simTableBody) return;
    const items = sampleLeads[industryKey] || sampleLeads['cold_storage'];
    simTableBody.innerHTML = '';

    items.forEach((item, index) => {
      const tr = document.createElement('tr');
      tr.style.opacity = '0';
      tr.style.transform = 'translateY(10px)';
      tr.style.transition = 'all 0.3s ease';

      const isHot = item.tier === 'HOT';
      tr.innerHTML = `
        <td><span class="${isHot ? 'mock-badge-hot' : 'mock-badge-warm'}">🔥 ${item.tier}</span></td>
        <td style="font-weight: 600;">${item.company}</td>
        <td><span class="mock-dm">👤 ${item.dm}</span></td>
        <td><a href="mailto:${item.email}" class="mock-email">${item.email}</a></td>
        <td style="font-family: 'JetBrains Mono', monospace; font-size: 11px;">${item.phone}</td>
        <td>${item.city}</td>
        <td style="color: #f59e0b; font-weight: 600;">${item.rating}</td>
      `;

      simTableBody.appendChild(tr);

      setTimeout(() => {
        tr.style.opacity = '1';
        tr.style.transform = 'translateY(0)';
      }, index * 80);
    });
  }

  // Initial render
  renderTable('cold_storage');

  if (simIndustry) {
    simIndustry.addEventListener('change', (e) => {
      renderTable(e.target.value);
    });
  }

  if (simScrapeBtn) {
    simScrapeBtn.addEventListener('click', () => {
      simScrapeBtn.innerHTML = '⏳ Scraping Live...';
      simScrapeBtn.disabled = true;
      simTableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--primary-glow);">⚡ Multi-threaded Chrome Crawling in progress...</td></tr>';
      
      setTimeout(() => {
        simScrapeBtn.innerHTML = '⚡ Simulate Scrape';
        simScrapeBtn.disabled = false;
        renderTable(simIndustry.value);
      }, 900);
    });
  }

});
