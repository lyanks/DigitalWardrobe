// Messages like "You are logged out." fade away by themselves.
// The × button closes one straight away.
const FLASH_SECONDS = 5;

function hideFlash(box) {
  box.classList.add("fading");  // CSS fades it out (transition: opacity)
  // When the fade has finished, take the box out of the page so the
  // content below moves up.
  box.addEventListener("transitionend", () => box.remove(), { once: true });
}

document.querySelectorAll("[data-flash]").forEach((box) => {
  // Errors stay twice as long: there is more to read.
  const seconds = box.classList.contains("flash-error") ? FLASH_SECONDS * 2 : FLASH_SECONDS;
  const timer = setTimeout(() => hideFlash(box), seconds * 1000);

  box.querySelector(".flash-close").addEventListener("click", () => {
    clearTimeout(timer);
    hideFlash(box);
  });
});
