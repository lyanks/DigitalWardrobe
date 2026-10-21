// The eye button next to a password box: click it to see what you typed,
// click again to hide it. Switching the input's type between "password"
// and "text" is all it takes.
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-toggle-password]");
  if (!button) return;

  const input = button.parentElement.querySelector("input");
  const show = input.type === "password";
  input.type = show ? "text" : "password";

  // Tell screen readers (and the CSS) which state the button is in.
  button.setAttribute("aria-pressed", String(show));
  button.setAttribute("aria-label", t(show ? "Hide password" : "Show password"));
});
