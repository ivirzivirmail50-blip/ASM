/* Dashboard charts + heatmap + AI modals. */

// ---- Daily ring chart — reads from window globals (set by template) ----
(function() {
  const daily = window.ASM_DAILY_WORDS || 0;
  const goal = window.ASM_DAILY_GOAL || 500;
  const pct = Math.min(daily / Math.max(goal, 1), 1);
  const ring = document.getElementById("dailyRing");
  if (!ring) return;
  const circumference = 2 * Math.PI * 48;  // ~301.59
  ring.style.strokeDashoffset = circumference * (1 - pct);
  // Animate the number
  let cur = 0;
  const step = Math.max(1, Math.ceil(daily / 30));
  const interval = setInterval(() => {
    cur += step;
    if (cur >= daily) { cur = daily; clearInterval(interval); }
    const valEl = document.getElementById("dailyRingValue");
    if (valEl) valEl.textContent = cur;
  }, 30);
})();

// ---- 30-day word history chart ----
(function() {
  const ctx = document.getElementById("wordHistoryChart");
  if (!ctx) return;
  const data = window.ASM_DAILY_HISTORY || [];
  const labels = data.map(d => d.date.slice(5));   // MM-DD
  const values = data.map(d => d.words);
  const maxValue = Math.max(...values, 100);
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Words",
        data: values,
        backgroundColor: "rgba(99, 102, 241, 0.6)",
        borderColor: "#6366f1",
        borderWidth: 1,
        maxBarThickness: 20,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#6b7299", maxTicksLimit: 8, font: { size: 10 } }
        },
        y: {
          grid: { color: "rgba(108, 115, 153, 0.15)" },
          ticks: { color: "#6b7299", font: { size: 10 } },
          beginAtZero: true,
          max: Math.ceil(maxValue * 1.2),
        }
      }
    }
  });
})();

// ---- Annual heatmap ----
(function() {
  const container = document.getElementById("annualHeatmap");
  if (!container) return;
  const data = window.ASM_ANNUAL_HEATMAP || [];
  container.innerHTML = "";
  data.forEach(d => {
    const cell = document.createElement("div");
    cell.className = "heatmap-cell" + (d.level > 0 ? ` l${d.level}` : "");
    cell.title = `${d.date}: ${d.words} words`;
    cell.onclick = () => {
      if (d.words > 0) {
        showToast(`${d.date}: ${d.words} words written`, "info", 2000);
      }
    };
    container.appendChild(cell);
  });
})();

// ---- AI Consistency Check ----
async function runConsistencyCheck() {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal modal-lg">
      <div class="modal-header"><h3 class="modal-title">🔍 AI Consistency Check</h3></div>
      <div class="modal-body">
        <div id="ccStatus" class="text-sm text-dim">Scanning chapters against character/world DB…</div>
        <div id="ccResults" class="mt-3"></div>
      </div>
      <div class="modal-footer">
        <button class="btn" data-act="close">Close</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector('[data-act="close"]').onclick = () => backdrop.remove();
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });

  const { data } = await asmFetch("/ai/consistency-check", { method: "POST", body: {} });
  const status = document.getElementById("ccStatus");
  const results = document.getElementById("ccResults");
  if (data.ok) {
    status.textContent = `Found ${data.count} finding${data.count !== 1 ? 's' : ''}.`;
    if (data.findings && data.findings.length) {
      results.innerHTML = data.findings.map(f => `
        <div class="card mb-2" style="border-left: 3px solid ${f.severity === 'error' ? 'var(--danger)' : (f.severity === 'warning' ? 'var(--warning)' : 'var(--info)')}">
          <div class="flex items-center gap-2 mb-1">
            <span class="badge no-dot ${f.severity === 'error' ? 'danger' : (f.severity === 'warning' ? 'warning' : '')}">${f.severity}</span>
            <span class="badge no-dot" style="font-size: 0.65rem">${f.category}</span>
            ${f.chapter ? `<span class="text-mute text-xs">in "${escapeHtml(f.chapter)}"</span>` : ''}
          </div>
          <div class="text-sm" style="color: var(--text)">${escapeHtml(f.message)}</div>
        </div>
      `).join("");
    } else {
      results.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div><h3>No issues found</h3></div>';
    }
  } else {
    status.textContent = "Check failed: " + (data.error || "unknown error");
    status.style.color = "var(--danger)";
  }
}

// ---- AI Name Generator ----
function openNameGenerator() {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <div class="modal-header"><h3 class="modal-title">🎲 AI Name Generator</h3></div>
      <div class="modal-body">
        <div class="card-grid cols-2 mb-3">
          <div class="form-row">
            <label class="form-label">Culture / Style</label>
            <select id="ngCulture" class="form-select">
              <option value="fantasy">Fantasy</option>
              <option value="medieval">Medieval European</option>
              <option value="norse">Norse</option>
              <option value="arabic">Arabic</option>
              <option value="japanese">Japanese</option>
              <option value="elvish">Elvish</option>
              <option value="dwarven">Dwarven</option>
              <option value="scifi">Sci-fi</option>
            </select>
          </div>
          <div class="form-row">
            <label class="form-label">Kind</label>
            <select id="ngKind" class="form-select">
              <option value="character">Character</option>
              <option value="location">Location</option>
              <option value="faction">Faction</option>
              <option value="artifact">Artifact</option>
            </select>
          </div>
        </div>
        <div id="ngResults" class="flex flex-col gap-2"></div>
      </div>
      <div class="modal-footer">
        <button class="btn" data-act="close">Close</button>
        <button class="btn btn-primary" data-act="gen">Generate</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector('[data-act="close"]').onclick = () => backdrop.remove();
  backdrop.querySelector('[data-act="gen"]').onclick = async () => {
    const results = document.getElementById("ngResults");
    results.innerHTML = '<div class="text-mute text-sm">Generating…</div>';
    const { data } = await asmFetch("/ai/generate-name", {
      method: "POST",
      body: {
        culture: document.getElementById("ngCulture").value,
        kind: document.getElementById("ngKind").value,
      }
    });
    if (data.ok && data.names && data.names.length) {
      results.innerHTML = data.names.map(n => `
        <div class="flex items-center gap-2" style="padding: 0.5rem; background: var(--bg-elev-2); border-radius: 6px">
          <span style="flex: 1; font-weight: 500">${escapeHtml(n)}</span>
          <button class="btn btn-ghost btn-sm" onclick="navigator.clipboard.writeText('${escapeHtml(n)}'); showToast('Copied.', 'success', 1200)">Copy</button>
        </div>
      `).join("");
    } else {
      results.innerHTML = `<div class="text-danger text-sm">${escapeHtml(data.error || 'Failed')}</div>`;
    }
  };
  // Auto-generate on open
  backdrop.querySelector('[data-act="gen"]').click();
}
