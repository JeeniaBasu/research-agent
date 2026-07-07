/**
 * main.js — ResearchMind AI Agent — Shared Frontend Utilities
 * Handles: theme toggle, toasts, modals, sidebar, global state, API helpers
 */

// =============================================================================
// Global State
// =============================================================================
const ResearchMind = {
  currentPapers: [],         // Papers from last search (available for all modes)
  bookmarks: [],             // Current bookmarks
  history: [],               // Research history
  currentCitations: {},      // Citations for citation modal
  currentReport: null,       // Current report for export
  settings: {
    citationStyle: 'APA',
    autoSearch: true,
  }
};

// =============================================================================
// Theme Management
// =============================================================================
const ThemeManager = {
  init() {
    const saved = localStorage.getItem('rm_theme') || 'light';
    this.set(saved);
  },

  set(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('rm_theme', theme);
    const icon = document.getElementById('themeIcon');
    if (icon) {
      icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }
  },

  toggle() {
    const current = document.documentElement.getAttribute('data-theme');
    this.set(current === 'dark' ? 'light' : 'dark');
  }
};

document.getElementById('themeToggle')?.addEventListener('click', () => ThemeManager.toggle());
ThemeManager.init();

// =============================================================================
// Toast Notifications
// =============================================================================
const Toast = {
  show(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const id = 'toast-' + Date.now();
    const iconMap = {
      success: 'check-circle-fill',
      error: 'x-circle-fill',
      warning: 'exclamation-triangle-fill',
      info: 'info-circle-fill'
    };
    const colorMap = {
      success: 'text-success',
      error: 'text-danger',
      warning: 'text-warning',
      info: 'text-primary'
    };

    const html = `
      <div id="${id}" class="toast align-items-center" role="alert">
        <div class="d-flex">
          <div class="toast-body d-flex align-items-center gap-2">
            <i class="bi bi-${iconMap[type] || 'info-circle-fill'} ${colorMap[type] || ''}"></i>
            ${escHtml(message)}
          </div>
          <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', html);
    const toastEl = document.getElementById(id);
    const bsToast = new bootstrap.Toast(toastEl, { delay: duration });
    bsToast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  },

  success: (msg) => Toast.show(msg, 'success'),
  error:   (msg) => Toast.show(msg, 'error', 6000),
  warning: (msg) => Toast.show(msg, 'warning'),
  info:    (msg) => Toast.show(msg, 'info'),
};

// =============================================================================
// API Helper
// =============================================================================
const API = {
  async post(endpoint, data) {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const json = await response.json();
    if (!response.ok || !json.success) {
      throw new Error(json.message || `API error ${response.status}`);
    }
    return json.data;
  },

  async get(endpoint) {
    const response = await fetch(endpoint);
    const json = await response.json();
    if (!response.ok || !json.success) {
      throw new Error(json.message || `API error ${response.status}`);
    }
    return json.data;
  },

  async delete(endpoint) {
    const response = await fetch(endpoint, { method: 'DELETE' });
    const json = await response.json();
    if (!response.ok || !json.success) {
      throw new Error(json.message || `API error ${response.status}`);
    }
    return json;
  },

  async downloadFile(endpoint, data, filename) {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const json = await response.json().catch(() => ({}));
      throw new Error(json.message || 'Download failed');
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
};

// =============================================================================
// Loading Overlay
// =============================================================================
const Loading = {
  show(text = 'Processing with IBM Granite...') {
    const overlay = document.getElementById('globalLoading');
    if (overlay) {
      overlay.querySelector('.loading-text').textContent = text;
      overlay.classList.remove('d-none');
    }
  },
  hide() {
    document.getElementById('globalLoading')?.classList.add('d-none');
  }
};

// =============================================================================
// Markdown Renderer
// =============================================================================
const MD = {
  render(text) {
    if (typeof marked === 'undefined') return escHtml(text);
    try {
      marked.setOptions({ breaks: true, gfm: true });
      return marked.parse(text || '');
    } catch (e) {
      return escHtml(text);
    }
  }
};

// =============================================================================
// Clipboard
// =============================================================================
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    Toast.success('Copied to clipboard!');
  } catch {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    Toast.success('Copied!');
  }
}

// =============================================================================
// HTML Escape
// =============================================================================
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

// =============================================================================
// Paper Card Renderer — shared across Chat and Search modes
// =============================================================================
function renderPaperCard(paper, index, options = {}) {
  const {
    showSummarize = true,
    showBookmark = true,
    showCompare = false,
    showCite = true,
    compact = false
  } = options;

  const sourceClass = {
    'arXiv': 'source-arxiv',
    'Semantic Scholar': 'source-semantic',
    'Crossref': 'source-crossref',
    'PubMed': 'source-pubmed',
  }[paper.source] || 'source-default';

  const authors = (paper.authors || []).slice(0, 3).join(', ') +
    (paper.authors?.length > 3 ? ' et al.' : '');

  const isBookmarked = ResearchMind.bookmarks.some(b => b.paper?.id === paper.id);

  return `
    <div class="paper-card" data-paper-idx="${index}" data-paper-id="${escHtml(paper.id || '')}">
      <div class="paper-title">
        ${paper.url
          ? `<a href="${escHtml(paper.url)}" target="_blank" rel="noopener">${escHtml(paper.title || 'Untitled')}</a>`
          : escHtml(paper.title || 'Untitled')
        }
      </div>
      <div class="paper-authors">${escHtml(authors || 'Unknown authors')}</div>
      <div class="paper-meta">
        <span class="source-badge ${sourceClass}">
          <i class="bi bi-journal me-1"></i>${escHtml(paper.source || 'Unknown')}
        </span>
        ${paper.year ? `<span class="text-muted small"><i class="bi bi-calendar me-1"></i>${paper.year}</span>` : ''}
        ${paper.citations != null ? `<span class="text-muted small"><i class="bi bi-diagram-2 me-1"></i>${paper.citations} citations</span>` : ''}
        ${paper.doi ? `<a href="https://doi.org/${escHtml(paper.doi)}" target="_blank" class="text-muted small"><i class="bi bi-link-45deg me-1"></i>DOI</a>` : ''}
      </div>
      ${paper.abstract ? `
        <div class="paper-abstract" id="abstract-${index}">
          ${escHtml(paper.abstract)}
        </div>
        <button class="btn btn-xs btn-link p-0 mb-2" onclick="toggleAbstract(${index})">
          <span id="abstract-toggle-${index}">Show more</span>
        </button>
      ` : ''}
      <div class="paper-actions">
        ${showSummarize ? `
          <button class="btn btn-xs btn-outline-primary" onclick="summarizePaper(${index})">
            <i class="bi bi-file-text me-1"></i>Summarize
          </button>` : ''}
        ${showBookmark ? `
          <button class="btn btn-xs ${isBookmarked ? 'btn-warning' : 'btn-outline-secondary'}" 
                  onclick="toggleBookmark(${index})" id="bookmark-btn-${index}">
            <i class="bi bi-bookmark${isBookmarked ? '-fill' : ''} me-1"></i>
            ${isBookmarked ? 'Bookmarked' : 'Bookmark'}
          </button>` : ''}
        ${showCite ? `
          <button class="btn btn-xs btn-outline-secondary" onclick="showCitation(${index})">
            <i class="bi bi-quote me-1"></i>Cite
          </button>` : ''}
        ${paper.url ? `
          <a class="btn btn-xs btn-outline-secondary" href="${escHtml(paper.url)}" target="_blank" rel="noopener">
            <i class="bi bi-box-arrow-up-right me-1"></i>View
          </a>` : ''}
      </div>
    </div>
  `;
}

function toggleAbstract(index) {
  const el = document.getElementById(`abstract-${index}`);
  const btn = document.getElementById(`abstract-toggle-${index}`);
  if (!el) return;
  el.classList.toggle('expanded');
  btn.textContent = el.classList.contains('expanded') ? 'Show less' : 'Show more';
}

// =============================================================================
// Bookmark Management
// =============================================================================
async function toggleBookmark(paperIndex) {
  const paper = ResearchMind.currentPapers[paperIndex];
  if (!paper) return;

  const existingIdx = ResearchMind.bookmarks.findIndex(b => b.paper?.id === paper.id);

  if (existingIdx >= 0) {
    // Remove bookmark
    const bookmark = ResearchMind.bookmarks[existingIdx];
    try {
      await API.delete(`/api/bookmarks/${bookmark.id}`);
      ResearchMind.bookmarks.splice(existingIdx, 1);
      updateBookmarkButton(paperIndex, false);
      Toast.info('Bookmark removed.');
      refreshBookmarkSidebar();
    } catch (e) {
      Toast.error('Could not remove bookmark: ' + e.message);
    }
  } else {
    // Add bookmark
    try {
      const data = await API.post('/api/bookmarks', { paper });
      ResearchMind.bookmarks.push(data.bookmark);
      updateBookmarkButton(paperIndex, true);
      Toast.success('Paper bookmarked!');
      refreshBookmarkSidebar();
    } catch (e) {
      if (e.message.includes('already bookmarked')) {
        Toast.warning('Paper already bookmarked.');
      } else {
        Toast.error('Could not bookmark: ' + e.message);
      }
    }
  }
}

function updateBookmarkButton(index, isBookmarked) {
  const btn = document.getElementById(`bookmark-btn-${index}`);
  if (!btn) return;
  btn.className = `btn btn-xs ${isBookmarked ? 'btn-warning' : 'btn-outline-secondary'}`;
  btn.innerHTML = `<i class="bi bi-bookmark${isBookmarked ? '-fill' : ''} me-1"></i>${isBookmarked ? 'Bookmarked' : 'Bookmark'}`;
}

function refreshBookmarkSidebar() {
  const list = document.getElementById('bookmarkList');
  if (!list) return;

  if (ResearchMind.bookmarks.length === 0) {
    list.innerHTML = `
      <div class="sidebar-empty text-center py-3">
        <i class="bi bi-bookmark opacity-25 fs-2"></i>
        <p class="small text-muted mt-2">No bookmarks yet.</p>
      </div>`;
    return;
  }

  list.innerHTML = ResearchMind.bookmarks.map(bm => `
    <div class="sidebar-item">
      <div class="sidebar-item-query">${escHtml(bm.paper?.title?.slice(0, 50) || 'Unknown')}...</div>
      <div class="sidebar-item-meta">${escHtml(bm.paper?.year || 'n.d.')} · ${escHtml(bm.paper?.source || '')}</div>
    </div>
  `).join('');
}

// =============================================================================
// Citation Modal
// =============================================================================
function showCitation(paperIndex) {
  const paper = ResearchMind.currentPapers[paperIndex];
  if (!paper) return;

  ResearchMind.currentCitations = {
    APA: 'Loading...',
    IEEE: 'Loading...',
    MLA: 'Loading...',
  };

  const modal = new bootstrap.Modal(document.getElementById('citationModal'));
  modal.show();

  API.post('/api/citations', { papers: [paper], style: 'APA' })
    .then(data => {
      const title = paper.title || 'Unknown';
      const citeData = data.citations[title];
      if (citeData) {
        ResearchMind.currentCitations = citeData.all_styles || {};
        updateCitationDisplay('APA');
      }
    })
    .catch(e => Toast.error('Citation error: ' + e.message));
}

function updateCitationDisplay(style) {
  const content = document.getElementById('citationContent');
  if (content) {
    content.textContent = ResearchMind.currentCitations[style] || 'Not available';
  }
}

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-style]');
  if (!btn) return;
  document.querySelectorAll('#citationTabs .nav-link').forEach(l => l.classList.remove('active'));
  btn.classList.add('active');
  updateCitationDisplay(btn.dataset.style);
});

document.getElementById('copyCitationBtn')?.addEventListener('click', () => {
  const style = document.querySelector('#citationTabs .nav-link.active')?.dataset.style || 'APA';
  copyToClipboard(ResearchMind.currentCitations[style] || '');
});

// =============================================================================
// Paper Summarizer (opens in chat)
// =============================================================================
async function summarizePaper(paperIndex) {
  const paper = ResearchMind.currentPapers[paperIndex];
  if (!paper) return;

  // Switch to chat mode if not already there
  const chatTab = document.querySelector('[data-mode="chat"]');
  if (chatTab && !chatTab.classList.contains('active')) {
    chatTab.click();
  }

  // If chat module is loaded, use it
  if (typeof ChatModule !== 'undefined') {
    await ChatModule.summarizePaper(paper);
  } else {
    Toast.info('Switch to the Chat tab to summarize this paper.');
  }
}

// =============================================================================
// Export Modal
// =============================================================================
document.getElementById('exportBtn')?.addEventListener('click', () => {
  if (!ResearchMind.currentReport) {
    Toast.warning('No report to export. Generate a literature review or report section first.');
    return;
  }
  new bootstrap.Modal(document.getElementById('exportModal')).show();
});

document.getElementById('exportPdfBtn')?.addEventListener('click', async () => {
  if (!ResearchMind.currentReport) return;
  Loading.show('Generating PDF...');
  try {
    await API.downloadFile(
      '/api/export/pdf',
      { report: ResearchMind.currentReport },
      `research_report_${Date.now()}.pdf`
    );
    Toast.success('PDF downloaded!');
  } catch (e) {
    Toast.error('PDF export failed: ' + e.message);
  } finally {
    Loading.hide();
    bootstrap.Modal.getInstance(document.getElementById('exportModal'))?.hide();
  }
});

document.getElementById('exportDocxBtn')?.addEventListener('click', async () => {
  if (!ResearchMind.currentReport) return;
  Loading.show('Generating DOCX...');
  try {
    await API.downloadFile(
      '/api/export/docx',
      { report: ResearchMind.currentReport },
      `research_report_${Date.now()}.docx`
    );
    Toast.success('DOCX downloaded!');
  } catch (e) {
    Toast.error('DOCX export failed: ' + e.message);
  } finally {
    Loading.hide();
    bootstrap.Modal.getInstance(document.getElementById('exportModal'))?.hide();
  }
});

// =============================================================================
// Sidebar Toggle (mobile)
// =============================================================================
document.getElementById('sidebarToggle')?.addEventListener('click', () => {
  document.getElementById('sidebar')?.classList.toggle('open');
});

// Close sidebar on backdrop click (mobile)
document.addEventListener('click', e => {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('sidebarToggle');
  if (sidebar && !sidebar.contains(e.target) && !toggle?.contains(e.target)) {
    sidebar.classList.remove('open');
  }
});

// =============================================================================
// History Sidebar
// =============================================================================
function refreshHistorySidebar(history) {
  const list = document.getElementById('historyList');
  if (!list) return;

  if (!history || history.length === 0) {
    list.innerHTML = `
      <div class="sidebar-empty text-center py-4">
        <i class="bi bi-journal-text opacity-25 fs-2"></i>
        <p class="small text-muted mt-2">No history yet.<br>Start researching!</p>
      </div>`;
    return;
  }

  list.innerHTML = history.slice(0, 30).map(entry => `
    <div class="sidebar-item" onclick="loadHistoryEntry(${escHtml(JSON.stringify(entry.query))})">
      <div class="sidebar-item-query">${escHtml(entry.query?.slice(0, 48) || 'Unknown')}...</div>
      <div class="sidebar-item-meta">
        <span class="type-badge-${escHtml(entry.type)}">${escHtml(entry.type?.replace('_', ' ') || '')}</span>
        <span class="ms-2">${entry.timestamp?.slice(0, 10) || ''}</span>
      </div>
    </div>
  `).join('');
}

function loadHistoryEntry(query) {
  const input = document.getElementById('chatInput');
  if (input) {
    input.value = query;
    input.focus();
    // Switch to chat mode
    document.querySelector('[data-mode="chat"]')?.click();
  }
}

// History search filter
document.getElementById('historySearch')?.addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('#historyList .sidebar-item').forEach(item => {
    const text = item.querySelector('.sidebar-item-query')?.textContent?.toLowerCase() || '';
    item.style.display = text.includes(q) ? '' : 'none';
  });
});

// Clear history
document.getElementById('clearHistoryBtn')?.addEventListener('click', async () => {
  if (!confirm('Clear all research history?')) return;
  const history = await API.get('/api/history').catch(() => ({ history: [] }));
  for (const entry of (history.history || [])) {
    await API.delete(`/api/history/${entry.id}`).catch(() => {});
  }
  ResearchMind.history = [];
  refreshHistorySidebar([]);
  Toast.success('History cleared.');
});

// =============================================================================
// Load initial data
// =============================================================================
(async () => {
  try {
    const [hData, bData] = await Promise.all([
      API.get('/api/history?limit=30'),
      API.get('/api/bookmarks'),
    ]);
    ResearchMind.history = hData.history || [];
    ResearchMind.bookmarks = bData.bookmarks || [];
    refreshHistorySidebar(ResearchMind.history);
    refreshBookmarkSidebar();
  } catch (e) {
    console.warn('Could not load initial data:', e.message);
  }
})();
