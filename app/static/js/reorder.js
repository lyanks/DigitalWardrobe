// Drag and drop to reorder the wardrobe grid ("My order" only).
//
// 1. While you drag, the card moves around in the page (the DOM) only.
// 2. When you let go, we read the new order of the cards and send it to
//    Flask with fetch(). Flask saves it, so the order survives a reload.

const grid = document.querySelector("[data-reorder-url]");

if (grid) {
  const status = document.querySelector(".reorder-status");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  let dragged = null;
  let orderBefore = "";

  const currentOrder = () =>
    [...grid.querySelectorAll(".item-card")].map((card) => Number(card.dataset.id));

  grid.addEventListener("dragstart", (event) => {
    dragged = event.target.closest(".item-card");
    if (!dragged) return;
    orderBefore = currentOrder().join(",");
    event.dataTransfer.effectAllowed = "move";
    // Firefox only starts a drag if some data is set.
    event.dataTransfer.setData("text/plain", dragged.dataset.id);
    // Wait one frame so the "ghost" image is taken before we fade the card.
    requestAnimationFrame(() => dragged.classList.add("dragging"));
  });

  grid.addEventListener("dragover", (event) => {
    if (!dragged) return;
    event.preventDefault(); // "yes, you may drop here"
    const target = event.target.closest(".item-card");
    if (!target || target === dragged) return;

    // Left half of a card: put the dragged card before it. Right half: after.
    const box = target.getBoundingClientRect();
    const after = event.clientX > box.left + box.width / 2;
    grid.insertBefore(dragged, after ? target.nextSibling : target);
  });

  // Without this, dropping a link would make the browser open it.
  grid.addEventListener("drop", (event) => event.preventDefault());

  grid.addEventListener("dragend", async () => {
    if (!dragged) return;
    dragged.classList.remove("dragging");
    dragged = null;

    const ids = currentOrder();
    if (ids.join(",") === orderBefore) return; // dropped where it was

    status.textContent = "Saving…";
    try {
      const response = await fetch(grid.dataset.reorderUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ ids }),
      });
      if (!response.ok) throw new Error(`Server answered ${response.status}`);
      status.textContent = "Order saved.";
    } catch (error) {
      status.textContent = "Couldn't save the new order. Reloading…";
      setTimeout(() => location.reload(), 1500);
    }
  });
}
