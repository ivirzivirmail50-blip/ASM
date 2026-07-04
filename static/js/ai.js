/* AI integration helpers — only loaded when AI is enabled.
   Provides client-side helpers for AI features (modals, streaming display, etc.)
   The actual AI calls go through asmFetch to /ai/* endpoints.
*/

window.AsmAI = {
  enabled: true,

  /** Show a "Stop generating" button while waiting for AI response. */
  withStopButton(message, promise) {
    const container = document.createElement("div");
    container.className = "toast info";
    container.style.minWidth = "300px";
    container.innerHTML = `
      <span>${escapeHtml(message)}</span>
      <button class="btn btn-ghost btn-sm" style="margin-left: auto">Stop</button>
    `;
    document.getElementById("toastContainer").appendChild(container);
    let cancelled = false;
    const stopBtn = container.querySelector("button");
    stopBtn.onclick = () => { cancelled = true; container.remove(); };
    return promise.finally(() => {
      if (!cancelled) container.remove();
    });
  },

  /** Insert AI-generated text into an editor at cursor position. */
  insertAtCursor(editor, text) {
    const cm = editor.codemirror;
    const doc = cm.getDoc();
    const cursor = doc.getCursor();
    doc.replaceRange(text, cursor);
  },

  /** Show AI response in a modal with copy/insert buttons. */
  showResponseModal(response, onInsert) {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal modal-lg">
        <div class="modal-header">
          <h3 class="modal-title">✨ AI Response</h3>
          <button class="btn btn-ghost btn-icon btn-sm" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>
        <div class="modal-body">
          <div class="font-serif" style="line-height: 1.7; color: var(--text); white-space: pre-wrap">${escapeHtml(response)}</div>
        </div>
        <div class="modal-footer">
          <button class="btn" onclick="navigator.clipboard.writeText(${JSON.stringify(response)}); showToast('Copied.', 'success', 1500)">Copy</button>
          <button class="btn btn-primary" data-act="insert">Insert</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    backdrop.querySelector('[data-act="insert"]').onclick = () => {
      if (onInsert) onInsert(response);
      backdrop.remove();
    };
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.remove();
    });
  }
};
