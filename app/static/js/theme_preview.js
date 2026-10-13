// The Look card on the profile page: show a theme or accent colour the
// moment you pick it, before you press "Save look". Nothing is saved here;
// reload the page without saving and your old look is back.

const lookForm = document.querySelector(".look-form");

if (lookForm) {
  const root = document.documentElement;  // the <html> tag
  const accent = lookForm.querySelector('input[type="color"]');
  const useTheme = lookForm.querySelector('input[type="checkbox"]');

  // Same rule as text_on() in app/themes.py: dark text on light colours.
  function textOn(hex) {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45 ? "#1d0b3a" : "#ffffff";
  }

  function showAccent() {
    if (useTheme.checked) {
      // Remove the inline colours: the theme's own come back.
      root.style.removeProperty("--color-primary");
      root.style.removeProperty("--color-on-primary");
    } else {
      root.style.setProperty("--color-primary", accent.value);
      root.style.setProperty("--color-on-primary", textOn(accent.value));
    }
  }

  lookForm.addEventListener("change", (event) => {
    if (event.target.name.endsWith("theme")) {
      root.dataset.theme = event.target.value;  // <html data-theme="...">
    }
    showAccent();
  });

  // Picking a colour means you want it, so untick "use the theme's colour".
  accent.addEventListener("input", () => {
    useTheme.checked = false;
    showAccent();
  });
}
