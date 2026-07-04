/* Outline drag-and-drop (nested SortableJS) with real persistence */
document.addEventListener("DOMContentLoaded", () => {
  const trees = document.querySelectorAll(".outline-tree");
  if (!trees.length || typeof Sortable === "undefined") return;

  trees.forEach((tree) => {
    Sortable.create(tree, {
      group: "outline",
      animation: 150,
      fallbackOnBody: true,
      swapThreshold: 0.65,
      handle: ".drag-handle",
      ghostClass: "sortable-ghost",
      chosenClass: "sortable-chosen",
      onEnd: async (evt) => {
        // Walk the entire outline DOM and build {id, parent_id, sort_order} list
        const items = [];
        const root = document.querySelector(".outline-tree");
        if (!root) return;

        function walkList(ul, parentId) {
          const children = ul.children;
          for (let i = 0; i < children.length; i++) {
            const li = children[i];
            const id = li.dataset.id;
            if (id) {
              items.push({ id, parent_id: parentId, sort_order: i + 1 });
            }
            // Recurse into nested ul
            const nested = li.querySelector(":scope > .outline-tree");
            if (nested) walkList(nested, id);
          }
        }
        walkList(root, null);

        const { data } = await asmFetch("/plans/reorder-nested", {
          method: "POST",
          body: { items }
        });
        if (data.ok) {
          showToast("Outline saved.", "success", 1500);
        } else {
          showToast(data.error || "Save failed", "error");
        }
      }
    });
  });
});
