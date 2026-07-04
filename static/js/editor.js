/* EasyMDE init helper (loaded alongside editor page) */
// Loaded by chapters/edit.html; placeholder for any future shared editor logic.
window.AsmEditor = {
  instances: new Map(),
  register(id, mde) { this.instances.set(id, mde); }
};
