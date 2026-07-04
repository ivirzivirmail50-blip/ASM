/* Absolute Story Manager — app.js
   CSRF, keyboard shortcuts, undo/redo, toasts, theme/sidebar toggle, helpers.
*/

// ---- CSRF helper ----
function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : "";
}

// ---- Fetch wrapper with CSRF + JSON ----
async function asmFetch(url, opts = {}) {
  opts.method = opts.method || "GET";
  opts.headers = opts.headers || {};
  opts.headers["X-CSRFToken"] = getCsrfToken();
  if (opts.body && !(opts.body instanceof FormData) && !opts.headers["Content-Type"]) {
    opts.headers["Content-Type"] = "application/json";
    if (typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, opts);
  let data;
  try { data = await res.json(); }
  catch { data = { ok: false, error: "Invalid response" }; }
  return { res, data };
}

// ---- Form submission helper (sends FormData, not JSON) ----
// Use this for all form POSTs so request.form works on the backend.
async function submitForm(formEl, url) {
  const fd = new FormData(formEl);
  const res = await fetch(url || formEl.action, {
    method: "POST",
    headers: { "X-CSRFToken": getCsrfToken() },
    body: fd
  });
  let data;
  try { data = await res.json(); }
  catch { data = { ok: false, error: "Invalid response from server" }; }
  return data;
}

// ---- Toast system ----
function showToast(message, kind = "info", duration = 3000) {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.innerHTML = `<span>${_toastIcon(kind)}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(t);
  setTimeout(() => {
    t.classList.add("removing");
    setTimeout(() => t.remove(), 200);
  }, duration);
}

function _toastIcon(kind) {
  return {
    success: "✓", error: "✕", warning: "⚠", info: "ℹ"
  }[kind] || "ℹ";
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// ---- Theme + sidebar toggle (persisted via /settings/save) ----
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme") || "dark";
  const next = current === "dark" ? "light" : "dark";
  html.setAttribute("data-theme", next);
  // Persist
  asmFetch("/settings/save", {
    method: "POST",
    body: { theme: next }
  }).then(({ data }) => {
    if (data.ok) showToast(`Theme: ${next}`, "info", 1500);
  });
}

function toggleSidebar() {
  const shell = document.getElementById("appShell");
  if (!shell) return;
  const collapsed = shell.getAttribute("data-sidebar-collapsed") === "true";
  const next = !collapsed;
  shell.setAttribute("data-sidebar-collapsed", next ? "true" : "false");
  asmFetch("/settings/save", {
    method: "POST",
    body: { sidebar_collapsed: next ? "true" : "false" }
  });
}

function toggleMobileNav() {
  const shell = document.getElementById("appShell");
  if (!shell) return;
  shell.classList.toggle("mobile-nav-open");
  // Close on click outside
  if (shell.classList.contains("mobile-nav-open")) {
    setTimeout(() => {
      document.addEventListener("click", function closeNav(e) {
        if (!e.target.closest(".sidebar") && !e.target.closest(".mobile-menu-btn")) {
          shell.classList.remove("mobile-nav-open");
          document.removeEventListener("click", closeNav);
        }
      });
    }, 100);
  }
}

// ---- Undo / Redo (command pattern, in-memory + DB-backed for deletes) ----
const _undoStack = [];
const _redoStack = [];
const MAX_UNDO = 100;

function pushUndo(label, undoFn, redoFn) {
  _undoStack.push({ label, undoFn, redoFn });
  if (_undoStack.length > MAX_UNDO) _undoStack.shift();
  _redoStack.length = 0;
  _updateUndoButtons();
}

function undo() {
  // First try DB-backed undo (persistent delete undo)
  asmFetch("/undo", { method: "POST", body: {} }).then(({ data }) => {
    if (data.ok) {
      showToast(`Undid: ${data.label}`, "success");
      setTimeout(() => location.reload(), 600);
    } else {
      // Fall back to in-memory undo
      const cmd = _undoStack.pop();
      if (!cmd) {
        showToast("Nothing to undo.", "info", 1500);
        return;
      }
      cmd.undoFn();
      _redoStack.push(cmd);
      _updateUndoButtons();
      showToast(`Undid: ${cmd.label}`, "info", 1500);
    }
  });
}

function redo() {
  const cmd = _redoStack.pop();
  if (!cmd) {
    showToast("Nothing to redo.", "info", 1500);
    return;
  }
  cmd.redoFn();
  _undoStack.push(cmd);
  _updateUndoButtons();
  showToast(`Redid: ${cmd.label}`, "info", 1500);
}

function _updateUndoButtons() {
  const undoBtn = document.getElementById("undoBtn");
  const redoBtn = document.getElementById("redoBtn");
  if (undoBtn) undoBtn.disabled = _undoStack.length === 0;
  if (redoBtn) redoBtn.disabled = _redoStack.length === 0;
}

// ---- Delete with undo toast (10-second window) ----
function showUndoToast(label, onUndo) {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const t = document.createElement("div");
  t.className = "toast warning";
  t.style.minWidth = "320px";
  t.innerHTML = `
    <span style="flex: 1">${escapeHtml(label)}. Undo?</span>
    <button class="btn btn-sm btn-primary" style="margin-left: 0.5rem">Undo</button>
  `;
  container.appendChild(t);
  let undone = false;
  const undoBtn = t.querySelector("button");
  undoBtn.onclick = () => {
    undone = true;
    t.classList.add("removing");
    setTimeout(() => t.remove(), 200);
    if (onUndo) onUndo();
  };
  // Auto-dismiss after 10 seconds
  setTimeout(() => {
    if (!undone) {
      t.classList.add("removing");
      setTimeout(() => t.remove(), 200);
    }
  }, 10000);
}

// ---- Keyboard shortcuts ----
document.addEventListener("keydown", (e) => {
  // Skip when typing in inputs/textareas (except for Ctrl+S / Ctrl+Z)
  const target = e.target;
  const isTyping = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);

  // Ctrl+S — save (let editor handle it; otherwise prevent default)
  if ((e.ctrlKey || e.metaKey) && e.key === "s") {
    e.preventDefault();
    return;
  }
  // Ctrl+Z / Ctrl+Shift+Z
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    if (e.shiftKey) { e.preventDefault(); redo(); }
    else if (!isTyping) { e.preventDefault(); undo(); }
    return;
  }
  // Ctrl+N — new chapter
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
    e.preventDefault();
    window.location.href = "/chapters/new";
    return;
  }
  // Ctrl+Shift+N — new character
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "n") {
    e.preventDefault();
    window.location.href = "/characters/new";
    return;
  }
  // "/" — focus search (if not typing)
  if (e.key === "/" && !isTyping) {
    e.preventDefault();
    const input = document.querySelector('input[name="q"]');
    if (input) input.focus();
    return;
  }
  // Ctrl+P / Cmd+P — Quick Switch
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
    e.preventDefault();
    openQuickSwitch();
    return;
  }
  // Escape — close modal / exit distraction-free
  if (e.key === "Escape") {
    const modal = document.querySelector(".modal-backdrop");
    if (modal) { modal.remove(); return; }
    if (document.body.classList.contains("distraction-free")) {
      document.body.classList.remove("distraction-free");
      return;
    }
  }
  // F11 — distraction-free
  if (e.key === "F11") {
    e.preventDefault();
    document.body.classList.toggle("distraction-free");
  }
  // Ctrl+E — toggle edit mode on detail pages
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "e") {
    e.preventDefault();
    const editLink = document.querySelector('a[href*="/edit"]');
    if (editLink) {
      window.location.href = editLink.href;
    }
  }
});

// ---- Confirmation modal ----
function confirmDialog(message, opts = {}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3 class="modal-title">${escapeHtml(opts.title || "Confirm")}</h3>
        </div>
        <div class="modal-body">
          <p style="margin:0;color:var(--text)">${escapeHtml(message)}</p>
        </div>
        <div class="modal-footer">
          <button class="btn" data-act="cancel">Cancel</button>
          <button class="btn ${opts.danger ? 'btn-danger' : 'btn-primary'}" data-act="ok">${escapeHtml(opts.okLabel || "Confirm")}</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", (ev) => {
      if (ev.target === backdrop) { backdrop.remove(); resolve(false); }
    });
    backdrop.querySelector('[data-act="cancel"]').onclick = () => { backdrop.remove(); resolve(false); };
    backdrop.querySelector('[data-act="ok"]').onclick = () => { backdrop.remove(); resolve(true); };
  });
}

// ---- Wire up undo/redo buttons ----
document.addEventListener("DOMContentLoaded", () => {
  const undoBtn = document.getElementById("undoBtn");
  const redoBtn = document.getElementById("redoBtn");
  if (undoBtn) undoBtn.addEventListener("click", undo);
  if (redoBtn) redoBtn.addEventListener("click", redo);
  _updateUndoButtons();
});

// ---- cycleStatus: click chapter status badge to cycle draft→revised→final ----
function cycleStatus(chapterId, currentStatus) {
  asmFetch(`/chapters/${chapterId}/cycle-status`, {
    method: "POST",
    body: {}
  }).then(({ data }) => {
    if (data.ok) {
      showToast(`Status → ${data.status}`, "success");
      setTimeout(() => location.reload(), 500);
    } else {
      showToast(data.error || "Failed", "error");
    }
  });
}

// ---- Export diff helper (client-side download) ----
function exportDiff(filename, content, format = "txt") {
  const blob = new Blob([content], { type: format === "html" ? "text/html" : "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---- Expose globally ----
window.asmFetch = asmFetch;
window.submitForm = submitForm;
window.getCsrfToken = getCsrfToken;
window.showToast = showToast;
window.pushUndo = pushUndo;
window.undo = undo;
window.redo = redo;
window.toggleTheme = toggleTheme;
window.toggleSidebar = toggleSidebar;
window.toggleMobileNav = toggleMobileNav;
window.confirmDialog = confirmDialog;
window.cycleStatus = cycleStatus;
window.exportDiff = exportDiff;
window.escapeHtml = escapeHtml;
window.showUndoToast = showUndoToast;

// ---- Quick Switch (Ctrl+P) ----
let _qsSelected = -1;
let _qsResults = [];

function openQuickSwitch() {
  const overlay = document.getElementById("quickSwitchOverlay");
  if (!overlay) return;
  overlay.style.display = "flex";
  const input = document.getElementById("quickSwitchInput");
  input.value = "";
  input.focus();
  _qsResults = [];
  _qsSelected = -1;
  document.getElementById("quickSwitchResults").innerHTML =
    '<div class="quickswitch-empty">Start typing to search chapters, characters, world entries…</div>';

  // Load nav items immediately (empty query shows navigation)
  _qsSearch("");
}

function closeQuickSwitch() {
  const overlay = document.getElementById("quickSwitchOverlay");
  if (overlay) overlay.style.display = "none";
}

async function _qsSearch(q) {
  const res = await fetch(`/search-all?q=${encodeURIComponent(q)}`);
  const data = await res.json();
  _qsResults = data.results || [];
  _qsSelected = _qsResults.length > 0 ? 0 : -1;
  _qsRender();
}

function _qsRender() {
  const container = document.getElementById("quickSwitchResults");
  if (!_qsResults.length) {
    container.innerHTML = '<div class="quickswitch-empty">No results found.</div>';
    return;
  }
  // Group by type
  const groups = {};
  for (const r of _qsResults) {
    const label = {chapter:"Chapters",character:"Characters",plan:"Plans",world_entry:"World",nav:"Navigation"}[r.type] || "Other";
    (groups[label] = groups[label] || []).push(r);
  }
  let html = "";
  let idx = 0;
  for (const [label, items] of Object.entries(groups)) {
    html += `<div class="quickswitch-section-label">${label}</div>`;
    for (const item of items) {
      const cls = idx === _qsSelected ? "quickswitch-item selected" : "quickswitch-item";
      html += `<a class="${cls}" data-idx="${idx}" href="${item.url}" onclick="closeQuickSwitch()">
        <span class="qs-icon">${item.icon || "▸"}</span>
        <div>
          <div class="qs-title">${escapeHtml(item.title)}</div>
          <div class="qs-sub">${escapeHtml(item.subtitle || "")}</div>
        </div>
      </a>`;
      idx++;
    }
  }
  container.innerHTML = html;
}

// Quick Switch keyboard navigation
document.addEventListener("keydown", (e) => {
  const overlay = document.getElementById("quickSwitchOverlay");
  if (!overlay || overlay.style.display === "none") return;
  if (e.key === "Escape") { closeQuickSwitch(); e.preventDefault(); return; }
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (_qsResults.length) { _qsSelected = (_qsSelected + 1) % _qsResults.length; _qsRender(); }
    return;
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    if (_qsResults.length) { _qsSelected = (_qsSelected - 1 + _qsResults.length) % _qsResults.length; _qsRender(); }
    return;
  }
  if (e.key === "Enter") {
    e.preventDefault();
    if (_qsSelected >= 0 && _qsResults[_qsSelected]) {
      window.location.href = _qsResults[_qsSelected].url;
    }
    return;
  }
});

// Quick Switch input listener
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("quickSwitchInput");
  if (!input) return;
  let debounce = null;
  input.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => _qsSearch(input.value.trim()), 200);
  });
  // Click outside to close
  document.getElementById("quickSwitchOverlay")?.addEventListener("click", (e) => {
    if (e.target.id === "quickSwitchOverlay") closeQuickSwitch();
  });
});

window.openQuickSwitch = openQuickSwitch;
window.closeQuickSwitch = closeQuickSwitch;

// ---- Global AI functions (available on every page when AI enabled) ----
async function aiConsistencyCheck() {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal modal-lg">
      <div class="modal-header"><h3 class="modal-title">🔍 AI Consistency Check</h3></div>
      <div class="modal-body">
        <div id="ccStatus" class="text-sm text-dim">Scanning chapters against character/world DB…</div>
        <div id="ccResults" class="mt-3" style="max-height: 60vh; overflow-y: auto"></div>
      </div>
      <div class="modal-footer"><button class="btn" data-act="close">Close</button></div>
    </div>`;
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
        <div class="card mb-2" style="border-left: 3px solid ${f.severity === 'error' ? 'var(--danger)' : (f.severity === 'warning' ? 'var(--warning)' : 'var(--info)')}; padding: 0.6rem">
          <div class="flex items-center gap-2 mb-1">
            <span class="badge no-dot ${f.severity === 'error' ? 'danger' : (f.severity === 'warning' ? 'warning' : '')}">${f.severity}</span>
            <span class="badge no-dot" style="font-size: 0.6rem">${f.category}</span>
            ${f.chapter ? `<span class="text-mute text-xs">in "${escapeHtml(f.chapter)}"</span>` : ''}
          </div>
          <div class="text-sm" style="color: var(--text)">${escapeHtml(f.message)}</div>
        </div>`).join("");
    } else {
      results.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div><h3>No issues found</h3></div>';
    }
  } else {
    status.textContent = "Check failed: " + (data.error || "unknown error");
    status.style.color = "var(--danger)";
  }
}

async function aiNameGenerator() {
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
    </div>`;
  document.body.appendChild(backdrop);
  backdrop.querySelector('[data-act="close"]').onclick = () => backdrop.remove();
  backdrop.querySelector('[data-act="gen"]').onclick = async () => {
    const results = document.getElementById("ngResults");
    results.innerHTML = '<div class="text-mute text-sm">Generating…</div>';
    const { data } = await asmFetch("/ai/generate-name", {
      method: "POST",
      body: { culture: document.getElementById("ngCulture").value, kind: document.getElementById("ngKind").value }
    });
    if (data.ok && data.names && data.names.length) {
      results.innerHTML = data.names.map(n => `
        <div class="flex items-center gap-2" style="padding: 0.5rem; background: var(--bg-elev-2); border-radius: 6px">
          <span style="flex: 1; font-weight: 500">${escapeHtml(n)}</span>
          <button class="btn btn-ghost btn-sm" onclick="navigator.clipboard.writeText('${escapeHtml(n)}'); showToast('Copied.', 'success', 1200)">Copy</button>
        </div>`).join("");
    } else {
      results.innerHTML = `<div class="text-danger text-sm">${escapeHtml(data.error || 'Failed')}</div>`;
    }
  };
  backdrop.querySelector('[data-act="gen"]').click();
}

window.aiConsistencyCheck = aiConsistencyCheck;
window.aiNameGenerator = aiNameGenerator;

// ---- AI Loading Overlay with Cancel ----
let _aiAbortController = null;

function showAILoading(message, subMessage) {
  hideAILoading();
  _aiAbortController = new AbortController();
  const overlay = document.createElement("div");
  overlay.className = "ai-loading-overlay";
  overlay.id = "aiLoadingOverlay";
  overlay.innerHTML = `
    <div class="ai-loading-card">
      <div class="ai-loading-spinner"></div>
      <div class="ai-loading-text">${escapeHtml(message || "AI is thinking...")}</div>
      ${subMessage ? `<div class="ai-loading-sub">${escapeHtml(subMessage)}</div>` : ""}
      <button class="ai-loading-cancel" onclick="cancelAI()">✕ Cancel</button>
    </div>
  `;
  document.body.appendChild(overlay);
}

function hideAILoading() {
  const overlay = document.getElementById("aiLoadingOverlay");
  if (overlay) overlay.remove();
  _aiAbortController = null;
}

function cancelAI() {
  if (_aiAbortController) {
    _aiAbortController.abort();
    _aiAbortController = null;
  }
  hideAILoading();
  showToast("AI request cancelled.", "info", 1500);
}

function getAIAbortSignal() {
  return _aiAbortController ? _aiAbortController.signal : undefined;
}

// ---- AI Chat (brainstorming assistant) ----
let _aiChatHistory = [];

async function openAIChat() {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal modal-lg" style="max-width: 800px">
      <div class="modal-header" style="background: var(--grad-accent); color: #fff">
        <h3 class="modal-title" style="color: #fff">✨ AI Writing Assistant</h3>
        <button class="btn btn-ghost btn-icon btn-sm" style="color: #fff" onclick="this.closest('.modal-backdrop').remove()">×</button>
      </div>
      <div class="modal-body" style="padding: 0">
        <div class="ai-chat-container" id="aiChatMessages" style="min-height: 300px; max-height: 55vh">
          ${_aiChatHistory.length ? _aiChatHistory.map(m => `
            <div class="ai-chat-msg ${m.role}">${m.role === 'assistant' ? '<div class="font-serif">' + escapeHtml(m.content) + '</div>' : escapeHtml(m.content)}</div>
          `).join("") : `
            <div style="text-align: center; padding: 2rem 1rem">
              <div style="font-size: 2.5rem; opacity: 0.3">✨</div>
              <div style="color: var(--text-dim); margin-top: 0.5rem; font-size: 0.9rem">Ask me anything about your story, characters, plot ideas, or writing tips!</div>
              <div class="flex gap-2 justify-center mt-3 flex-wrap">
                <button class="btn btn-sm" onclick="document.getElementById('aiChatInput').value='Give me a plot twist idea'; sendAIChatMessage()">💡 Plot twist</button>
                <button class="btn btn-sm" onclick="document.getElementById('aiChatInput').value='How can I improve my character motivation?'; sendAIChatMessage()">🎭 Character</button>
                <button class="btn btn-sm" onclick="document.getElementById('aiChatInput').value='Suggest a setting for a fantasy battle scene'; sendAIChatMessage()">⚔️ Setting</button>
              </div>
            </div>
          `}
        </div>
        <div class="ai-chat-input" style="padding: 0.75rem; border-top: 1px solid var(--border); background: var(--bg-elev-2)">
          <textarea id="aiChatInput" placeholder="Type your question... (Enter to send, Shift+Enter for new line)" rows="1"
                    style="background: var(--bg-elev-1); border: 1px solid var(--border); border-radius: 10px; padding: 0.6rem 0.85rem; color: var(--text); font-size: 0.9rem; resize: none; min-height: 42px; max-height: 120px;"
                    onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAIChatMessage()}"></textarea>
          <button class="btn btn-primary" onclick="sendAIChatMessage()" style="border-radius: 10px">Send</button>
        </div>
      </div>
      <div class="modal-footer" style="padding: 0.5rem 0.75rem">
        <span class="text-mute text-xs">${_aiChatHistory.length} messages in this session</span>
        <div class="grow"></div>
        <button class="btn btn-sm" onclick="if(confirm('Clear chat?')){_aiChatHistory=[];document.getElementById('aiChatMessages').innerHTML='<div style=\\'text-align:center;padding:2rem\\'><div style=\\'font-size:2.5rem;opacity:0.3\\'>✨</div><div style=\\'color:var(--text-dim);margin-top:0.5rem\\'>Chat cleared.</div></div>'}">🗑 Clear</button>
        <a href="/ai-history" class="btn btn-sm">📋 History</a>
        <button class="btn" data-act="close">Close</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector('[data-act="close"]').onclick = () => backdrop.remove();
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });
  const container = document.getElementById("aiChatMessages");
  if (container) container.scrollTop = container.scrollHeight;
  setTimeout(() => document.getElementById("aiChatInput")?.focus(), 100);
}

