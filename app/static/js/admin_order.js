// Admin options: drag a row up or down, then the new order is saved.
// Same idea as reorder.js on the wardrobe: move the row in the page while
// dragging, and on drop send the ids in their new order to Flask.

const list = document.querySelector("[data-order-url]");

if (list) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  let dragged = null;
  let before = "";

  const ids = () => [...list.children].map((row) => Number(row.dataset.id));

  list.addEventListener("dragstart", (event) => {
    dragged = event.target.closest(".option-row");
    if (!dragged) return;
    before = ids().join(",");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", dragged.dataset.id);
    requestAnimationFrame(() => dragged.classList.add("dragging"));
  });

  list.addEventListener("dragover", (event) => {
    if (!dragged) return;
    event.preventDefault();
    const over = event.target.closest(".option-row");
    if (!over || over === dragged) return;
    // Upper half of the row: put it before; lower half: after.
    const box = over.getBoundingClientRect();
    const after = event.clientY > box.top + box.height / 2;
    over[after ? "after" : "before"](dragged);
  });

  list.addEventListener("dragend", async () => {
    if (!dragged) return;
    dragged.classList.remove("dragging");
    dragged = null;
    if (ids().join(",") === before) return;
    try {
      const response = await fetch(list.dataset.orderUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ ids: ids() }),
      });
      if (!response.ok) throw new Error();
      window.showToast(t("Order saved."), "success");
    } catch {
      window.showToast(t("Couldn't save the new order. Reloading…"), "error");
      setTimeout(() => location.reload(), 1200);
    }
  });
}
