/**
 * LabelBox SPA Orchestrator
 * Manages screen navigation, user state, camera handling, and result rendering.
 */
const App = (() => {
  // ── State ─────────────────────────────────────────────────────────────
  let currentOfficer = null;
  let currentSession = null;
  let capturedImageBlob = null;

  // ── DOM helpers ───────────────────────────────────────────────────────
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // ── View navigation ──────────────────────────────────────────────────
  function showView(viewId) {
    $$('.view').forEach((v) => v.classList.remove('active'));
    const view = $(`#${viewId}`);
    if (view) view.classList.add('active');

    // Update bottom nav
    $$('.bottom-nav-item').forEach((item) => {
      item.classList.toggle('active', item.dataset.view === viewId);
    });
  }

  // ── Toast notifications ───────────────────────────────────────────────
  function showToast(message, type = 'info') {
    const container = $('#toast-container');
    const toast = document.createElement('div');
    const colors = {
      success: 'bg-emerald-600',
      error: 'bg-red-600',
      info: 'bg-ink',
      warning: 'bg-amber-600',
    };
    toast.className = `${colors[type] || colors.info} text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 animate-in`;
    toast.innerHTML = `
      <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
      <span>${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3500);
  }

  // ── Login ─────────────────────────────────────────────────────────────
  function initLogin() {
    const form = $('#login-form');
    const emailInput = $('#login-email');
    const passwordInput = $('#login-password');
    const errorEl = $('#login-error');
    const submitBtn = $('#login-submit');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorEl.classList.add('hidden');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="animate-spin inline-block w-5 h-5 border-2 border-lime border-t-transparent rounded-full"></span> Signing in…';

      try {
        const data = await API.login(emailInput.value.trim(), passwordInput.value);
        currentOfficer = data;
        onLoginSuccess();
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove('hidden');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Sign in';
      }
    });

    // Quick demo login buttons
    $$('.demo-login-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        emailInput.value = btn.dataset.email;
        passwordInput.value = btn.dataset.password;
      });
    });
  }

  function setCurrentSession(session) {
    currentSession = session;
    const storeEl = $('#active-session-store');
    const locEl = $('#active-session-location');
    const idEl = $('#active-session-id');
    const indEl = $('#active-session-indicator');

    if (session) {
      try {
        localStorage.setItem('labelbox_session', JSON.stringify(session));
      } catch { /* storage full/disabled */ }
      if (storeEl) storeEl.textContent = session.store_name;
      if (locEl) locEl.textContent = session.location || '—';
      if (idEl) idEl.textContent = session.id ? session.id.slice(0, 8) + '…' : '—';
      if (indEl) indEl.className = 'w-2 h-2 bg-success rounded-full animate-pulse';
    } else {
      localStorage.removeItem('labelbox_session');
      if (storeEl) storeEl.textContent = 'No active session (tap to start)';
      if (locEl) locEl.textContent = '—';
      if (idEl) idEl.textContent = '—';
      if (indEl) indEl.className = 'w-2 h-2 bg-amber-500 rounded-full';
    }
  }

  async function restoreSession() {
    try {
      const saved = localStorage.getItem('labelbox_session');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.id) {
          try {
            const fresh = await API.getSession(parsed.id);
            setCurrentSession(fresh);
            return fresh;
          } catch {
            localStorage.removeItem('labelbox_session');
          }
        }
      }
      // Check existing sessions for this officer
      const sessions = await API.listSessions();
      if (sessions && sessions.length > 0) {
        setCurrentSession(sessions[0]);
        return sessions[0];
      }
    } catch (err) {
      console.warn('Session auto-restore error:', err);
    }
    setCurrentSession(null);
    return null;
  }

  async function onLoginSuccess() {
    $('#officer-name').textContent = currentOfficer.name;
    $('#officer-email').textContent = currentOfficer.email;
    const restored = await restoreSession();
    if (restored) {
      showView('view-capture');
      showToast(`Welcome back, ${currentOfficer.name.split(' ').pop()}! (Active: ${restored.store_name})`, 'success');
    } else {
      showView('view-session');
      showToast(`Welcome, ${currentOfficer.name.split(' ').pop()}! Please start an inspection session.`, 'success');
    }
  }

  // ── Session ───────────────────────────────────────────────────────────
  function initSession() {
    const form = $('#session-form');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const storeName = $('#session-store').value.trim();
      const location = $('#session-location').value.trim();
      if (!storeName) return;

      const btn = $('#session-submit');
      btn.disabled = true;
      btn.textContent = 'Creating…';

      try {
        const newSession = await API.createSession(storeName, location);
        setCurrentSession(newSession);
        onSessionCreated();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Start Inspection';
      }
    });
  }

  function onSessionCreated() {
    showView('view-capture');
    showToast('Inspection session started', 'success');
  }

  // ── Capture ───────────────────────────────────────────────────────────
  function initCapture() {
    const fileInput = $('#capture-input');
    const dropZone = $('#drop-zone');
    const previewContainer = $('#preview-container');
    const previewImg = $('#preview-img');
    const scanBtn = $('#scan-submit-btn');
    const retakeBtn = $('#retake-btn');
    const sessionBar = $('#active-session-bar');

    if (sessionBar) {
      sessionBar.addEventListener('click', () => {
        showView('view-session');
      });
    }

    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) handleImageSelected(file);
    });

    // Drop zone
    if (dropZone) {
      dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
      dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
      dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleImageSelected(file);
      });
      dropZone.addEventListener('click', (e) => {
        if (e.target !== fileInput) fileInput.click();
      });
    }

    retakeBtn.addEventListener('click', () => {
      resetCapture();
    });

    scanBtn.addEventListener('click', () => submitCapturedScan());
  }

  function handleImageSelected(file) {
    capturedImageBlob = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      $('#preview-img').src = e.target.result;
      $('#preview-container').classList.remove('hidden');
      $('#drop-zone').classList.add('hidden');
      $('#scan-submit-btn').classList.remove('hidden');
      $('#retake-btn').classList.remove('hidden');
    };
    reader.readAsDataURL(file);
  }

  async function submitCapturedScan() {
    if (!capturedImageBlob) {
      showToast('Please select or capture a label image first', 'warning');
      return;
    }

    if (!currentSession) {
      const restored = await restoreSession();
      if (!restored) {
        showToast('Please start an inspection session first', 'warning');
        showView('view-session');
        return;
      }
    }

    const scanBtn = $('#scan-submit-btn');
    scanBtn.disabled = true;
    scanBtn.innerHTML = '<span class="animate-spin inline-block w-5 h-5 border-2 border-lime border-t-transparent rounded-full"></span> Analyzing label…';

    // Show processing view
    showView('view-processing');

    try {
      if (!navigator.onLine) {
        await OfflineQueue.enqueue(currentSession.id, capturedImageBlob);
        showToast('Scan queued for offline sync', 'warning');
        resetCapture();
        showView('view-capture');
        return;
      }

      const result = await API.submitScan(currentSession.id, capturedImageBlob);
      renderResult(result);
      resetCapture();
      showView('view-result');
    } catch (err) {
      console.error('Scan submission failed:', err);
      const isNetwork = !navigator.onLine ||
        err.message?.toLowerCase().includes('failed to fetch') ||
        err.message?.toLowerCase().includes('network');

      if (isNetwork) {
        try {
          await OfflineQueue.enqueue(currentSession.id, capturedImageBlob);
          showToast('Network issue — scan queued offline for sync', 'warning');
          resetCapture();
        } catch {
          showToast('Scan could not be submitted: ' + err.message, 'error');
        }
      } else if (err.message?.includes('Session expired') || err.message?.includes('401')) {
        showToast('Session expired. Please sign in again.', 'error');
        showView('view-login');
        return;
      } else if (err.message?.includes('not found') || err.message?.includes('404')) {
        showToast('Inspection session was not found. Please start a new session.', 'error');
        setCurrentSession(null);
        showView('view-session');
        return;
      } else {
        showToast('Analysis error: ' + err.message, 'error');
      }
      showView('view-capture');
    } finally {
      scanBtn.disabled = false;
      scanBtn.innerHTML = '🔍 Analyze Label';
    }
  }

  function resetCapture() {
    capturedImageBlob = null;
    const fileInput = $('#capture-input');
    if (fileInput) fileInput.value = '';
    $('#preview-container')?.classList.add('hidden');
    $('#drop-zone')?.classList.remove('hidden');
    $('#scan-submit-btn')?.classList.add('hidden');
    $('#retake-btn')?.classList.add('hidden');
  }


  // ── Result rendering ──────────────────────────────────────────────────
  function renderResult(scan) {
    const isCompliant = !scan.violations || scan.violations.length === 0;
    const fields = scan.classified_fields || {};
    const violations = scan.violations || [];
    const report = scan.compliance_report || {};

    // Status hero
    const heroEl = $('#result-hero');
    heroEl.className = `rounded-2xl p-6 mb-6 ${isCompliant ? 'bg-success/10 border border-success/20' : 'bg-danger/10 border border-danger/20'}`;
    heroEl.innerHTML = `
      <div class="flex items-center gap-3 mb-3">
        <span class="text-3xl">${isCompliant ? '✅' : '⚠️'}</span>
        <h2 class="font-display text-2xl font-black text-ink">
          ${isCompliant ? 'Label looks compliant' : 'Declarations need attention'}
        </h2>
      </div>
      <p class="text-ink-muted text-sm">
        ${isCompliant
          ? 'Required declarations reviewed in this scan were detected.'
          : `We found ${violations.length} item(s) that were missing, unclear, or could not be verified.`}
      </p>
      ${report.total_rules ? `
        <div class="flex gap-4 mt-4">
          <div class="bg-surface rounded-xl px-4 py-2 text-center">
            <div class="text-2xl font-black text-ink">${report.passed || 0}</div>
            <div class="text-xs text-ink-muted font-medium">Passed</div>
          </div>
          <div class="bg-surface rounded-xl px-4 py-2 text-center">
            <div class="text-2xl font-black ${report.failed > 0 ? 'text-danger' : 'text-ink'}">${report.failed || 0}</div>
            <div class="text-xs text-ink-muted font-medium">Issues</div>
          </div>
          <div class="bg-surface rounded-xl px-4 py-2 text-center">
            <div class="text-2xl font-black text-ink">${report.total_rules || 0}</div>
            <div class="text-xs text-ink-muted font-medium">Checked</div>
          </div>
        </div>
      ` : ''}
    `;

    // Classified fields
    const fieldsEl = $('#result-fields');
    const fieldEntries = [
      { key: 'mrp', label: 'MRP', icon: '💰' },
      { key: 'net_quantity', label: 'Net Quantity', icon: '⚖️' },
      { key: 'date_of_manufacture', label: 'Mfg / Pkg Date', icon: '📅' },
      { key: 'manufacturer_name', label: 'Manufacturer', icon: '🏭' },
      { key: 'manufacturer_address', label: 'Address', icon: '📍' },
      { key: 'consumer_care', label: 'Consumer Care', icon: '📞' },
    ];
    fieldsEl.innerHTML = fieldEntries.map((f) => {
      const val = fields[f.key];
      const found = val && val !== 'None';
      return `
        <div class="bg-surface rounded-xl p-4 border border-line">
          <div class="flex items-center gap-2 mb-1">
            <span>${f.icon}</span>
            <span class="text-xs font-semibold text-ink-muted uppercase tracking-wide">${f.label}</span>
          </div>
          <div class="text-sm font-semibold ${found ? 'text-ink' : 'text-ink-muted italic'}">
            ${found ? val : 'Not detected'}
          </div>
        </div>
      `;
    }).join('');

    // Violations
    const violationsEl = $('#result-violations');
    if (violations.length > 0) {
      violationsEl.innerHTML = `
        <h3 class="font-display text-lg font-bold text-ink mb-3">Cited Violations</h3>
        ${violations.map((v) => `
          <div class="bg-danger/5 border border-danger/20 rounded-xl p-4 mb-3">
            <div class="flex items-start gap-2">
              <span class="text-danger text-lg mt-0.5">⚠</span>
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <span class="status-pill bg-danger/15 text-danger text-xs">${v.severity || 'major'}</span>
                  ${v.rule_id ? `<span class="text-xs text-ink-muted font-mono">Rule ${v.rule_id.replace(/_/g, '.')}</span>` : ''}
                </div>
                <p class="text-sm text-ink font-medium mb-1">${v.reason || 'Rule check failed'}</p>
                <p class="text-xs text-ink-muted leading-relaxed">${v.citation || ''}</p>
              </div>
            </div>
          </div>
        `).join('')}
      `;
    } else {
      violationsEl.innerHTML = '';
    }
  }

  // ── Session summary ───────────────────────────────────────────────────
  async function loadSessionSummary() {
    if (!currentSession) {
      await restoreSession();
    }
    if (!currentSession) {
      showToast('Please start an inspection session first', 'info');
      showView('view-session');
      return;
    }
    try {
      const report = await API.getSessionReport(currentSession.id);
      const scans = report.scans;
      const total = report.total_scans;
      const compliant = report.compliant_scans;
      const nonCompliant = report.scans_with_violations;

      $('#summary-store').textContent = currentSession.store_name;
      $('#summary-location').textContent = currentSession.location || '—';
      $('#summary-total').textContent = total;
      $('#summary-compliant').textContent = compliant;
      $('#summary-violations').textContent = nonCompliant;
      $('#summary-rate').textContent = total > 0 ? Math.round((compliant / total) * 100) + '%' : '—';

      $('#summary-export-pdf').classList.remove('hidden');

      // Scan list
      const listEl = $('#summary-scan-list');
      listEl.innerHTML = scans.map((s) => {
        const ok = s.is_compliant;
        return `
          <div class="flex items-center justify-between bg-surface rounded-xl p-4 border border-line card-interactive cursor-pointer" data-scan-id="${s.id}">
            <div>
              <div class="text-sm font-semibold text-ink">Scan ${s.id.slice(0, 8)}…</div>
              <div class="text-xs text-ink-muted">${new Date(s.captured_at).toLocaleTimeString()}</div>
            </div>
            <span class="status-pill ${ok ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger'}">
              ${ok ? '✓ Compliant' : s.status === 'failed' ? '✕ Processing failed' : `⚠ ${s.violation_count} issue(s)`}
            </span>
          </div>
        `;
      }).join('');

      // Click handler for scan details
      listEl.querySelectorAll('[data-scan-id]').forEach((el) => {
        el.addEventListener('click', async () => {
          try {
            const scan = await API.getScan(el.dataset.scanId);
            renderResult(scan);
            showView('view-result');
          } catch (err) {
            showToast(err.message, 'error');
          }
        });
      });
    } catch (err) {
      showToast('Failed to load summary: ' + err.message, 'error');
    }
  }

  // ── Logout ────────────────────────────────────────────────────────────
  function initLogout() {
    $('#logout-btn')?.addEventListener('click', () => {
      API.logout();
      currentOfficer = null;
      setCurrentSession(null);
      showView('view-login');
      showToast('Logged out', 'info');
    });
  }


  // ── Bottom nav ────────────────────────────────────────────────────────
  function initBottomNav() {
    $$('.bottom-nav-item').forEach((item) => {
      item.addEventListener('click', () => {
        const viewId = item.dataset.view;
        if (viewId === 'view-summary') loadSessionSummary();
        if (viewId && (viewId !== 'view-login' || !API.isLoggedIn())) {
          showView(viewId);
        }
      });
    });
  }

  // ── Init ──────────────────────────────────────────────────────────────
  function init() {
    initLogin();
    initSession();
    initCapture();
    initLogout();
    initBottomNav();

    // Wire "Scan Another" and "View Summary" buttons on result screen
    $('#result-scan-another')?.addEventListener('click', () => {
      resetCapture();
      showView('view-capture');
    });
    $('#result-view-summary')?.addEventListener('click', () => {
      loadSessionSummary();
      showView('view-summary');
    });
    // Wire "Scan Next" from summary
    $('#summary-scan-next')?.addEventListener('click', () => {
      resetCapture();
      showView('view-capture');
    });
    $('#summary-export-pdf')?.addEventListener('click', async () => {
      if (!currentSession) return;
      try {
        const pdf = await API.downloadSessionReportPdf(currentSession.id);
        const url = URL.createObjectURL(pdf);
        const link = document.createElement('a');
        link.href = url;
        link.download = `labelbox-session-${currentSession.id.slice(0, 8)}.pdf`;
        link.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        showToast(err.message, 'error');
      }
    });

    // Check auth state on load
    if (API.isLoggedIn()) {
      API.getMe()
        .then((officer) => {
          currentOfficer = officer;
          onLoginSuccess();
        })
        .catch(() => showView('view-login'));
    } else {
      showView('view-login');
    }

    // Offline queue badge
    OfflineQueue.updateBadge();

    // Register service worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  }

  document.addEventListener('DOMContentLoaded', init);

  return { showView, showToast, renderResult, loadSessionSummary };
})();
