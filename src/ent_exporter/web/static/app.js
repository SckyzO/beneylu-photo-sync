(function () {
  // Theme toggle: flip .dark on <html>, persist choice. Default is dark.
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      const dark = document.documentElement.classList.toggle("dark");
      try { localStorage.theme = dark ? "dark" : "light"; } catch (e) {}
    });
  }

  // Gallery search: live client-side filter over sections by board/month/section
  // title. Hides empty months and boards, shows an empty-state when nothing matches.
  (function () {
    const input = document.getElementById("gallery-search");
    if (!input) return;
    const sections = Array.prototype.slice.call(document.querySelectorAll(".js-section"));
    const months = Array.prototype.slice.call(document.querySelectorAll(".js-month"));
    const boards = Array.prototype.slice.call(document.querySelectorAll(".js-board"));
    const empty = document.getElementById("search-empty");

    // Accent-insensitive: "mathemat" must match "En mathématiques".
    function norm(s) {
      return (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    }
    function visibleChild(parent, selector) {
      return Array.prototype.slice
        .call(parent.querySelectorAll(selector))
        .some(function (n) { return !n.classList.contains("hidden"); });
    }
    function apply() {
      const q = norm(input.value.trim());
      let anySection = false;
      sections.forEach(function (s) {
        const hit = !q || norm(s.getAttribute("data-search")).indexOf(q) !== -1;
        s.classList.toggle("hidden", !hit);
        if (hit) anySection = true;
      });
      months.forEach(function (m) {
        m.classList.toggle("hidden", !visibleChild(m, ".js-section"));
      });
      boards.forEach(function (b) {
        b.classList.toggle("hidden", !visibleChild(b, ".js-section"));
      });
      if (empty) empty.classList.toggle("hidden", anySection);
    }
    input.addEventListener("input", apply);
  })();

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
    overlay.className = "fixed inset-0 z-[100] hidden items-center justify-center bg-black/90 p-4";

    const img = document.createElement("img");
    img.alt = "";
    img.className = "max-h-[90vh] max-w-[90vw] rounded-lg object-contain";

    const counter = document.createElement("div");
    counter.className = "absolute left-1/2 top-4 -translate-x-1/2 text-sm text-white/70";
    const caption = document.createElement("div");
    caption.className = "absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-3 py-1 text-sm text-white/90";

    overlay.appendChild(makeBtn("prev", "Précédent", "absolute left-4 top-1/2 -translate-y-1/2 px-4 py-2 text-3xl text-white/80 hover:text-white", "‹"));
    overlay.appendChild(img);
    overlay.appendChild(makeBtn("next", "Suivant", "absolute right-4 top-1/2 -translate-y-1/2 px-4 py-2 text-3xl text-white/80 hover:text-white", "›"));
    overlay.appendChild(makeBtn("close", "Fermer", "absolute right-4 top-4 px-3 py-1 text-2xl text-white/80 hover:text-white", "✕"));
    overlay.appendChild(counter);
    overlay.appendChild(caption);
    document.body.appendChild(overlay);

    let group = [];
    let index = 0;

    function show(i) {
      index = (i + group.length) % group.length;
      const a = group[index];
      img.src = a.getAttribute("data-full") || a.getAttribute("href");
      img.alt = a.getAttribute("data-name") || "";
      const name = a.getAttribute("data-name") || "";
      caption.textContent = name;
      caption.style.display = name ? "" : "none";
      counter.textContent = (index + 1) + " / " + group.length;
      counter.style.display = group.length > 1 ? "" : "none";
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
