/**
 * chat.js — ResearchMind AI Agent — Chat Interface & Mode Logic
 * Handles: Chat, Search, Literature Review, Report, Citations tabs
 */

// =============================================================================
// Mode Tab Switching
// =============================================================================
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const mode = btn.dataset.mode;
    if (!mode) return;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Show correct panel
    document.querySelectorAll('.mode-panel').forEach(panel => panel.classList.remove('active'));
    const targetPanel = document.getElementById(`mode-${mode}`);
    if (targetPanel) targetPanel.classList.add('active');

    // Special handling
    if (mode === 'citations') refreshCitationWorkspace();
  });
});

// Handle URL param for initial mode
const urlParams = new URLSearchParams(window.location.search);
const initMode = urlParams.get('mode');
if (initMode) {
  document.querySelector(`[data-mode="${initMode}"]`)?.click();
}

// =============================================================================
// Chat Module
// =============================================================================
const ChatModule = {
  conversationHistory: [],
  isLoading: false,

  // ------------------------------------------------------------------
  init() {
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');

    if (input) {
      // Auto-resize textarea
      input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 160) + 'px';
      });

      // Enter to send, Shift+Enter for new line
      input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.send();
        }
      });
    }

    sendBtn?.addEventListener('click', () => this.send());

    document.getElementById('clearChatBtn')?.addEventListener('click', () => this.clear());

    // Suggestion chips
    document.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.dataset.prompt;
        if (prompt) {
          if (input) { input.value = prompt; input.focus(); }
          this.send();
        }
      });
    });

    // Auto-search toggle
    const autoToggle = document.getElementById('autoSearchToggle');
    if (autoToggle) {
      autoToggle.addEventListener('change', () => {
        ResearchMind.settings.autoSearch = autoToggle.checked;
      });
    }

    // Clear papers strip
    document.getElementById('clearPapersBtn')?.addEventListener('click', () => {
      ResearchMind.currentPapers = [];
      this.updatePapersStrip([]);
    });
  },

  // ------------------------------------------------------------------
  async send() {
    if (this.isLoading) return;

    const input = document.getElementById('chatInput');
    const message = input?.value?.trim();
    if (!message) return;

    // Clear input
    input.value = '';
    input.style.height = 'auto';

    // Hide welcome, show message
    document.getElementById('chatWelcome')?.remove();

    // Add user message
    this.appendMessage('user', message);
    this.conversationHistory.push({ role: 'user', content: message });

    // Show typing indicator
    this.setLoading(true);

    try {
      const data = await API.post('/api/chat', {
        message,
        history: this.conversationHistory.slice(-8),
        auto_search: ResearchMind.settings.autoSearch,
      });

      const response = data.response;
      this.appendMessage('agent', response);
      this.conversationHistory.push({ role: 'assistant', content: response });

      // Update papers strip
      if (data.papers?.length) {
        ResearchMind.currentPapers = data.papers;
        this.updatePapersStrip(data.papers);
      }

      if (data.rag_grounded) {
        Toast.info(`Response grounded in ${data.papers_used} retrieved papers.`);
      }

      // Update history sidebar
      const histData = await API.get('/api/history?limit=30').catch(() => ({ history: [] }));
      ResearchMind.history = histData.history || [];
      refreshHistorySidebar(ResearchMind.history);

    } catch (e) {
      this.appendMessage('agent', `⚠️ **Error:** ${e.message}\n\nPlease check your IBM Watsonx.ai configuration.`, true);
    } finally {
      this.setLoading(false);
    }
  },

  // ------------------------------------------------------------------
  appendMessage(role, content, isError = false) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    const msgId = 'msg-' + Date.now();
    const isUser = role === 'user';
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const html = `
      <div class="chat-message" id="${msgId}">
        <div class="msg-avatar ${isUser ? 'user' : 'agent'}">
          ${isUser ? '<i class="bi bi-person-fill"></i>' : '<i class="bi bi-cpu-fill"></i>'}
        </div>
        <div class="msg-body">
          <div class="msg-header">
            <span class="msg-name">${isUser ? 'You' : 'ResearchMind'}</span>
            <span class="msg-time">${time}</span>
            
          </div>
          <div class="msg-content ${isUser ? 'user-content' : ''} ${isError ? 'border-danger' : ''}">
            ${isUser ? escHtml(content) : MD.render(content)}
          </div>
          ${!isUser ? `
            <div class="msg-actions">
              <button class="msg-action-btn" onclick="copyToClipboard(${JSON.stringify(content)})">
                <i class="bi bi-clipboard me-1"></i>Copy
              </button>
            </div>
          ` : ''}
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', html);
    this.scrollToBottom();
  },

  // Helper to avoid template literal issue — set rag flag context
  _appendMessage(role, content, rag = false) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    const msgId = 'msg-' + Date.now();
    const isUser = role === 'user';
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const div = document.createElement('div');
    div.className = 'chat-message';
    div.id = msgId;
    div.innerHTML = `
      <div class="msg-avatar ${isUser ? 'user' : 'agent'}">
        ${isUser ? '<i class="bi bi-person-fill"></i>' : '<i class="bi bi-cpu-fill"></i>'}
      </div>
      <div class="msg-body">
        <div class="msg-header">
          <span class="msg-name">${isUser ? 'You' : 'ResearchMind'}</span>
          <span class="msg-time">${time}</span>
          ${rag ? '<span class="badge bg-success bg-opacity-10 text-success ms-1" style="font-size:10px"><i class="bi bi-shield-check me-1"></i>RAG</span>' : ''}
        </div>
        <div class="msg-content ${isUser ? 'user-content' : ''}">
          ${isUser ? escHtml(content) : MD.render(content)}
        </div>
        ${!isUser ? `
          <div class="msg-actions">
            <button class="msg-action-btn copy-btn">
              <i class="bi bi-clipboard me-1"></i>Copy
            </button>
          </div>
        ` : ''}
      </div>
    `;

    div.querySelector('.copy-btn')?.addEventListener('click', () => copyToClipboard(content));
    container.appendChild(div);
    this.scrollToBottom();
  },

  // Override the broken appendMessage above
  appendMessage(role, content, isError = false) {
    this._appendMessage(role, content, false);
  },

  // ------------------------------------------------------------------
  async summarizePaper(paper) {
    document.getElementById('chatWelcome')?.remove();
    this._appendMessage('user', `Summarize this paper: "${paper.title}"`);
    this.setLoading(true);

    try {
      const data = await API.post('/api/summarize', { paper });
      let response = data.summary;
      response += `\n\n---\n**📚 Citation (APA):** ${data.citations?.APA || 'N/A'}`;
      this._appendMessage('agent', response);
    } catch (e) {
      this._appendMessage('agent', `⚠️ Summarization failed: ${e.message}`);
    } finally {
      this.setLoading(false);
    }
  },

  // ------------------------------------------------------------------
  clear() {
    document.getElementById('chatMessages').innerHTML = '';
    this.conversationHistory = [];
    // Restore welcome
    const container = document.getElementById('chatContainer');
    if (container && !document.getElementById('chatWelcome')) {
      container.insertAdjacentHTML('afterbegin', `
        <div class="chat-welcome" id="chatWelcome">
          <div class="welcome-icon"><i class="bi bi-cpu-fill"></i></div>
          <h2 class="welcome-title">Chat cleared</h2>
          <p class="welcome-subtitle">Start a new research session.</p>
        </div>
      `);
    }
    Toast.info('Chat cleared.');
  },

  // ------------------------------------------------------------------
  setLoading(state) {
    this.isLoading = state;
    const typing = document.getElementById('chatTyping');
    const sendBtn = document.getElementById('sendBtn');
    if (typing) typing.classList.toggle('d-none', !state);
    if (sendBtn) sendBtn.disabled = state;
    if (state) this.scrollToBottom();
  },

  // ------------------------------------------------------------------
  scrollToBottom() {
    const container = document.getElementById('chatContainer');
    if (container) {
      setTimeout(() => {
        container.scrollTop = container.scrollHeight;
      }, 50);
    }
  },

  // ------------------------------------------------------------------
  updatePapersStrip(papers) {
    const strip = document.getElementById('papersStrip');
    const list = document.getElementById('papersList');
    const count = document.getElementById('papersCount');

    if (!papers?.length) {
      strip?.classList.add('d-none');
      return;
    }

    strip?.classList.remove('d-none');
    if (count) count.textContent = papers.length;

    if (list) {
      list.innerHTML = papers.map((p, i) => `
        <div class="paper-chip" onclick="summarizePaper(${i})" title="${escHtml(p.title || '')}">
          <div class="paper-chip-title">${escHtml(p.title?.slice(0, 45) || 'Unknown')}...</div>
          <div class="paper-chip-meta">${escHtml(p.year || 'n.d.')} · ${escHtml(p.source || '')}</div>
        </div>
      `).join('');
    }
  }
};

// =============================================================================
// Search Module
// =============================================================================
const SearchModule = {
  init() {
    document.getElementById('searchBtn')?.addEventListener('click', () => this.search());
    document.getElementById('searchQuery')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') this.search();
    });
  },

  async search() {
    const query = document.getElementById('searchQuery')?.value?.trim();
    if (!query) { Toast.warning('Please enter a search query.'); return; }

    const maxResults = parseInt(document.getElementById('searchLimit')?.value || '10');

    // Get selected databases
    const databases = Array.from(
      document.querySelectorAll('.filter-chip input:checked')
    ).map(cb => cb.value);

    if (databases.length === 0) {
      Toast.warning('Select at least one database.');
      return;
    }

    const loading = document.getElementById('searchLoading');
    const results = document.getElementById('searchResults');

    loading?.classList.remove('d-none');
    if (results) results.innerHTML = '';

    try {
      const data = await API.post('/api/search', { query, max_results: maxResults, databases });
      ResearchMind.currentPapers = data.papers || [];
      this.renderResults(data);
      ChatModule.updatePapersStrip(data.papers);

      // Update history
      const hData = await API.get('/api/history?limit=30').catch(() => ({ history: [] }));
      ResearchMind.history = hData.history || [];
      refreshHistorySidebar(ResearchMind.history);

    } catch (e) {
      Toast.error('Search failed: ' + e.message);
    } finally {
      loading?.classList.add('d-none');
    }
  },

  renderResults(data) {
    const container = document.getElementById('searchResults');
    if (!container) return;

    if (!data.papers?.length) {
      container.innerHTML = `
        <div class="text-center py-5 text-muted">
          <i class="bi bi-search fs-1 opacity-25"></i>
          <p class="mt-3">No papers found for "<strong>${escHtml(data.query)}</strong>".<br>Try different keywords or broader search terms.</p>
        </div>`;
      return;
    }

    const header = `
      <div class="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h6 class="mb-0 fw-bold">
            <i class="bi bi-journals me-2 text-primary"></i>
            Found <strong>${data.count}</strong> papers for "<em>${escHtml(data.query)}</em>"
          </h6>
        </div>
        <div class="d-flex gap-2">
          <button class="btn btn-sm btn-outline-primary" onclick="SearchModule.compareAll()">
            <i class="bi bi-bar-chart me-1"></i>Compare All
          </button>
        </div>
      </div>
    `;

    const cards = data.papers.map((paper, i) => renderPaperCard(paper, i)).join('');
    container.innerHTML = header + cards;
  },

  async compareAll() {
    if (ResearchMind.currentPapers.length < 2) {
      Toast.warning('Need at least 2 papers to compare.');
      return;
    }
    Loading.show('Comparing papers with IBM Granite...');
    try {
      const data = await API.post('/api/compare', { papers: ResearchMind.currentPapers });
      // Display in chat
      document.querySelector('[data-mode="chat"]')?.click();
      document.getElementById('chatWelcome')?.remove();
      ChatModule._appendMessage('agent', `## Paper Comparison\n\n${data.comparison}`);
    } catch (e) {
      Toast.error('Comparison failed: ' + e.message);
    } finally {
      Loading.hide();
    }
  }
};

