/* EasyMDE editor helpers — shared across chapter edit pages. */
window.AsmEditor = {
  instances: new Map(),
  register(id, mde) { this.instances.set(id, mde); },
  get(id) { return this.instances.get(id); },
};
