// The menu button on phones: opens and closes the nav.
// aria-expanded tells screen readers whether the menu is open.
const navToggle = document.querySelector(".nav-toggle");
const nav = document.querySelector("#site-nav");

if (navToggle && nav) {
  navToggle.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", open);
  });
}