// =============================================================================
// Literature Review Module
// =============================================================================
const ReviewModule = {
  init() {
    document.getElementById('generateReviewBtn')?.addEventListener('click', () => this.generate());
  },

  async generate() {
    const topic = document.getElementById('reviewTopic')?.value?.trim();
    if (!topic) { Toast.warning('Please enter a research topic.'); return; }

    const paperCount = parseInt(document.getElementById('reviewPaperCount')?.value || '12');
    const citationStyle = document.getElementById('reviewCitationStyle')?.value || 'APA';

    const loading = document.getElementById('reviewLoading');
    const result = document.getElementById('reviewResult');
    const btn = document.getElementById('generateReviewBtn');

    loading?.classList.remove('d-none');
    if (result) result.innerHTML = '';
    if (btn) btn.disabled = true;

    try {
      const data = await API.post('/api/literature-review', {
        topic,
        papers: ResearchMind.currentPapers,
        auto_search: true,
      });

      // Store for export
      ResearchMind.currentReport = {
        title: `Literature Review: ${topic}`,
        topic,
        sections: [
          { heading: 'Literature Review', content: data.review },
          { heading: 'Research Gaps & Future Directions', content: data.research_gaps },
        ],
        references: data.bibliography?.split('\n').filter(l => l.trim()),
        generated_at: new Date().toLocaleString(),
      };

      // Update current papers
      if (data.papers?.length) {
        ResearchMind.currentPapers = data.papers;
        ChatModule.updatePapersStrip(data.papers);
      }

      result.innerHTML = this.renderReviewOutput(data, topic, citationStyle);

    } catch (e) {
      if (result) result.innerHTML = `<div class="alert alert-danger">Error: ${escHtml(e.message)}</div>`;
      Toast.error('Literature review failed: ' + e.message);
    } finally {
      loading?.classList.add('d-none');
      if (btn) btn.disabled = false;
    }
  },

  renderReviewOutput(data, topic, citationStyle) {
    return `
      <div class="review-output mb-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="fw-bold mb-0">
            <i class="bi bi-journal-richtext me-2 text-primary"></i>
            Literature Review: ${escHtml(topic)}
          </h5>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary" onclick="copyToClipboard(${JSON.stringify(data.review)})">
              <i class="bi bi-clipboard me-1"></i>Copy
            </button>
            <button class="btn btn-sm btn-primary" onclick="document.getElementById('exportBtn').click()">
              <i class="bi bi-download me-1"></i>Export
            </button>
          </div>
        </div>
        <div class="review-body">
          ${MD.render(data.review)}
        </div>
      </div>

      <div class="review-output mb-4">
        <h5 class="fw-bold mb-3">
          <i class="bi bi-lightbulb me-2 text-warning"></i>Research Gaps & Future Directions
        </h5>
        ${MD.render(data.research_gaps || '')}
      </div>

      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="fw-bold mb-0"><i class="bi bi-list-ol me-2 text-primary"></i>Bibliography (${escHtml(citationStyle)})</h6>
          <button class="btn btn-sm btn-outline-secondary" onclick="copyToClipboard(${JSON.stringify(data.bibliography)})">
            <i class="bi bi-clipboard me-1"></i>Copy
          </button>
        </div>
        <pre class="bibliography-pre">${escHtml(data.bibliography || '')}</pre>
      </div>
    `;
  }
};

