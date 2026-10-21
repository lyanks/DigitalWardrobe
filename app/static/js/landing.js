// The landing page intro:
// 1. "Your wardrobe, organised." types itself, letter by letter.
// 2. The purple "thoughtfully" opens a gap between the words and fades in.
// 3. The buttons slide up.
//
// The text is in the page from the start, only see-through. Typing makes
// one letter at a time visible, so nothing moves around while it types.

const title = document.querySelector("[data-typing]");

if (title && document.documentElement.classList.contains("landing-intro")) {
  const LETTER_MS = 55;  // one letter
  const PAUSE_MS = 250;  // between "Your wardrobe," and "organised."
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // With "thoughtfully" in, the title may need an extra line. Measure that
  // height now and keep it from the start, so the page never jumps.
  const word = title.querySelector("[data-reveal]");
  word.style.maxWidth = "none";
  title.style.minHeight = `${title.offsetHeight}px`;
  word.style.maxWidth = "";

  const caret = document.createElement("span");
  caret.className = "type-caret";
  caret.setAttribute("aria-hidden", "true");

  // Split each part into "typed" (visible) and "rest" (see-through).
  const parts = [...title.querySelectorAll("[data-type]")].map((part) => {
    const text = part.textContent;
    part.innerHTML = '<span class="typed"></span><span class="rest"></span>';
    part.querySelector(".rest").textContent = text;
    return { part, text };
  });

  async function typeOut({ part, text }) {
    const typed = part.querySelector(".typed");
    const rest = part.querySelector(".rest");
    typed.after(caret);
    for (let i = 1; i <= text.length; i += 1) {
      typed.textContent = text.slice(0, i);
      rest.textContent = text.slice(i);
      await wait(LETTER_MS);
    }
  }

  async function play() {
    await wait(400);  // let the tagline fade in first
    for (const [index, part] of parts.entries()) {
      if (index) await wait(PAUSE_MS);
      await typeOut(part);
    }
    await wait(350);
    caret.classList.add("done");  // the caret fades away

    // Open the gap to the exact width of the word, then fade it in.
    word.style.maxWidth = `${word.scrollWidth}px`;
    word.classList.add("shown");
    await wait(700);
    document.documentElement.classList.add("landing-done");  // buttons slide up
  }

  play();
}
