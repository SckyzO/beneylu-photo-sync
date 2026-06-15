(function () {
  const el = document.getElementById("status");
  if (!el) return;
  async function poll() {
    try {
      const r = await fetch("/api/status");
      const s = await r.json();
      el.textContent = s.state + (s.last_error ? " — " + s.last_error : "");
      el.dataset.state = s.state;
      if (s.state === "running") return setTimeout(poll, 1000);
    } catch (e) { /* keep last shown state */ }
  }
  if (el.dataset.state === "running") poll();
  const form = document.querySelector('form[action="/sync"]');
  if (form) form.addEventListener("submit", () => setTimeout(poll, 500));
})();
