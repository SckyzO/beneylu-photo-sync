(function () {
  // Theme toggle: flip .dark on <html>, persist choice. Default is dark.
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      const dark = document.documentElement.classList.toggle("dark");
      try { localStorage.theme = dark ? "dark" : "light"; } catch (e) {}
    });
  }

  // Sync status polling (unchanged behavior).
  const el = document.getElementById("status");
  if (!el) return;
  async function poll() {
    try {
      const r = await fetch("/api/status");
      const s = await r.json();
      let label = s.state;
      if (s.state === "error" && s.last_error) label += " — " + s.last_error;
      else if (s.state === "idle" && s.last_run_at) {
        label += ` — ${s.downloaded} téléchargées, ${s.skipped} ignorées, ${s.errors} erreurs`;
      }
      el.textContent = label;
      el.dataset.state = s.state;
      if (s.state === "running") return setTimeout(poll, 1000);
    } catch (e) { /* keep last shown state */ }
  }
  if (el.dataset.state === "running") poll();
  const form = document.querySelector('form[action="/sync"]');
  if (form) form.addEventListener("submit", () => setTimeout(poll, 500));
})();
