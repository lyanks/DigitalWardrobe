// Adding a photo to an item: review it before saving.
//
// 1. You pick a photo. The browser shrinks it to at most 1200 px (the size
//    the server keeps anyway) so the uploads below are quick.
// 2. POST /api/photos/cutout: the server removes a plain background (the
//    same code that runs on save) and sends back a see-through PNG.
// 3. The brush editor: drag over the photo to erase more, or switch to
//    Restore to paint parts of the original back.
// 4. POST /api/photos/details (if AI is on): Claude looks at the photo and
//    the form fills in name, category, colour, seasons, styles and mood.
// 5. On Save, the edited picture replaces the chosen file in the form, so
//    the server receives exactly what you see.
//
// How the editor works: three pictures of the same size.
//   original - the photo, never changed
//   mask     - white where the photo shows, empty where it's erased
//   canvas   - what you see: the original, cut by the mask
// Erasing paints holes into the mask; restoring paints white back.

const review = document.querySelector(".photo-review");

if (review) {
  const form = review.closest("form");
  const input = form.elements.photo;
  const canvas = review.querySelector(".photo-canvas");
  const view = canvas.getContext("2d");
  const cutoutStatus = review.querySelector("[data-cutout-status]");
  const aiStatus = review.querySelector("[data-ai-status]");
  const aiAgain = review.querySelector("[data-ai-again]");
  const undoButton = review.querySelector("[data-undo]");
  const sizeInput = review.querySelector("[data-brush-size]");
  const removeBackground = form.elements.remove_background;
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const MAX_SIZE = 1200;
  const isNewItem = !form.querySelector("[data-current-photo]");

  const original = document.createElement("canvas");
  const mask = document.createElement("canvas");
  let startMask = null;      // the mask as it came from the server, for "Start over"
  let history = [];          // earlier masks, for Undo
  let brush = "erase";
  let drawing = false;
  let last = null;           // the previous point while dragging
  let photoBlob = null;      // the shrunk photo, sent to the server
  let active = false;        // true once a photo is in the editor
  let submitting = false;

  // ---------- drawing ----------

  function render() {
    view.clearRect(0, 0, canvas.width, canvas.height);
    // The erased parts show faintly, so you can see what Restore brings back.
    view.globalAlpha = 0.15;
    view.drawImage(original, 0, 0);
    view.globalAlpha = 1;
    view.drawImage(cutPicture(), 0, 0);
  }

  // The original with the mask applied: what will be saved.
  function cutPicture() {
    const out = document.createElement("canvas");
    out.width = original.width;
    out.height = original.height;
    const ctx = out.getContext("2d");
    ctx.drawImage(original, 0, 0);
    // "destination-in": keep the picture only where the mask has paint.
    ctx.globalCompositeOperation = "destination-in";
    ctx.drawImage(mask, 0, 0);
    return out;
  }

  function fillMask() {
    const ctx = mask.getContext("2d");
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, mask.width, mask.height);
  }

  function copyOf(source) {
    const copy = document.createElement("canvas");
    copy.width = source.width;
    copy.height = source.height;
    copy.getContext("2d").drawImage(source, 0, 0);
    return copy;
  }

  function setMask(source) {
    const ctx = mask.getContext("2d");
    ctx.globalCompositeOperation = "copy";  // replace, don't blend
    ctx.drawImage(source, 0, 0);
    ctx.globalCompositeOperation = "source-over";
  }

  function remember() {
    history.push(copyOf(mask));
    if (history.length > 20) history.shift();  // keep memory use small
    undoButton.disabled = false;
  }

  // Where the pointer is, in canvas pixels (the canvas is shown smaller
  // than its real size on a phone, so scale the position).
  function pointFrom(event) {
    const box = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - box.left) * (canvas.width / box.width),
      y: (event.clientY - box.top) * (canvas.height / box.height),
    };
  }

  function brushWidth() {
    // The slider is in screen pixels; turn it into canvas pixels.
    const box = canvas.getBoundingClientRect();
    return Number(sizeInput.value) * (canvas.width / box.width);
  }

  function paint(from, to) {
    const ctx = mask.getContext("2d");
    // "destination-out" punches holes; "source-over" paints white back.
    ctx.globalCompositeOperation = brush === "erase" ? "destination-out" : "source-over";
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = brushWidth();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
    ctx.globalCompositeOperation = "source-over";
    render();
  }

  // Pointer events cover mouse, finger and pen with the same code.
  canvas.addEventListener("pointerdown", (event) => {
    if (!active) return;
    canvas.setPointerCapture(event.pointerId);
    remember();
    drawing = true;
    last = pointFrom(event);
    paint(last, last);  // a single tap still paints a dot
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!drawing) return;
    const point = pointFrom(event);
    paint(last, point);
    last = point;
  });
  for (const name of ["pointerup", "pointercancel"]) {
    canvas.addEventListener(name, () => { drawing = false; });
  }

  review.querySelectorAll("[data-brush]").forEach((button) => {
    button.addEventListener("click", () => {
      brush = button.dataset.brush;
      review.querySelectorAll("[data-brush]").forEach((other) => {
        other.classList.toggle("is-active", other === button);
        other.setAttribute("aria-pressed", String(other === button));
      });
    });
  });

  undoButton.addEventListener("click", () => {
    const previous = history.pop();
    if (previous) setMask(previous);
    undoButton.disabled = history.length === 0;
    render();
  });

  review.querySelector("[data-reset]").addEventListener("click", () => {
    remember();
    if (startMask) setMask(startMask); else fillMask();
    render();
  });

  review.querySelector("[data-whole]").addEventListener("click", () => {
    remember();
    fillMask();
    render();
  });

  // ---------- loading a photo ----------

  // Shrink the photo in the browser. createImageBitmap turns phone photos
  // upright by itself (it reads the EXIF rotation).
  async function loadPhoto(file) {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIZE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);
    for (const c of [original, mask, canvas]) {
      c.width = width;
      c.height = height;
    }
    original.getContext("2d").drawImage(bitmap, 0, 0, width, height);
    bitmap.close();
    // A PNG keeps see-through parts (an already cut-out photo); others go as JPEG.
    const type = file.type === "image/png" ? "image/png" : "image/jpeg";
    return new Promise((resolve) => original.toBlob(resolve, type, 0.92));
  }

  async function post(url, blob) {
    const data = new FormData();
    data.append("photo", blob, blob.type === "image/png" ? "photo.png" : "photo.jpg");
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": csrfToken }, body: data });
  }

  async function errorText(response) {
    try {
      return (await response.json()).error;
    } catch {
      return t("Something went wrong. Try again.");
    }
  }

  async function cutOut() {
    cutoutStatus.textContent = t("Removing the background…");
    try {
      const response = await post(review.dataset.cutoutUrl, photoBlob);
      if (!response.ok) {
        cutoutStatus.textContent = await errorText(response);
        return;
      }
      const cut = await createImageBitmap(await response.blob());
      setMask(cut);  // only its see-through-ness matters for the mask
      cut.close();
      startMask = copyOf(mask);
      history = [];
      undoButton.disabled = true;
      render();
      cutoutStatus.textContent = t("Background removed. Drag over the photo to erase more, or switch to Restore.");
    } catch {
      cutoutStatus.textContent = t("Couldn't reach the server. Try again.");
    }
  }

  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file || !file.type.startsWith("image/")) return;
    try {
      photoBlob = await loadPhoto(file);
    } catch {
      return;  // the browser can't read it: the server will say why on Save
    }
    fillMask();
    startMask = null;
    history = [];
    undoButton.disabled = true;
    active = true;
    review.hidden = false;
    // The editor does the cutting now, so hide the old checkbox.
    // (style, not the hidden attribute: CSS gives .checkbox display: flex.)
    form.querySelector("[data-remove-background]").style.display = "none";
    render();
    // Both requests at once: the AI doesn't need to wait for the cut-out.
    const jobs = [cutOut()];
    if (review.dataset.detailsUrl) jobs.push(suggest());
    await Promise.all(jobs);
  });

  // ---------- AI details ----------

  // Fields you changed yourself are never overwritten by the AI.
  const touched = new Set();
  form.addEventListener("change", (event) => {
    const name = event.target.name;
    if (name && name !== "photo" && event.isTrusted) touched.add(name);
    event.target.closest(".ai-filled")?.classList.remove("ai-filled");
  });

  function mark(element) {
    element.classList.add("ai-filled");
  }

  function fillText(name, value) {
    const field = form.elements[name];
    if (!field || !value || touched.has(name) || field.value.trim()) return false;
    field.value = value;
    mark(field);
    return true;
  }

  function fillSelect(name, value) {
    const field = form.elements[name];
    if (!field || value == null || touched.has(name)) return false;
    if (!isNewItem) return false;  // editing: keep what was saved
    if (![...field.options].some((option) => option.value === String(value))) return false;
    field.value = String(value);
    mark(field);
    return true;
  }

  function fillChips(name, values) {
    const group = form.querySelector(`[data-chips="${name}"]`);
    if (!group || !values?.length || touched.has(name)) return false;
    const boxes = [...group.querySelectorAll("input")];
    if (boxes.some((box) => box.checked)) return false;  // you already picked some
    let any = false;
    for (const box of boxes) {
      if (values.includes(box.value)) {
        box.checked = true;
        any = true;
      }
    }
    if (any) mark(group);
    return any;
  }

  async function suggest() {
    aiStatus.textContent = t("Looking at the photo…");
    aiAgain.hidden = true;
    try {
      const response = await post(review.dataset.detailsUrl, photoBlob);
      if (!response.ok) {
        aiStatus.textContent = await errorText(response);
        aiAgain.hidden = response.status === 429;
        return;
      }
      const details = await response.json();
      const filled = [
        fillText("name", details.name) && t("name"),
        fillSelect("category_id", details.category_id) && t("category"),
        fillSelect("color", details.color) && t("colour"),
        fillChips("seasons", details.seasons) && t("season"),
        fillChips("styles", details.styles) && t("style"),
        fillChips("moods", details.moods) && t("mood"),
        fillText("brand", details.brand) && t("brand"),
      ].filter(Boolean);
      aiStatus.textContent = filled.length
        ? t("Suggested from the photo: %(fields)s. Check them before saving.", { fields: filled.join(", ") })
        : t("The details are already filled in, so nothing was changed.");
      aiAgain.hidden = false;
    } catch {
      aiStatus.textContent = t("Couldn't reach the server. Try again.");
      aiAgain.hidden = false;
    }
  }

  if (aiAgain) {
    aiAgain.addEventListener("click", () => {
      // "Again" means "you may change what you filled in before".
      form.querySelectorAll(".ai-filled").forEach((element) => {
        element.classList.remove("ai-filled");
        if (element.matches("[data-chips]")) {
          element.querySelectorAll("input").forEach((box) => { box.checked = false; });
        } else if (element.matches("input")) {
          element.value = "";
        }
      });
      suggest();
    });
  }

  // ---------- saving ----------

  // True if any pixel of the mask is (partly) erased.
  function hasHoles() {
    const pixels = mask.getContext("2d").getImageData(0, 0, mask.width, mask.height).data;
    for (let i = 3; i < pixels.length; i += 4) {  // every 4th number is alpha
      if (pixels[i] < 255) return true;
    }
    return false;
  }

  form.addEventListener("submit", async (event) => {
    if (!active || submitting) return;
    event.preventDefault();
    submitting = true;
    const holes = hasHoles();
    // With holes: a see-through PNG. Without: the plain photo as JPEG.
    const picture = holes ? cutPicture() : original;
    const type = holes ? "image/png" : "image/jpeg";
    const blob = await new Promise((resolve) => picture.toBlob(resolve, type, 0.92));
    // A file input can't be set directly; a DataTransfer (the object a
    // drag-and-drop carries) builds the file list for it.
    const files = new DataTransfer();
    files.items.add(new File([blob], holes ? "photo.png" : "photo.jpg", { type }));
    input.files = files.files;
    // The cutting is done; don't let the server cut the JPEG again.
    if (removeBackground) removeBackground.checked = false;
    // The form has a button called "submit", which hides form.submit(),
    // so call the browser's own method.
    HTMLFormElement.prototype.requestSubmit.call(form, event.submitter || null);
  });
}
