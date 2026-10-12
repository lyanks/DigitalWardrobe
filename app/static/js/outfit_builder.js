// The outfit builder, live: every time you tick or untick an item,
//  - the preview strip shows the ticked items, and
//  - we ask Flask (POST /api/outfits/check) whether the outfit is complete,
//    and show the answer under the preview.
// The rules stay in Python (services/outfit_rules.py): JavaScript only asks.

const picker = document.querySelector("[data-check-url]");

if (picker) {
  const preview = document.querySelector(".builder-preview");
  const strip = preview.querySelector(".preview-strip");
  const verdict = preview.querySelector(".preview-verdict");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  let latestRequest = 0;

  const tickedBoxes = () => [...picker.querySelectorAll('input[name="item_ids"]:checked')];

  function drawPreview(boxes) {
    // Copy each ticked card's picture into the strip. cloneNode makes a
    // copy, so the original stays in the picker.
    strip.replaceChildren(
      ...boxes.map((box) => {
        const card = box.closest(".pick-card");
        const tile = document.createElement("div");
        tile.className = "preview-tile";
        tile.title = card.querySelector(".pick-name").textContent;
        tile.append(card.querySelector(".item-photo").cloneNode(true));
        return tile;
      })
    );
  }

  async function check(boxes) {
    const requestNumber = ++latestRequest;
    const response = await fetch(picker.dataset.checkUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ item_ids: boxes.map((box) => Number(box.value)) }),
    });
    // Clicking fast sends several requests; only the newest answer counts.
    if (requestNumber !== latestRequest || !response.ok) return;
    const { problems } = await response.json();
    verdict.textContent = problems.length ? problems.join(" ") : "Looks like a complete outfit ✓";
    verdict.classList.toggle("ok", problems.length === 0);
  }

  function update() {
    const boxes = tickedBoxes();
    preview.hidden = false;
    drawPreview(boxes);
    check(boxes).catch(() => (verdict.textContent = ""));
  }

  picker.addEventListener("change", (event) => {
    if (event.target.name === "item_ids") update();
  });
  // On the edit page (or after a form error) some boxes start ticked.
  if (tickedBoxes().length) update();
}
