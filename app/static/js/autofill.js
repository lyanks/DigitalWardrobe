// "Fill in from link" on the wish form (idea #4).
// JavaScript in the browser isn't allowed to read another website's page
// (the same-origin rule), so we ask our own server to do it:
// POST /api/fetch-product -> {name, price, currency, image_url}.

const box = document.querySelector(".autofill");

if (box) {
  const form = box.closest("form");
  const button = box.querySelector("[data-autofill]");
  const status = box.querySelector(".autofill-status");
  const photo = box.querySelector(".autofill-photo");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  // Put a value into a form field. A <select> only changes if it has that option.
  function setField(name, value) {
    const field = form.elements[name];
    if (!field || value == null) return false;
    if (field.tagName === "SELECT" && ![...field.options].some((o) => o.value === value)) {
      return false;
    }
    field.value = value;
    return true;
  }

  button.addEventListener("click", async () => {
    const url = form.elements.shop_url.value.trim();
    if (!url) {
      status.textContent = "Paste a link first.";
      return;
    }

    button.disabled = true;
    status.textContent = "Looking at the page…";
    try {
      const response = await fetch(box.dataset.fetchUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ url }),
      });
      const data = await response.json();
      if (!response.ok) {
        status.textContent = data.error;
        return;
      }

      // Fill what was found. The name only if you haven't typed one.
      const filled = [];
      let note = "";
      if (data.name && !form.elements.name.value.trim()) {
        setField("name", data.name);
        filled.push("name");
      }
      if (setField("price", data.price)) filled.push("price");
      if (data.currency && !setField("currency", data.currency)) {
        note = ` The price is in ${data.currency}, which isn't in the list.`;
      }
      if (data.image_url) {
        setField("image_url", data.image_url);  // the server downloads it on Save
        photo.src = data.image_url;
        photo.hidden = false;
        filled.push("photo");
      }

      status.textContent = filled.length
        ? `Filled in: ${filled.join(", ")}. Check it, then pick a category and colour.` + note
        : "The page had no details we could read. Fill the form in by hand.";
    } catch {
      status.textContent = "Something went wrong. Try again, or fill the form in by hand.";
    } finally {
      button.disabled = false;
    }
  });
}
