/* Kanban drag-and-drop (SortableJS) */
document.addEventListener("DOMContentLoaded", function () {
  const board = document.getElementById("kanbanBoard");
  if (!board || typeof Sortable === "undefined") return;

  // Initialize Sortable on each column body
  board.querySelectorAll(".kanban-column-body").forEach((colBody) => {
    Sortable.create(colBody, {
      group: "plans",
      animation: 150,
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      dragClass: "sortable-drag",
      dragoverBubble: true,
      onEnd: async function (evt) {
        // Build payload {column: [ids]} for all columns
        const ordersByColumn = {};
        board.querySelectorAll(".kanban-column-body").forEach((cb) => {
          const col = cb.dataset.column;
          ordersByColumn[col] = Array.from(cb.children)
            .map(el => el.dataset.id)
            .filter(Boolean);
        });
        const { data } = await asmFetch("/plans/reorder", {
          method: "POST",
          body: ordersByColumn
        });
        if (data.ok) {
          showToast("Plan items reordered.", "success", 1500);
          // Update counts
          board.querySelectorAll(".kanban-column").forEach((col) => {
            const colName = col.dataset.column;
            const body = col.querySelector(".kanban-column-body");
            const count = col.querySelector(".count");
            if (count && body) count.textContent = body.children.length;
          });
        } else {
          showToast(data.error || "Reorder failed", "error");
          setTimeout(() => location.reload(), 800);
        }
      }
    });
  });
});
