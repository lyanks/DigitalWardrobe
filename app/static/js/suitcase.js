// The pack page: drag clothes (or a whole outfit) from your wardrobe on the
// right into the suitcase on the left, and drag them back out to remove.
//
// Every button on the page is also a normal form, so the page works without
// this file. Here we send the same requests with fetch() and ask for JSON
// (Accept: application/json), then update the page instead of reloading it.

const suitcase = document.querySelector("[data-suitcase]");

if (suitcase) {
  const list = suitcase.querySelector("[data-drop]");
  const wardrobe = document.querySelector(".pack-wardrobe");
  const status = suitcase.querySelector(".suitcase-status");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  // The routes were rendered with id 0; swap in the real id.
  const urlFor = (template, id) => template.replace(/\/0$/, `/${id}`);
  const cardFor = (id) => wardrobe.querySelector(`.pack-card[data-item-id="${id}"]`);

  async function send(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
      body,
    });
    if (!response.ok) throw new Error(response.status);
    return response.json();
  }

  // After any change: "3 of 7 packed", the progress bar, the empty hint.
  function showCounts({ count, packed }) {
    suitcase.querySelector("[data-count]").textContent = count
      ? t("%(packed)s of %(count)s packed", { packed, count }) : t("Empty");
    suitcase.querySelector("[data-bar]").style.setProperty("--width", `${count ? (packed / count) * 100 : 0}%`);
    suitcase.querySelector(".suitcase-empty").hidden = count > 0;
  }

  function added(data) {
    list.insertAdjacentHTML("beforeend", data.html);
    data.added.forEach((id) => cardFor(id)?.classList.add("in-suitcase"));
    showCounts(data);
    status.textContent = data.added.length ? "" : t("Already in the suitcase.");
  }

  function removed(data) {
    list.querySelector(`[data-item-id="${data.removed}"]`)?.remove();
    cardFor(data.removed)?.classList.remove("in-suitcase");
    showCounts(data);
  }

  function packed(data) {
    const row = list.querySelector(`[data-item-id="${data.item}"]`);
    row.classList.toggle("is-packed", data.is_packed);
    row.querySelector(".pack-check").setAttribute("aria-pressed", data.is_packed);
    showCounts(data);
  }

  const handlers = { add: added, remove: removed, packed };

  // 1. The buttons: send the form with fetch instead of reloading.
  document.addEventListener("submit", (event) => {
    const form = event.target;
    const action = form.dataset.suitcaseAction;
    if (!action) return;
    event.preventDefault();
    send(form.action, new FormData(form))
      .then(handlers[action])
      .catch(() => (status.textContent = t("Couldn't save that. Try again.")));
  });

  // 2. Dragging. What is being dragged goes into dataTransfer as text:
  //    "item:12" or "outfit:3" from the right, "out:12" from the suitcase.
  document.addEventListener("dragstart", (event) => {
    const card = event.target.closest?.(".pack-card");
    const chip = event.target.closest?.(".outfit-chip");
    const row = event.target.closest?.(".suitcase-item");
    const what = card ? `item:${card.dataset.itemId}`
      : chip ? `outfit:${chip.dataset.outfitId}`
      : row ? `out:${row.dataset.itemId}` : null;
    if (!what) return;
    event.dataTransfer.setData("text/plain", what);
    event.dataTransfer.effectAllowed = "move";
    document.body.classList.add(row ? "dragging-out" : "dragging-in");
  });
  document.addEventListener("dragend", () => {
    document.body.classList.remove("dragging-in", "dragging-out");
    suitcase.classList.remove("drop-target");
  });

  // 3. The suitcase accepts things from the wardrobe...
  suitcase.addEventListener("dragover", (event) => {
    if (!document.body.classList.contains("dragging-in")) return;
    event.preventDefault();  // "yes, you may drop here"
    suitcase.classList.add("drop-target");
  });
  suitcase.addEventListener("dragleave", (event) => {
    if (!suitcase.contains(event.relatedTarget)) suitcase.classList.remove("drop-target");
  });
  suitcase.addEventListener("drop", (event) => {
    event.preventDefault();
    suitcase.classList.remove("drop-target");
    const [kind, id] = event.dataTransfer.getData("text/plain").split(":");
    const url = kind === "item" ? urlFor(suitcase.dataset.addUrl, id)
      : kind === "outfit" ? urlFor(suitcase.dataset.outfitUrl, id) : null;
    if (url) send(url).then(added).catch(() => (status.textContent = t("Couldn't save that. Try again.")));
  });

  // ...and the wardrobe side takes things back out of the suitcase.
  wardrobe.addEventListener("dragover", (event) => {
    if (document.body.classList.contains("dragging-out")) event.preventDefault();
  });
  wardrobe.addEventListener("drop", (event) => {
    const [kind, id] = event.dataTransfer.getData("text/plain").split(":");
    if (kind !== "out") return;
    event.preventDefault();
    const form = list.querySelector(`[data-item-id="${id}"] [data-suitcase-action="remove"]`);
    send(form.action, new FormData(form)).then(removed);
  });
}
