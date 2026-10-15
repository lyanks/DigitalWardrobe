// Messages like "You are logged out." float in the corner and fade away by
// themselves. The × button closes one straight away.
const FLASH_SECONDS = 5;

function hideFlash(box) {
  box.classList.add("fading");  // CSS fades it out (transition: opacity)
  // When the fade has finished, take the box out of the page.
  box.addEventListener("transitionend", () => box.remove(), { once: true });
  // Backup in case the transition never runs (e.g. the tab was hidden).
  setTimeout(() => box.remove(), 600);
}

function startFlash(box) {
  // Errors stay twice as long: there is more to read.
  const seconds = box.classList.contains("flash-error") ? FLASH_SECONDS * 2 : FLASH_SECONDS;
  // The shrinking line under the message (CSS) uses the same number.
  box.style.setProperty("--seconds", seconds);
  const timer = setTimeout(() => hideFlash(box), seconds * 1000);

  box.querySelector(".flash-close").addEventListener("click", () => {
    clearTimeout(timer);
    hideFlash(box);
  });
}

document.querySelectorAll("[data-flash]").forEach(startFlash);

// The same message box from JavaScript, for pages that save without
// reloading (washer.js). category: "success", "info" or "error".
window.showToast = (message, category = "info") => {
  const box = document.createElement("div");
  box.className = `flash flash-${category}`;
  box.setAttribute("role", "status");
  box.innerHTML = '<span></span><button type="button" class="flash-close" aria-label="Close">×</button>';
  box.querySelector("span").textContent = message;  // textContent: never treated as HTML
  document.querySelector(".toasts").append(box);
  startFlash(box);
};