// =============================================================================
// Report Module
// =============================================================================
const ReportModule = {
  selectedSection: 'abstract',

  init() {
    // Section grid buttons
    document.querySelectorAll('.section-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.section-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.selectedSection = btn.dataset.section;
      });
    });

    document.getElementById('generateSectionBtn')?.addEventListener('click', () => this.generate());
  },

  async generate() {
    const topic = document.getElementById('reportTopic')?.value?.trim();
    if (!topic) { Toast.warning('Please enter a research topic.'); return; }

    const notes = document.getElementById('reportNotes')?.value?.trim() || '';
    const loading = document.getElementById('reportLoading');
    const result = document.getElementById('reportResult');
    const btn = document.getElementById('generateSectionBtn');

    loading?.classList.remove('d-none');
    if (result) result.innerHTML = '';
    if (btn) btn.disabled = true;

    try {
      const data = await API.post('/api/report-section', {
        section: this.selectedSection,
        topic,
        notes,
        papers: ResearchMind.currentPapers,
      });

      // Build/extend current report for export
      if (!ResearchMind.currentReport) {
        ResearchMind.currentReport = {
          title: `Research Report: ${topic}`,
          topic,
          sections: [],
          references: [],
          generated_at: new Date().toLocaleString(),
        };
      }

      // Add/replace section
      const sIdx = ResearchMind.currentReport.sections.findIndex(
        s => s.heading.toLowerCase() === data.section.replace('_', ' ').toLowerCase()
      );
      const newSection = {
        heading: data.section.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        content: data.content,
      };
      if (sIdx >= 0) {
        ResearchMind.currentReport.sections[sIdx] = newSection;
      } else {
        ResearchMind.currentReport.sections.push(newSection);
      }

      result.innerHTML = `
        <div class="review-output">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h5 class="fw-bold text-capitalize mb-0">
              <i class="bi bi-pencil me-2 text-primary"></i>
              ${escHtml(data.section.replace('_', ' '))}
            </h5>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-outline-primary" onclick="copyToClipboard(${JSON.stringify(data.content)})">
                <i class="bi bi-clipboard me-1"></i>Copy
              </button>
              <button class="btn btn-sm btn-primary" onclick="document.getElementById('exportBtn').click()">
                <i class="bi bi-download me-1"></i>Export
              </button>
            </div>
          </div>
          <div>${MD.render(data.content)}</div>
        </div>
      `;

    } catch (e) {
      if (result) result.innerHTML = `<div class="alert alert-danger">Error: ${escHtml(e.message)}</div>`;
      Toast.error('Draft failed: ' + e.message);
    } finally {
      loading?.classList.add('d-none');
      if (btn) btn.disabled = false;
    }
  }
};

