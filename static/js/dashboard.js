/**
 * dashboard.js — ResearchMind AI Agent — Dashboard Analytics & Interactivity
 * Handles: activity chart, history filtering, bookmark management
 */

// =============================================================================
// Activity Chart (pure SVG — no external chart library required)
// =============================================================================
(function initActivityChart() {
  const canvas = document.getElementById('activityChart');
  if (!canvas) return;

  // Collect counts from the visible history items
  const items = document.querySelectorAll('.history-item');
  const dayCounts = {};
  const today = new Date();

  // Generate last 7 days
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    dayCounts[key] = { search: 0, chat: 0, review: 0 };
  }

  items.forEach(item => {
    const meta = item.querySelector('.history-meta');
    const timeEl = meta?.querySelector('.text-muted.small');
    const typeEl = meta?.querySelector('[class*="type-badge-"]');
    if (!timeEl || !typeEl) return;

    const dateStr = timeEl.textContent.trim().slice(0, 10);
    if (dayCounts[dateStr]) {
      const type = Array.from(typeEl.classList)
        .find(c => c.startsWith('type-badge-'))
        ?.replace('type-badge-', '');
      if (type === 'search') dayCounts[dateStr].search++;
      else if (type === 'chat') dayCounts[dateStr].chat++;
      else if (type === 'literature') dayCounts[dateStr].review++;
    }
  });

  const days = Object.keys(dayCounts).sort();
  const searches = days.map(d => dayCounts[d].search);
  const chats = days.map(d => dayCounts[d].chat);
  const reviews = days.map(d => dayCounts[d].review);

  const maxVal = Math.max(...searches, ...chats, ...reviews, 1);

  // Build SVG bar chart
  const svgNS = 'http://www.w3.org/2000/svg';
  const W = canvas.clientWidth || 600;
  const H = 100;
  const padding = { left: 30, right: 10, top: 10, bottom: 20 };
  const chartW = W - padding.left - padding.right;
  const chartH = H - padding.top - padding.bottom;
  const n = days.length;
  const groupW = chartW / n;
  const barW = Math.min(groupW / 4, 14);
  const gap = 2;

  const colors = { search: '#3b82f6', chat: '#7c3aed', review: '#10b981' };
  const series = [searches, chats, reviews];
  const seriesColors = [colors.search, colors.chat, colors.review];

  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  // Y gridlines
  for (let i = 0; i <= 4; i++) {
    const y = padding.top + chartH - (i / 4) * chartH;
    const line = document.createElementNS(svgNS, 'line');
    line.setAttribute('x1', padding.left);
    line.setAttribute('x2', W - padding.right);
    line.setAttribute('y1', y);
    line.setAttribute('y2', y);
    line.setAttribute('stroke', getComputedStyle(document.documentElement)
      .getPropertyValue('--border-color').trim() || '#e2e8f0');
    line.setAttribute('stroke-width', '0.5');
    svg.appendChild(line);
  }

  // Bars
  days.forEach((day, i) => {
    const groupX = padding.left + i * groupW + groupW / 2;
    series.forEach((s, si) => {
      const val = s[i];
      const barH = (val / maxVal) * chartH;
      const x = groupX + (si - 1) * (barW + gap);
      const y = padding.top + chartH - barH;

      const rect = document.createElementNS(svgNS, 'rect');
      rect.setAttribute('x', x);
      rect.setAttribute('y', y);
      rect.setAttribute('width', barW);
      rect.setAttribute('height', Math.max(barH, 1));
      rect.setAttribute('fill', seriesColors[si]);
      rect.setAttribute('rx', 2);
      rect.setAttribute('opacity', '0.85');
      svg.appendChild(rect);
    });

    // Day label
    const label = document.createElementNS(svgNS, 'text');
    label.setAttribute('x', groupX);
    label.setAttribute('y', H - 3);
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('font-size', '9');
    label.setAttribute('fill', '#94a3b8');
    const d = new Date(day + 'T00:00:00');
    label.textContent = d.toLocaleDateString(undefined, { weekday: 'short' });
    svg.appendChild(label);
  });

  canvas.appendChild(svg);
})();

// =============================================================================
// Clear History Button
// =============================================================================
document.getElementById('clearAllHistoryBtn')?.addEventListener('click', async () => {
  if (!confirm('Clear all research history? This cannot be undone.')) return;

  const rows = document.querySelectorAll('.history-item');
  let cleared = 0;
  for (const row of rows) {
    const id = row.dataset.id;
    if (id) {
      try {
        await fetch(`/api/history/${id}`, { method: 'DELETE' });
        row.remove();
        cleared++;
      } catch {}
    }
  }

  if (cleared > 0) {
    Toast.success(`${cleared} history entries cleared.`);
    // Show empty state
    const list = document.getElementById('dashHistoryList');
    if (list && !list.querySelector('.history-item')) {
      list.innerHTML = `
        <div class="text-center py-5 text-muted">
          <i class="bi bi-clock-history fs-1 opacity-25"></i>
          <p class="mt-2">History cleared.</p>
          <a href="/" class="btn btn-sm btn-primary mt-2">
            <i class="bi bi-chat-dots me-1"></i>Start Researching
          </a>
        </div>
      `;
    }
  }
});

// =============================================================================
// History Filter
// =============================================================================
document.getElementById('historyFilter')?.addEventListener('change', e => {
  const type = e.target.value;
  document.querySelectorAll('.history-item').forEach(item => {
    item.style.display = (!type || item.dataset.type === type) ? '' : 'none';
  });
});

// =============================================================================
// Update stats from live API
// =============================================================================
(async () => {
  try {
    const status = await fetch('/api/status').then(r => r.json());
    if (status.data) {
      const d = status.data;
      const el = document.getElementById('totalSearches');
      if (el) el.textContent = d.history_entries || el.textContent;
    }
  } catch {}
})();
