/* character relationship graph using vis-network
   - Loads nodes/edges from /characters/graph/data
   - Drag nodes → save position
   - Click node → open character detail (or group popup for groups)
   - Click edge → show relationship details popup (draggable, smart-positioned)
   - Filter pills → show only specific types
   - Click legend group → highlight members
   - Add relationship mode: click 2 nodes (characters OR groups) → modal → save
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

    showToast("Graph loaded.", "info", 2500);
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
      if (node) {
        if (node.group) {
          // Show group info popup instead of navigating
          showGroupPopup(nodeId, params.pointer.DOM);
        } else {
          window.location.href = `/characters/${nodeId}`;
        }
      }
    } else {
      hidePopup();
    }
  }

  function handleDragEnd(params) {
    if (params.nodes.length === 0) return;
    const nodeId = params.nodes[0];
    if (String(nodeId).startsWith("g-")) return;  // skip group nodes (but group IDs don't have g- prefix in graph_data)
    // Actually group IDs in graph_data are the raw group IDs (not prefixed)
    // So check if it's a group node by looking it up
    const node = allNodes.find(n => n.id === nodeId);
    if (node && node.group) return;
    const pos = network.getPositions([nodeId])[nodeId];
    if (!pos) return;
    // Save position
    asmFetch("/characters/graph/save-position", {
      method: "POST",
      body: { id: nodeId, x: Math.round(pos.x), y: Math.round(pos.y) }
    }).then(({ data }) => {
      if (data.ok) showToast("Position saved.", "success", 2000);
    });
  }

  function buildPopup() {
    popup = document.createElement("div");
    popup.className = "card graph-popup";
    popup.style.cssText = `
      position: fixed; display: none; z-index: 1000; min-width: 260px; max-width: 360px;
      box-shadow: var(--shadow-lg); border: 1px solid var(--border-strong);
      background: var(--bg-elev-1); border-radius: 8px;
    `;
    document.body.appendChild(popup);

    // Make popup draggable via header
    let isDragging = false;
    let dragOffsetX = 0, dragOffsetY = 0;
    popup.addEventListener("mousedown", (e) => {
      // Only drag from header area
      const header = e.target.closest(".modal-header");
      if (!header) return;
      isDragging = true;
      const rect = popup.getBoundingClientRect();
      dragOffsetX = e.clientX - rect.left;
      dragOffsetY = e.clientY - rect.top;
      popup.style.transition = "none";
      e.preventDefault();
    });
    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      let x = e.clientX - dragOffsetX;
      let y = e.clientY - dragOffsetY;
      // Keep popup within viewport
      const pw = popup.offsetWidth;
      const ph = popup.offsetHeight;
      x = Math.max(8, Math.min(window.innerWidth - pw - 8, x));
      y = Math.max(8, Math.min(window.innerHeight - ph - 8, y));
      popup.style.left = `${x}px`;
      popup.style.top = `${y}px`;
    });
    document.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        popup.style.transition = "";
      }
    });

    // Click outside to close
    document.addEventListener("click", (e) => {
      if (popup && popup.style.display !== "none" &&
          !popup.contains(e.target) && !container.contains(e.target)) {
        hidePopup();
      }
    });
    // Escape to close
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && popup && popup.style.display !== "none") {
        hidePopup();
      }
    });
  }

  function positionPopup(domPos) {
    const popupWidth = 280; // estimated
    const popupHeight = 200; // estimated
    const containerRect = container.getBoundingClientRect();
    let x = containerRect.left + domPos.x + 16;
    let y = containerRect.top + domPos.y + 16;
    // If popup would go off right edge, place it to the left
    if (x + popupWidth > window.innerWidth - 16) {
      x = containerRect.left + domPos.x - popupWidth - 16;
    }
    // If popup would go off bottom edge, place it above
    if (y + popupHeight > window.innerHeight - 16) {
      y = containerRect.top + domPos.y - popupHeight - 16;
    }
    // Ensure minimum margins
    x = Math.max(16, x);
    y = Math.max(16, y);
    popup.style.left = `${x}px`;
    popup.style.top = `${y}px`;
  }

  function showEdgePopup(edgeId, domPos) {
    const edge = allEdges.find(e => e.id === edgeId);
    if (!edge) return;
    popupEdgeId = edgeId;
    const isGroup = String(edgeId).startsWith("g2g-") || String(edgeId).startsWith("g2m-");
    const fromNode = allNodes.find(n => n.id === edge.from);
    const toNode = allNodes.find(n => n.id === edge.to);
    const fromLabel = fromNode ? fromNode.label : edge.from;
    const toLabel = toNode ? toNode.label : edge.to;
    popup.innerHTML = `
      <div class="modal-header" style="cursor: move; user-select: none; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border)">
        <h3 class="modal-title" style="font-size: 1rem">${escapeHtml(edge.label || "Relationship")}</h3>
        <button class="btn btn-ghost btn-icon btn-sm" onclick="hidePopup()">×</button>
      </div>
      <div class="modal-body" style="padding: 0.75rem 1rem">
        <div class="text-sm mb-2">
          <strong>${escapeHtml(fromLabel)}</strong>
          <span class="text-mute">→</span>
          <strong>${escapeHtml(toLabel)}</strong>
        </div>
        ${edge.title ? `<div class="text-sm text-mute mb-2">${escapeHtml(edge.title)}</div>` : ''}
        ${isGroup ? '<div class="text-xs text-mute">Group-level link (auto-generated)</div>' : `
        <div class="flex gap-2 mt-2">
          <button class="btn btn-danger btn-sm" onclick="deleteEdge('${edgeId}')">Delete</button>
        </div>`}
      </div>
    `;
    popup.style.display = "block";
    positionPopup(domPos);
  }

  function showGroupPopup(nodeId, domPos) {
    const node = allNodes.find(n => n.id === nodeId);
    if (!node) return;
    popup.innerHTML = `
      <div class="modal-header" style="cursor: move; user-select: none; padding: 0.75rem 1rem; border-bottom: 1px solid var(--border)">
        <h3 class="modal-title" style="font-size: 1rem">${escapeHtml(node.label)} (Group)</h3>
        <button class="btn btn-ghost btn-icon btn-sm" onclick="hidePopup()">×</button>
      </div>
      <div class="modal-body" style="padding: 0.75rem 1rem">
        ${node.title ? `<div class="text-sm text-mute mb-2">${escapeHtml(node.title)}</div>` : ''}
        <a class="btn btn-sm btn-primary" href="/characters/groups">Manage Group →</a>
      </div>
    `;
    popup.style.display = "block";
    positionPopup(domPos);
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
      showToast("Relationship deleted.", "success", 3000);
    } else {
      showToast(data.error || "Failed", "error", 5000);
    }
  };

  // ---- Add relationship mode ----
  window.enterAddMode = function () {
    addMode = true;
    addFirstNode = null;
    showToast("Click first node (character or group)…", "info", 4000);
    container.style.cursor = "crosshair";
  };

  function handleAddModeClick(params) {
    if (params.nodes.length === 0) {
      showToast("Click a node, not empty space.", "warning", 4000);
      return;
    }
    const nodeId = params.nodes[0];
    const node = allNodes.find(n => n.id === nodeId);
    if (!node) return;
    const nodeLabel = node.label + (node.group ? " (group)" : "");
    if (!addFirstNode) {
      addFirstNode = nodeId;
      showToast(`First: ${nodeLabel}. Click second node…`, "info", 4000);
    } else if (addFirstNode === nodeId) {
      showToast("Pick a different second node.", "warning", 4000);
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
    const fromLabel = fromN ? (fromN.label + (fromN.group ? " (group)" : "")) : fromId;
    const toLabel = toN ? (toN.label + (toN.group ? " (group)" : "")) : toId;
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
            From <strong style="color: var(--text)">${escapeHtml(fromLabel)}</strong>
            to <strong style="color: var(--text)">${escapeHtml(toLabel)}</strong>
          </div>
          <div class="form-row">
            <label class="form-label">Type</label>
            <select class="form-select" id="relType">
              ${types.map(t => `<option value="${t}">${t.replace("_", " ")}</option>`).join("")}
            </select>
          </div>
          <div class="form-row">
            <label class="form-label">Description (optional)</label>
            <textarea class="form-textarea" id="relDesc" rows="2" placeholder="e.g., 'secretly sympathizes with'"></textarea>
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
        showToast("Relationship created.", "success", 3000);
        setTimeout(() => location.reload(), 800);
      } else {
        showToast(data.error || "Failed", "error", 5000);
      }
    };
  }

  // ---- Group highlight ----
  window.highlightGroup = function (groupId) {
    if (!network) return;
    // groupId is the raw group ID from the legend
    // Node IDs in vis are "g-<groupId>"
    const groupNodeId = "g-" + groupId;
    // Find members via g2m edges
    const memberEdgeIds = allEdges
      .filter(e => String(e.id).startsWith(`g2m-${groupId}-`))
      .map(e => e.to);
    const memberIds = new Set(memberEdgeIds);
    // Dim all, then highlight members + group
    const updates = allNodes.map(n => ({
      id: n.id,
      opacity: (n.id === groupNodeId || memberIds.has(n.id)) ? 1.0 : 0.18,
    }));
    network.body.data.nodes.update(updates);
    // Dim non-member edges
    const edgeUpdates = allEdges.map(e => {
      const keep = (String(e.id).startsWith(`g2m-${groupId}-`)) ||
                   (memberIds.has(e.from) && memberIds.has(e.to));
      return { id: e.id, opacity: keep ? 1.0 : 0.08 };
    });
    network.body.data.edges.update(edgeUpdates);
    showToast(`Highlighted group. Click anywhere to reset.`, "info", 3000);
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
    showToast("Layout reset.", "info", 2500);
  };
  window.togglePhysics = function () {
    physicsOn = !physicsOn;
    network.setOptions({ physics: { enabled: physicsOn } });
    showToast(physicsOn ? "Physics resumed." : "Physics paused.", "info", 2500);
  };

  document.addEventListener("DOMContentLoaded", init);
})();
