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

  // Lightbox: intercept thumbnail clicks, show an in-page overlay with prev/next.
  (function () {
    const photos = Array.prototype.slice.call(document.querySelectorAll("a.js-photo"));
    if (!photos.length) return;

    function makeBtn(lb, label, cls, text) {
      const b = document.createElement("button");
      b.setAttribute("data-lb", lb);
      b.setAttribute("aria-label", label);
      b.className = cls;
      b.textContent = text;
      return b;
    }

    const overlay = document.createElement("div");
    overlay.id = "lightbox";
    overlay.className = "fixed inset-0 z-[100] hidden items-center justify-center bg-black/80 p-4";

    const img = document.createElement("img");
    img.alt = "";
    img.className = "max-h-[90vh] max-w-[90vw] rounded-lg object-contain";

    overlay.appendChild(makeBtn("prev", "Précédent", "absolute left-4 top-1/2 -translate-y-1/2 px-4 py-2 text-3xl text-white/80 hover:text-white", "‹"));
    overlay.appendChild(img);
    overlay.appendChild(makeBtn("next", "Suivant", "absolute right-4 top-1/2 -translate-y-1/2 px-4 py-2 text-3xl text-white/80 hover:text-white", "›"));
    overlay.appendChild(makeBtn("close", "Fermer", "absolute right-4 top-4 px-3 py-1 text-2xl text-white/80 hover:text-white", "✕"));
    document.body.appendChild(overlay);

    let group = [];
    let index = 0;

    function show(i) {
      index = (i + group.length) % group.length;
      const a = group[index];
      img.src = a.getAttribute("data-full") || a.getAttribute("href");
      img.alt = a.getAttribute("data-name") || "";
    }
    function open(a) {
      const container = a.closest("[data-lightbox-group]");
      group = container
        ? Array.prototype.slice.call(container.querySelectorAll("a.js-photo"))
        : [a];
      overlay.classList.remove("hidden");
      overlay.classList.add("flex");
      show(group.indexOf(a));
    }
    function close() {
      overlay.classList.add("hidden");
      overlay.classList.remove("flex");
      img.src = "";
    }

    photos.forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        open(a);
      });
    });
    overlay.addEventListener("click", function (e) {
      const act = e.target.getAttribute && e.target.getAttribute("data-lb");
      if (act === "next") show(index + 1);
      else if (act === "prev") show(index - 1);
      else if (act === "close" || e.target === overlay) close();
    });
    document.addEventListener("keydown", function (e) {
      if (overlay.classList.contains("hidden")) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") show(index + 1);
      else if (e.key === "ArrowLeft") show(index - 1);
    });
  })();
})();