// =============================================================================
// Citations Module
// =============================================================================
function refreshCitationWorkspace() {
  const workspace = document.getElementById('citationWorkspace');
  if (!workspace) return;

  const bookmarks = ResearchMind.bookmarks;

  if (!bookmarks.length) {
    workspace.innerHTML = `
      <div class="text-center py-4 text-muted">
        <i class="bi bi-bookmark fs-2 opacity-25"></i>
        <p class="mt-2">Bookmark papers from the Search tab to manage their citations here.</p>
      </div>`;
    return;
  }

  workspace.innerHTML = bookmarks.map(bm => {
    const p = bm.paper;
    return `
      <div class="paper-card mb-2">
        <div class="paper-title">${escHtml(p.title || 'Unknown')}</div>
        <div class="paper-authors">${escHtml((p.authors || []).slice(0, 3).join(', '))}${p.authors?.length > 3 ? ' et al.' : ''}</div>
        <div class="paper-meta">
          <span class="source-badge source-${(p.source || '').toLowerCase().replace(' ', '-')}">${escHtml(p.source || '')}</span>
          <span class="text-muted small">${p.year || 'n.d.'}</span>
        </div>
        <div class="mt-2">
          ${['APA', 'IEEE', 'MLA'].map(style => `
            <div class="d-flex align-items-start gap-2 mb-1">
              <span class="badge bg-primary bg-opacity-10 text-primary" style="min-width:40px;font-size:10px">${style}</span>
              <code class="small text-muted" style="font-size:11px">${escHtml(bm.citations?.[style] || 'Generating...')}</code>
            </div>
          `).join('')}
        </div>
        <div class="mt-2">
          <button class="btn btn-xs btn-outline-secondary" onclick="copyToClipboard(${JSON.stringify(bm.citations?.APA || '')})">
            <i class="bi bi-clipboard me-1"></i>Copy APA
          </button>
        </div>
      </div>
    `;
  }).join('');
}

