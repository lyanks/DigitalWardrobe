// Buttons with data-copy="text": copy that text and say so.
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    window.showToast(t("Copied: %(text)s", { text: button.dataset.copy }), "success");
  } catch {
    window.showToast(t("Couldn't copy. Select the code and copy it by hand."), "error");
  }
});
