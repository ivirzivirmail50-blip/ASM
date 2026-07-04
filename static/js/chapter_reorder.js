/* Chapter drag-and-drop reorder (SortableJS) */
document.addEventListener("DOMContentLoaded", function () {
  const list = document.getElementById("chapterList");
  if (!list || typeof Sortable === "undefined") return;
  Sortable.create(list, {
    animation: 150,
    ghostClass: "sortable-ghost",
    chosenClass: "sortable-chosen",
    dragClass: "sortable-drag",
    handle: ".drag-handle",
    filter: ".no-drag",
    onEnd: async function (evt) {
      const ids = Array.from(list.children).map(el => el.dataset.id);
      const oldIndex = evt.oldDraggedIndex || evt.oldIndex;
      // Optimistic: keep new order; revert if save fails
      const { data } = await asmFetch("/chapters/reorder", {
        method: "POST",
        body: { order: ids }
      });
      if (data.ok) {
        showToast("Chapters reordered.", "success", 1500);
        pushUndo("Reorder chapters",
          () => { /* would need previous order */ },
          () => { /* same */ });
      } else {
        showToast(data.error || "Reorder failed", "error");
        // Reload to revert
        setTimeout(() => location.reload(), 800);
      }
    }
  });
});
