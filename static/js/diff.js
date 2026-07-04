/* Diff view helpers — collect for export, hunk navigation. */

function collectDiffAsText() {
  return Array.from(document.querySelectorAll(".diff-view > div"))
    .map(el => {
      const op = el.className.replace("diff-", "").split(" ")[0];
      const sign = { eq: " ", add: "+", del: "-" }[op] || " ";
      const text = el.querySelector(".diff-text").textContent;
      return sign + text;
    }).join("\n");
}
function collectDiffAsHtml() {
  return `<html><head><meta charset="utf-8"><style>
    body{font-family:monospace;line-height:1.5}
    .add{background:#dcfce7;color:#166534}
    .del{background:#fee2e2;color:#991b1b}
    .eq{color:#666}
  </style></head><body>` +
  Array.from(document.querySelectorAll(".diff-view > div"))
    .map(el => {
      const op = el.className.replace("diff-", "").split(" ")[0];
      const text = el.querySelector(".diff-text").textContent
        .replace(/&/g, "&amp;").replace(/</g, "&lt;");
      return `<div class="${op}">${escapeHtml(text)}</div>`;
    }).join("") +
  `</body></html>`;
}

// Hunk navigation
let currentHunk = 0;
const hunks = Array.from(document.querySelectorAll('.diff-view > div[data-hunk="1"]'));
function navHunk(direction) {
  if (!hunks.length) { showToast("No changed hunks.", "info", 1500); return; }
  currentHunk = (currentHunk + direction + hunks.length) % hunks.length;
  hunks[currentHunk].scrollIntoView({ behavior: "smooth", block: "center" });
  hunks[currentHunk].style.background = "var(--accent-soft)";
  setTimeout(() => {
    hunks[currentHunk].style.background = "";
  }, 1500);
  showToast(`Hunk ${currentHunk + 1} / ${hunks.length}`, "info", 1200);
}
