/* character relationship graph using vis-network
   - Loads nodes/edges from /characters/graph/data
   - Drag nodes → save position
   - Click node → navigate to character detail
   - Click edge → show relationship details popup with delete
   - Filter pills → show only specific relationship types
   - Click legend group → highlight members, dim others
   - Add relationship mode: click 2 nodes → modal → save
*/
(function () {
  let network = null;
  let allNodes = [];
  let allEdges = [];
  let activeFilter = "all";
  let addMode = false;
  let addFirstNode = null;
  let physicsOn = true;
  let container, popup, popupEdgeId = null;

  async function init() {
    container = document.getElementById("character-graph");
    if (!container) return;
    const res = await fetch("/characters/graph/data");
    const data = await res.json();
    allNodes = data.nodes;
    allEdges = data.edges;

    // Use saved positions when available
    const nodesDS = new vis.DataSet(allNodes.map(n => ({
      ...n,
      x: (typeof n.x === "number") ? n.x : undefined,
      y: (typeof n.y === "number") ? n.y : undefined,
    })));
    const edgesDS = new vis.DataSet(allEdges);

    const options = {
      nodes: {
        shape: "dot",
        font: { color: "#e6e9f5", size: 13, face: "Inter" },
        borderWidth: 2,
        borderWidthSelected: 4,
      },
      edges: {
        font: {
          color: "#9aa3c7",
          size: 10,
          face: "Inter",
          strokeWidth: 0,
          background: "rgba(11, 16, 32, 0.7)",
        },
        smooth: { type: "continuous", roundness: 0.5 },
        selectionWidth: 2,
      },
      physics: {
        enabled: true,
        solver: "forceAtlas2Based",
        forceAtlas2Based: {
          gravitationalConstant: -45,
          centralGravity: 0.012,
          springLength: 110,
          springConstant: 0.05,
          damping: 0.5,
          avoidOverlap: 0.7,
        },
        stabilization: {
          enabled: true,
          iterations: 200,
          updateInterval: 25,
          fit: true,
        },
        timestep: 0.5,
        maxVelocity: 50,
      },
      interaction: {
        hover: true,
        tooltipDelay: 150,
        zoomView: true,
        dragView: true,
        dragNodes: true,
        navigationButtons: false,
        keyboard: false,
        multiselect: false,
      },
      layout: { improvedLayout: true, randomSeed: 42 },
    };

    network = new vis.Network(container, { nodes: nodesDS, edges: edgesDS }, options);

    // Click events
    network.on("click", handleClick);
    network.on("doubleClick", () => network.fit({ animation: true }));
    network.on("dragEnd", handleDragEnd);
    network.on("stabilizationIterationsDone", () => {
      // Once stable, save current positions
      const positions = network.getPositions();
      // We don't auto-save to avoid DB spam; positions save only on manual drag
    });

    // Build popup element
    buildPopup();

    // Wire up filter pills
    document.querySelectorAll('.pill[data-filter]').forEach(p => {
      p.addEventListener("click", () => {
        document.querySelectorAll('.pill[data-filter]').forEach(x => x.classList.remove("active"));
        p.classList.add("active");
        activeFilter = p.dataset.filter;
        applyFilter();
      });
    });

    showToast("Graph loaded.", "info", 1500);
  }

  function applyFilter() {
    if (!network) return;
    if (activeFilter === "all") {
      // Show all edges
      network.body.data.edges.update(allEdges.map(e => ({ id: e.id, hidden: false })));
      return;
    }
    allEdges.forEach(e => {
      // Group-related edges stay visible only when "all"
      const isGroupLink = String(e.id).startsWith("g2g-") || String(e.id).startsWith("g2m-");
      const hide = isGroupLink || (e.label && e.label.replace(/\s/g, "_") !== activeFilter);
      network.body.data.edges.update({ id: e.id, hidden: hide });
    });
  }

  function handleClick(params) {
    if (addMode) {
      handleAddModeClick(params);
      return;
    }
    if (params.edges.length > 0) {
      const edgeId = params.edges[0];
      showEdgePopup(edgeId, params.pointer.DOM);
      return;
    }
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0];
      const node = allNodes.find(n => n.id === nodeId);
      if (node && !node.group) {
        window.location.href = `/characters/${nodeId}`;
      }
    } else {
      hidePopup();
    }
  }

  function handleDragEnd(params) {
    if (params.nodes.length === 0) return;
    const nodeId = params.nodes[0];
    if (String(nodeId).startsWith("g-")) return;  // skip group nodes
    const pos = network.getPositions([nodeId])[nodeId];
    if (!pos) return;
    // Save position
    asmFetch("/characters/graph/save-position", {
      method: "POST",
      body: { id: nodeId, x: Math.round(pos.x), y: Math.round(pos.y) }
    }).then(({ data }) => {
      if (data.ok) showToast("Position saved.", "success", 1200);
    });
  }

  function buildPopup() {
    popup = document.createElement("div");
    popup.className = "card";
    popup.style.cssText = `
      position: absolute; display: none; z-index: 30; min-width: 240px;
      box-shadow: var(--shadow-lg); border: 1px solid var(--border-strong);
    `;
    container.parentNode.appendChild(popup);
    // Click outside to close
    document.addEventListener("click", (e) => {
      if (popup && popup.style.display !== "none" &&
          !popup.contains(e.target) && !container.contains(e.target)) {
        hidePopup();
      }
    });
  }

  function showEdgePopup(edgeId, domPos) {
    const edge = allEdges.find(e => e.id === edgeId);
    if (!edge) return;
    popupEdgeId = edgeId;
    const isGroup = String(edgeId).startsWith("g2g-") || String(edgeId).startsWith("g2m-");
    popup.innerHTML = `
      <div class="modal-header">
        <h3 class="modal-title">${escapeHtml(edge.label || "Relationship")}</h3>
        <button class="btn btn-ghost btn-icon btn-sm" onclick="hidePopup()">×</button>
      </div>
      <div class="modal-body">
        <div class="text-sm text-dim mb-2">${escapeHtml(edge.title || "")}</div>
        ${isGroup ? '<div class="text-xs text-mute">Group-level link (no delete)</div>' : `
        <div class="flex gap-2">
          <button class="btn btn-danger btn-sm" onclick="deleteEdge('${edgeId}')">Delete</button>
        </div>`}
      </div>
    `;
    const rect = container.getBoundingClientRect();
    popup.style.left = `${rect.left + domPos.x + 12}px`;
    popup.style.top = `${rect.top + domPos.y + 12}px`;
    popup.style.display = "block";
  }

  window.hidePopup = function () {
    if (popup) popup.style.display = "none";
    popupEdgeId = null;
  };

  window.deleteEdge = async function (edgeId) {
    const ok = await confirmDialog("Delete this relationship?", { danger: true, okLabel: "Delete" });
    if (!ok) return;
    const { data } = await asmFetch(`/characters/relationships/${edgeId}/delete`, { method: "POST" });
    if (data.ok) {
      // Remove from local state + vis
      allEdges = allEdges.filter(e => e.id !== edgeId);
      network.body.data.edges.remove(edgeId);
      hidePopup();
      showToast("Relationship deleted.", "success");
    } else {
      showToast(data.error || "Failed", "error");
    }
  };

  // ---- Add relationship mode ----
  window.enterAddMode = function () {
    addMode = true;
    addFirstNode = null;
    showToast("Click first character…", "info", 0);
    container.style.cursor = "crosshair";
  };

  function handleAddModeClick(params) {
    if (params.nodes.length === 0) {
      showToast("Click a character node, not empty space.", "warning");
      return;
    }
    const nodeId = params.nodes[0];
    if (String(nodeId).startsWith("g-")) {
      showToast("Click a character, not a group.", "warning");
      return;
    }
    if (!addFirstNode) {
      addFirstNode = nodeId;
      const n = allNodes.find(x => x.id === nodeId);
      showToast(`First: ${n ? n.label : nodeId}. Click second character…`, "info", 0);
    } else if (addFirstNode === nodeId) {
      showToast("Pick a different second character.", "warning");
    } else {
      const fromId = addFirstNode;
      const toId = nodeId;
      addMode = false;
      addFirstNode = null;
      container.style.cursor = "default";
      openRelationshipModal(fromId, toId);
    }
  }

  function openRelationshipModal(fromId, toId) {
    const fromN = allNodes.find(n => n.id === fromId);
    const toN = allNodes.find(n => n.id === toId);
    const types = ["married_to","rival_of","parent_of","friend_of","enemy_of",
                   "serves","mentors","loves","betrayed_by","custom"];
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header">
          <h3 class="modal-title">New Relationship</h3>
        </div>
        <div class="modal-body">
          <div class="text-sm text-dim mb-3">
            From <strong style="color: var(--text)">${escapeHtml(fromN ? fromN.label : fromId)}</strong>
            to <strong style="color: var(--text)">${escapeHtml(toN ? toN.label : toId)}</strong>
          </div>
          <div class="form-row">
            <label class="form-label">Type</label>
            <select class="form-select" id="relType">
              ${types.map(t => `<option value="${t}">${t.replace("_", " ")}</option>`).join("")}
            </select>
          </div>
          <div class="form-row">
            <label class="form-label">Description (optional)</label>
            <textarea class="form-textarea" id="relDesc" rows="2" placeholder="e.g., 'married in secret'"></textarea>
          </div>
          <div class="form-row">
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" id="relBi"> Bidirectional (mutual)
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn" data-act="cancel">Cancel</button>
          <button class="btn btn-primary" data-act="ok">Create</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    backdrop.querySelector('[data-act="cancel"]').onclick = () => backdrop.remove();
    backdrop.querySelector('[data-act="ok"]').onclick = async () => {
      const type = document.getElementById("relType").value;
      const desc = document.getElementById("relDesc").value.trim();
      const bi = document.getElementById("relBi").checked;
      const { data } = await asmFetch("/characters/relationships/new", {
        method: "POST",
        body: { from_id: fromId, to_id: toId, type, description: desc, bidirectional: bi }
      });
      backdrop.remove();
      if (data.ok) {
        showToast("Relationship created.", "success");
        setTimeout(() => location.reload(), 600);
      } else {
        showToast(data.error || "Failed", "error");
      }
    };
  }

  // ---- Group highlight ----
  window.highlightGroup = function (groupId) {
    if (!network) return;
    // Find members
    const memberEdgeIds = allEdges
      .filter(e => String(e.id).startsWith(`g2m-${groupId}-`))
      .map(e => e.to);
    const memberIds = new Set(memberEdgeIds);
    // Dim all, then highlight members + group
    const updates = allNodes.map(n => ({
      id: n.id,
      opacity: (n.id === groupId || memberIds.has(n.id)) ? 1.0 : 0.18,
    }));
    network.body.data.nodes.update(updates);
    // Dim non-member edges
    const edgeUpdates = allEdges.map(e => {
      const keep = (String(e.id).startsWith(`g2m-${groupId}-`)) ||
                   (memberIds.has(e.from) && memberIds.has(e.to));
      return { id: e.id, opacity: keep ? 1.0 : 0.08 };
    });
    network.body.data.edges.update(edgeUpdates);
    showToast(`Highlighted group.`, "info", 1500);
    // Click same group again to reset
    setTimeout(() => {
      document.addEventListener("click", function reset() {
        const resetUpdates = allNodes.map(n => ({ id: n.id, opacity: 1.0 }));
        const resetEdges = allEdges.map(e => ({ id: e.id, opacity: 1.0 }));
        network.body.data.nodes.update(resetUpdates);
        network.body.data.edges.update(resetEdges);
        document.removeEventListener("click", reset);
      });
    }, 50);
  };

  // ---- Misc controls ----
  window.zoomGraph = function (delta) {
    if (!network) return;
    const scale = network.getScale() + delta;
    network.moveTo({ scale: Math.max(0.1, Math.min(5, scale)) });
  };
  window.fitGraph = function () { if (network) network.fit({ animation: true }); };
  window.resetGraphLayout = function () {
    if (!network) return;
    // Re-enable physics briefly to re-layout
    network.setOptions({ physics: { enabled: true } });
    network.stabilize();
    showToast("Layout reset.", "info", 1500);
  };
  window.togglePhysics = function () {
    physicsOn = !physicsOn;
    network.setOptions({ physics: { enabled: physicsOn } });
    showToast(physicsOn ? "Physics resumed." : "Physics paused.", "info", 1200);
  };

  document.addEventListener("DOMContentLoaded", init);
})();
