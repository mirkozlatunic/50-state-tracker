// The light/dark switch in the header.
//
// The page is dark when <html> has data-theme="dark", or when it has no
// data-theme and the device is in dark mode. Pressing the button picks the
// other theme and saves it in a cookie, so Flask can put it straight into the
// next page (no white flash).

const root = document.documentElement;
const themeButton = document.querySelector(".theme-toggle");

// Which theme is showing right now: a saved choice, or else the device setting.
// matchMedia() asks the browser the same question the CSS @media rule asks.
function currentTheme() {
  const saved = root.getAttribute("data-theme");
  if (saved) {
    return saved;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// The button shows the theme you'd switch to.
function updateThemeButton() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  themeButton.textContent = next === "dark" ? "☾ Dark" : "☀ Light";
  themeButton.setAttribute("aria-label", "Switch to " + next + " mode");
}

themeButton.addEventListener("click", function () {
  const next = currentTheme() === "dark" ? "light" : "dark";
  root.setAttribute("data-theme", next);
  // Remember it for a year (max-age is in seconds) on every page (path=/).
  document.cookie = "theme=" + next + "; path=/; max-age=31536000; SameSite=Lax";
  updateThemeButton();
});

updateThemeButton();
