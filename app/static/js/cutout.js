// "Cut out with AI": removes any background (a room, a bed, a street)
// right here in the browser, then uploads the finished cut-out.
//
// Why in the browser? The AI model needs more memory and CPU than the free
// server has. Your phone or laptop runs it instead, so the server only
// receives a ready PNG with a see-through background, and keeps it as it is
// (save_image in services/images.py skips its own cut-out for those).
//
// The library (@imgly/background-removal) and its model are downloaded
// only when you press the button, and the browser keeps them in its cache,
// so the second photo is much faster than the first.

const LIBRARY = "https://cdn.jsdelivr.net/npm/@imgly/background-removal@1.4.5/+esm";

const box = document.querySelector("[data-cutout]");

if (box) {
  const fileInput = box.closest("form").querySelector('input[type="file"][name="photo"]');
  const plainBox = box.closest("form").querySelector('input[name="remove_background"]');
  const runButton = box.querySelector("[data-cutout-run]");
  const status = box.querySelector(".cutout-status");
  const result = box.querySelector(".cutout-result");
  const preview = result.querySelector("img");
  let cutBlob = null;

  box.hidden = false; // without JavaScript the button would do nothing, so it starts hidden

  // The photo to work on: a newly chosen file, or else the item's current photo.
  async function sourcePhoto() {
    if (fileInput.files.length) return fileInput.files[0];
    if (box.dataset.current) return (await fetch(box.dataset.current)).blob();
    return null;
  }

  function showProgress(key, current, total) {
    // The library calls this while downloading: key says which file.
    if (key.startsWith("fetch")) {
      status.textContent = t("Downloading the AI model (only the first time): %(percent)s", {
        percent: Math.round((current / total) * 100) + "%",
      });
    } else {
      status.textContent = t("Cutting out…");
    }
  }

  runButton.addEventListener("click", async () => {
    const photo = await sourcePhoto();
    if (!photo) {
      status.textContent = t("Choose a photo first.");
      return;
    }
    runButton.disabled = true;
    result.hidden = true;
    status.textContent = t("Loading the AI tool…");
    try {
      // import() loads a JavaScript module only when this line runs.
      const { removeBackground } = await import(LIBRARY);
      // "small" model: about 45 MB, good enough for clothes, fine on phones.
      cutBlob = await removeBackground(photo, { model: "small", progress: showProgress });
      preview.src = URL.createObjectURL(cutBlob);
      result.hidden = false;
      status.textContent = t("Done. Use it, or keep the original.");
    } catch (error) {
      console.error(error);
      status.textContent = t("The AI cut-out didn't work in this browser. The photo will be saved as it is.");
    } finally {
      runButton.disabled = false;
    }
  });

  // "Use this": put the cut-out into the file box, as if you had chosen it.
  // A DataTransfer is the browser's "list of files" object; it's the only
  // way scripts are allowed to fill a file input.
  box.querySelector("[data-cutout-use]").addEventListener("click", () => {
    const files = new DataTransfer();
    files.items.add(new File([cutBlob], "cutout.png", { type: "image/png" }));
    fileInput.files = files.files;
    if (plainBox) plainBox.checked = false; // already cut out, nothing left to remove
    result.hidden = true;
    status.textContent = t("The cut-out will be saved when you press Save.");
  });

  box.querySelector("[data-cutout-discard]").addEventListener("click", () => {
    result.hidden = true;
    status.textContent = "";
  });

  // A new photo chosen: the old result no longer belongs to it. (Filling
  // the box from a script, as "Use this" does, doesn't count as a change.)
  fileInput.addEventListener("change", () => {
    result.hidden = true;
    status.textContent = "";
  });
}