document.getElementById('generateAllCitationsBtn')?.addEventListener('click', async () => {
  const books = ResearchMind.bookmarks;
  if (!books.length) { Toast.warning('No bookmarked papers.'); return; }

  const style = document.getElementById('citationStyleSelect')?.value || 'APA';
  const output = document.getElementById('bibliographyOutput');
  const textEl = document.getElementById('bibliographyText');

  try {
    const data = await API.post('/api/citations', {
      papers: books.map(b => b.paper),
      style,
    });

    if (textEl) textEl.textContent = data.bibliography || '';
    output?.classList.remove('d-none');
    Toast.success(`Bibliography generated in ${style} format.`);

  } catch (e) {
    Toast.error('Citation generation failed: ' + e.message);
  }
});

document.getElementById('copyBibBtn')?.addEventListener('click', () => {
  const text = document.getElementById('bibliographyText')?.textContent || '';
  copyToClipboard(text);
});

// =============================================================================
// Dashboard History Actions
// =============================================================================
document.querySelectorAll('.history-rerun').forEach(btn => {
  btn.addEventListener('click', e => {
    e.stopPropagation();
    const query = btn.dataset.query;
    if (query) window.location.href = `/?q=${encodeURIComponent(query)}`;
  });
});

document.querySelectorAll('.history-delete').forEach(btn => {
  btn.addEventListener('click', async e => {
    e.stopPropagation();
    const id = btn.dataset.id;
    try {
      await API.delete(`/api/history/${id}`);
      btn.closest('.history-item')?.remove();
      Toast.success('Entry deleted.');
    } catch (err) {
      Toast.error('Could not delete: ' + err.message);
    }
  });
});

// History filter
document.getElementById('historyFilter')?.addEventListener('change', e => {
  const type = e.target.value;
  document.querySelectorAll('.history-item').forEach(item => {
    item.style.display = (!type || item.dataset.type === type) ? '' : 'none';
  });
});

// Handle URL query param for pre-filling chat
const qParam = urlParams.get('q');
if (qParam) {
  const input = document.getElementById('chatInput');
  if (input) { input.value = qParam; }
}

// =============================================================================
// Initialise all modules
// =============================================================================
ChatModule.init();
SearchModule.init();
ReviewModule.init();
ReportModule.init();
