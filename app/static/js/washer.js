// The washer on the wardrobe page: drag a card onto it and that item goes
// in the wash, without opening the item. The page doesn't reload: we send
// the same request as the "Put in the wash" button, ask for JSON, then fade
// the card and add the "In the wash" badge ourselves.

const washer = document.querySelector("[data-washer]");

if (washer) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const count = washer.querySelector("[data-washer-count]");
  const TYPE = "application/x-wardrobe-item";  // our own kind of drag data
  let dragged = null;

  // Any card can be picked up. (In "My order" reorder.js also listens.)
  document.addEventListener("dragstart", (event) => {
    dragged = event.target.closest?.(".item-card[data-item-id]");
    if (!dragged) return;
    event.dataTransfer.setData(TYPE, dragged.dataset.itemId);
    document.body.classList.add("dragging-item");
  });
  document.addEventListener("dragend", () => {
    document.body.classList.remove("dragging-item");
    washer.classList.remove("drop-target");
    dragged = null;
  });

  washer.addEventListener("dragover", (event) => {
    if (!event.dataTransfer.types.includes(TYPE)) return;
    event.preventDefault();  // "yes, you may drop here"
    event.dataTransfer.dropEffect = "move";
    washer.classList.add("drop-target");
  });
  washer.addEventListener("dragleave", () => washer.classList.remove("drop-target"));

  washer.addEventListener("drop", async (event) => {
    event.preventDefault();
    const id = event.dataTransfer.getData(TYPE);
    const card = dragged;
    if (card) card.dataset.droppedInWasher = "1";  // tells reorder.js not to save

    const body = new FormData();
    body.append("csrf_token", csrfToken);
    body.append("state", "in");
    try {
      const response = await fetch(washer.dataset.url.replace(/\/0\//, `/${id}/`), {
        method: "POST",
        headers: { Accept: "application/json" },
        body,
      });
      if (!response.ok) throw new Error(response.status);
      const data = await response.json();
      markWashing(card);
      count.textContent = data.washing;
      count.hidden = data.washing === 0;
      washer.classList.remove("spin");
      void washer.offsetWidth;  // restart the animation if it's still running
      washer.classList.add("spin");
      showToast(data.message, "info");
    } catch {
      showToast(t("Couldn't put that in the wash. Try again."), "error");
    }
  });

  function markWashing(card) {
    if (!card || card.classList.contains("washing")) return;
    card.classList.add("washing");
    const badge = document.createElement("span");
    badge.className = "wash-badge wash-badge-corner";
    badge.textContent = t("In the wash");
    card.querySelector(".item-photo").after(badge);
  }
}
