// "Are you sure?" as a box in the middle of the page instead of the
// browser's grey confirm() pop-up.
//
// Put it on anything that deletes:
//   <form data-confirm="Your clothes stay." data-confirm-title="Delete this trip?">
//   <a href="/items/3/delete" data-confirm="..." data-confirm-title="...">
// A form is sent after "Delete". A link sends a POST to its address (the same
// thing the "Are you sure?" page would do). Without JavaScript the form just
// sends and the link opens that page, so nothing breaks.

const dialog = document.createElement("dialog");
dialog.className = "confirm-box";
dialog.innerHTML = `
  <form method="dialog">
    <h2 class="confirm-title"></h2>
    <p class="confirm-text muted"></p>
    <div class="confirm-actions">
      <button value="cancel" class="button button-outline">Cancel</button>
      <button value="yes" class="button button-danger">Delete</button>
    </div>
  </form>`;
document.body.append(dialog);

let onYes = null;

function ask(element, yes) {
  dialog.querySelector(".confirm-title").textContent = element.dataset.confirmTitle || "Are you sure?";
  dialog.querySelector(".confirm-text").textContent = element.dataset.confirm;
  dialog.querySelector('[value="yes"]').textContent = element.dataset.confirmButton || "Delete";
  onYes = yes;
  dialog.showModal();  // centred, page behind it dimmed, Esc closes it
  dialog.querySelector('[value="cancel"]').focus();  // the safe choice first
}

// <form method="dialog"> closes the box; returnValue is the button's value.
dialog.addEventListener("close", () => {
  if (dialog.returnValue === "yes" && onYes) onYes();
  onYes = null;
});

// A click on the dimmed background is a "Cancel" too.
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close("cancel");
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form.matches("form[data-confirm]")) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  ask(form, () => HTMLFormElement.prototype.submit.call(form));  // submit() skips this listener
}, true);

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-confirm]");
  if (!link) return;
  event.preventDefault();
  ask(link, () => {
    const form = document.createElement("form");
    form.method = "post";
    form.action = link.href;
    form.innerHTML = '<input type="hidden" name="csrf_token">';
    form.firstChild.value = document.querySelector('meta[name="csrf-token"]').content;
    document.body.append(form);
    form.submit();
  });
});
