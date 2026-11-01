// Applies the saved theme before first paint. A file, not inline, so the
// Content-Security-Policy can forbid inline scripts.
(function () {
  try {
    var pref = localStorage.getItem("ee-theme") || "system";
    var dark =
      pref === "dark" ||
      (pref === "system" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
  } catch (e) {}
})();
