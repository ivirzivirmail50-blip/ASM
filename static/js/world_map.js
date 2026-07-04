/* World Map interactive logic — zoom, pan, pins, image upload. */

let addPinMode = false;
let mapZoom = 1;
let mapPanX = 0, mapPanY = 0;
let isPanning = false;
let panStartX = 0, panStartY = 0;
let panStartPanX = 0, panStartPanY = 0;

const viewport = document.getElementById("mapViewport");
const container = document.getElementById("mapContainer");

// ---- Zoom via mouse wheel ----
container.addEventListener("wheel", (e) => {
  e.preventDefault();
  const delta = e.deltaY > 0 ? -0.1 : 0.1;
  zoomMap(delta);
}, { passive: false });

function zoomMap(delta) {
  mapZoom = Math.max(0.5, Math.min(3, mapZoom + delta));
  applyTransform();
}

function resetZoom() {
  mapZoom = 1; mapPanX = 0; mapPanY = 0;
  applyTransform();
}

function applyTransform() {
  viewport.style.transform = `translate(${mapPanX}px, ${mapPanY}px) scale(${mapZoom})`;
}

// ---- Pan via drag on background ----
container.addEventListener("mousedown", (e) => {
  if (e.target.closest(".world-map-pin")) return;  // don't pan when clicking a pin
  if (addPinMode) return;
  isPanning = true;
  panStartX = e.clientX;
  panStartY = e.clientY;
  panStartPanX = mapPanX;
  panStartPanY = mapPanY;
  container.style.cursor = "grabbing";
});
document.addEventListener("mousemove", (e) => {
  if (!isPanning) return;
  mapPanX = panStartPanX + (e.clientX - panStartX);
  mapPanY = panStartPanY + (e.clientY - panStartY);
  applyTransform();
});
document.addEventListener("mouseup", () => {
  if (isPanning) {
    isPanning = false;
    container.style.cursor = "";
  }
});

// ---- Add pin mode ----
function enterAddPinMode() {
  addPinMode = true;
  showToast("Click on the map to place a pin…", "info", 0);
  container.style.cursor = "crosshair";
}

container.addEventListener("click", (e) => {
  if (!addPinMode) return;
  if (e.target.closest(".world-map-pin")) return;
  const rect = viewport.getBoundingClientRect();
  // Convert click position to percentage (accounting for zoom/pan)
  const x = ((e.clientX - rect.left - mapPanX) / rect.width / mapZoom) * 100;
  const y = ((e.clientY - rect.top - mapPanY) / rect.height / mapZoom) * 100;
  if (x < 0 || x > 100 || y < 0 || y > 100) {
    showToast("Click within the map area.", "warning");
    return;
  }
  addPinMode = false;
  container.style.cursor = "";
  // Show selection modal
  const entries = {{ entries | map(attribute='id') | list | tojson }};
  const names = {{ entries | map(attribute='name') | list | tojson }};
  const html = entries.map((id, i) => `<option value="${id}">${names[i]}</option>`).join("");
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <div class="modal-header"><h3 class="modal-title">Place a pin</h3></div>
      <div class="modal-body">
        <div class="text-sm text-dim mb-3">Position: x=${x.toFixed(1)}%, y=${y.toFixed(1)}%</div>
        <div class="form-row">
          <label class="form-label">Select location</label>
          <select id="pinSelect" class="form-select">${html}</select>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn" data-act="cancel">Cancel</button>
        <button class="btn btn-primary" data-act="ok">Place</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector('[data-act="cancel"]').onclick = () => backdrop.remove();
  backdrop.querySelector('[data-act="ok"]').onclick = async () => {
    const id = document.getElementById("pinSelect").value;
    const { data } = await asmFetch("/world/map/pin", {
      method: "POST", body: { id, x, y }
    });
    backdrop.remove();
    if (data.ok) {
      showToast("Pin placed.", "success");
      setTimeout(() => location.reload(), 500);
    } else {
      showToast(data.error || "Failed", "error");
    }
  };
});

// ---- Pin dragging ----
document.querySelectorAll(".world-map-pin").forEach((pin) => {
  let dragging = false;
  pin.addEventListener("mousedown", (e) => {
    dragging = true;
    e.stopPropagation();
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const rect = viewport.getBoundingClientRect();
    const x = ((e.clientX - rect.left - mapPanX) / rect.width / mapZoom) * 100;
    const y = ((e.clientY - rect.top - mapPanY) / rect.height / mapZoom) * 100;
    pin.style.left = `${x}%`;
    pin.style.top = `${y}%`;
  });
  document.addEventListener("mouseup", async () => {
    if (!dragging) return;
    dragging = false;
    const x = parseFloat(pin.style.left);
    const y = parseFloat(pin.style.top);
    await asmFetch("/world/map/pin", {
      method: "POST", body: { id: pin.dataset.id, x, y }
    });
    showToast("Pin saved.", "success", 1200);
  });
  // Click pin → popup
  pin.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = pin.dataset.id;
    const name = pin.querySelector(".pin-label").textContent;
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <div class="modal-header"><h3 class="modal-title">${escapeHtml(name)}</h3></div>
        <div class="modal-body">
          <div class="text-sm text-dim">Pin position: ${parseFloat(pin.style.left).toFixed(1)}%, ${parseFloat(pin.style.top).toFixed(1)}%</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-danger" data-act="remove">Remove Pin</button>
          <a class="btn btn-primary" href="/world/${id}">View Location →</a>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    backdrop.querySelector('[data-act="remove"]').onclick = async () => {
      const { data } = await asmFetch("/world/map/pin", {
        method: "POST", body: { id, x: null, y: null }
      });
      if (data.ok) {
        pin.remove();
        backdrop.remove();
        showToast("Pin removed.", "success", 1200);
      }
    };
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });
  });
});

// ---- Map image upload ----
async function uploadMapImage(input) {
  if (!input.files.length) return;
  const fd = new FormData();
  fd.append("file", input.files[0], input.files[0].name);
  fd.append("csrf_token", getCsrfToken());
  showToast("Uploading…", "info", 0);
  try {
    const res = await fetch("/world/map/upload", {
      method: "POST",
      headers: { "X-CSRFToken": getCsrfToken() },
      body: fd
    });
    let data;
    try { data = await res.json(); }
    catch { data = { ok: false, error: "Server returned an error (status " + res.status + ")" }; }
    if (data.ok) {
      showToast("Map uploaded! Reloading…", "success");
      setTimeout(() => location.reload(), 600);
    } else {
      showToast(data.error || "Upload failed", "error", 5000);
    }
  } catch (err) {
    showToast("Upload failed: " + err.message, "error", 5000);
  }
}

// ---- Placeholder canvas (if no image) ----
{% if not map_image_path %}
(function() {
  const canvas = document.getElementById("mapCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  const gradient = ctx.createRadialGradient(canvas.width/2, canvas.height/2, 100, canvas.width/2, canvas.height/2, canvas.width/1.5);
  gradient.addColorStop(0, "rgba(99, 102, 241, 0.05)");
  gradient.addColorStop(1, "rgba(11, 16, 32, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "rgba(108, 115, 153, 0.15)";
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += 50) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += 50) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
  }
  ctx.fillStyle = "rgba(154, 163, 199, 0.4)";
  ctx.font = "14px Inter";
  ctx.textAlign = "center";
  ctx.fillText("(Click 🖼 Upload Map Image to add a background)", canvas.width/2, canvas.height/2);
})();
{% endif %}