async function sendAIChatMessage() {
  const input = document.getElementById("aiChatInput");
  if (!input) return;
  const message = input.value.trim();
  if (!message) return;
  input.value = "";

  // Add user message to UI
  const container = document.getElementById("aiChatMessages");
  if (container) {
    container.innerHTML += `<div class="ai-chat-msg user">${escapeHtml(message)}</div>`;
    container.scrollTop = container.scrollHeight;
  }

  // Build chat prompt from history
  _aiChatHistory.push({ role: "user", content: message });
  const chatPrompt = _aiChatHistory.map(m =>
    `${m.role === "user" ? "Human" : "Assistant"}: ${m.content}`
  ).join("\n\n") + "\n\nAssistant:";

  // Show loading
  showAILoading("AI is thinking...", "This may take a few seconds");
  try {
    const { data } = await asmFetch("/ai/continue", {
      method: "POST",
      body: { text: chatPrompt, max_tokens: 500 }
    });
    hideAILoading();
    if (data.ok) {
      const response = data.response;
      _aiChatHistory.push({ role: "assistant", content: response });
      if (container) {
        container.innerHTML += `<div class="ai-chat-msg assistant"><div class="font-serif">${escapeHtml(response)}</div></div>`;
        container.scrollTop = container.scrollHeight;
      }
    } else {
      if (container) {
        container.innerHTML += `<div class="ai-chat-msg assistant" style="color:var(--danger)">Error: ${escapeHtml(data.error || 'Failed')}</div>`;
      }
      showToast(data.error || "AI failed", "error");
    }
  } catch (err) {
    hideAILoading();
    showToast("Request failed: " + err.message, "error");
  }
}

window.openAIChat = openAIChat;
window.sendAIChatMessage = sendAIChatMessage;
window.showAILoading = showAILoading;
window.hideAILoading = hideAILoading;
window.cancelAI = cancelAI;
window.getAIAbortSignal = getAIAbortSignal;
