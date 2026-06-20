(function () {
  // Theme toggle: flip .dark on <html>, persist choice. Default is dark.
  const toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      const dark = document.documentElement.classList.toggle("dark");
      try { localStorage.theme = dark ? "dark" : "light"; } catch (e) {}
    });
  }

  // Gallery view: progressive reveal (infinite scroll) + live accent-insensitive
  // search. All sections are server-rendered so search sees everything; we reveal
  // them in batches as the user scrolls (a spinner shows while more remain), and a
  // search query bypasses batching to show every match at once.
  (function () {
    const sections = Array.prototype.slice.call(document.querySelectorAll(".js-section"));
    if (!sections.length) return;
    const months = Array.prototype.slice.call(document.querySelectorAll(".js-month"));
    const boards = Array.prototype.slice.call(document.querySelectorAll(".js-board"));
    const input = document.getElementById("gallery-search");
    const empty = document.getElementById("search-empty");
    const sentinel = document.getElementById("scroll-sentinel");

    const BATCH = 6;
    let revealed = Math.min(BATCH, sections.length);
    let query = "";

    // Accent-insensitive: "mathemat" must match "En mathematiques".
    function norm(s) {
      return (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    }
    function visibleChild(parent, selector) {
      return Array.prototype.slice
        .call(parent.querySelectorAll(selector))
        .some(function (n) { return !n.classList.contains("hidden"); });
    }
    function recompute() {
      const searching = query.length > 0;
      let matches = 0;
      sections.forEach(function (s, i) {
        const hit = !searching || norm(s.getAttribute("data-search")).indexOf(query) !== -1;
        if (hit) matches++;
        // when searching, show every match; otherwise only the revealed batch
        s.classList.toggle("hidden", !(hit && (searching || i < revealed)));
      });
      months.forEach(function (m) {
        m.classList.toggle("hidden", !visibleChild(m, ".js-section"));
      });
      boards.forEach(function (b) {
        b.classList.toggle("hidden", !visibleChild(b, ".js-section"));
      });
      if (empty) empty.classList.toggle("hidden", !searching || matches > 0);
      if (sentinel) {
        const more = !searching && revealed < sections.length;
        sentinel.classList.toggle("hidden", !more);
        sentinel.classList.toggle("flex", more);
      }
    }

    if (input) {
      input.addEventListener("input", function () {
        query = norm(input.value.trim());
        recompute();
      });
    }
    if (sentinel && "IntersectionObserver" in window) {
      const io = new IntersectionObserver(function (entries) {
        if (entries[0].isIntersecting && !query && revealed < sections.length) {
          revealed = Math.min(revealed + BATCH, sections.length);
          recompute();
        }
      }, { rootMargin: "400px" });
      io.observe(sentinel);
    } else {
      revealed = sections.length;  // no IntersectionObserver: reveal everything
    }
    recompute();
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
    img.className = "max-h-[90vh] max-w-[90vw] rounded-xl object-contain";

    const counter = document.createElement("div");
    counter.className = "absolute left-1/2 top-4 -translate-x-1/2 text-sm text-white/70";
    const caption = document.createElement("div");
    caption.className = "absolute bottom-4 left-1/2 -translate-x-1/2 rounded-xl bg-black/50 px-3 py-1 text-sm text-white/90";

    // Download the photo currently shown. A plain <a download> hitting the same
    // /photo/{key} the image loads from; the browser saves it under data-name.
    const download = document.createElement("a");
    download.id = "lb-download";
    download.setAttribute("aria-label", "Télécharger la photo");
    download.setAttribute("title", "Télécharger la photo");
    download.className = "absolute left-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-xl text-white/80 hover:text-white";
    download.innerHTML = '<svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M5 21h14"/></svg>';

    overlay.appendChild(makeBtn("prev", "Précédent", "absolute left-4 top-1/2 -translate-y-1/2 px-4 py-2 text-3xl text-white/80 hover:text-white", "‹"));
    overlay.appendChild(img);
    overlay.appendChild(makeBtn("next", "Suivant", "absolute right-4 top-1/2 -translate-y-1/2 px-4 py-2 text-3xl text-white/80 hover:text-white", "›"));
    overlay.appendChild(makeBtn("close", "Fermer", "absolute right-4 top-4 px-3 py-1 text-2xl text-white/80 hover:text-white", "✕"));
    overlay.appendChild(download);
    overlay.appendChild(counter);
    overlay.appendChild(caption);
    document.body.appendChild(overlay);

    let group = [];
    let index = 0;

    function show(i) {
      index = (i + group.length) % group.length;
      const a = group[index];
      const full = a.getAttribute("data-full") || a.getAttribute("href");
      img.src = full;
      img.alt = a.getAttribute("data-name") || "";
      const name = a.getAttribute("data-name") || "";
      download.href = full;
      download.setAttribute("download", name || "");
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
      const counts = () => {
        let c = `${s.downloaded} téléchargées, ${s.skipped} ignorées, ${s.errors} erreurs`;
        if (s.pruned) c += `, ${s.pruned} élagués`;
        return c;
      };
      let label = s.state;
      if (s.state === "error" && s.last_error) label += " — " + s.last_error;
      else if (s.state === "running") label = `Synchronisation… ${counts()}`;
      else if (s.state === "idle" && s.last_run_at) label += ` — ${counts()}`;
      el.textContent = label;
      el.dataset.state = s.state;
      if (s.state === "running") return setTimeout(poll, 1000);
    } catch (e) { /* keep last shown state */ }
  }
  if (el.dataset.state === "running") poll();
  const form = document.querySelector('form[action="/sync"]');
  if (form) form.addEventListener("submit", () => setTimeout(poll, 500));
})();

// Danger-zone forms: keep the destructive button disabled until the exact
// confirmation word is typed, and ask once more on submit. The server enforces
// the same typed gate regardless; this is just a guard rail.
(function () {
  document.querySelectorAll("form.js-danger").forEach(function (form) {
    const want = form.getAttribute("data-confirm");
    const input = form.querySelector('input[name="confirm"]');
    const btn = form.querySelector('button[type="submit"]');
    if (!want || !input || !btn) return;
    const sync = () => { btn.disabled = input.value.trim() !== want; };
    sync();
    input.addEventListener("input", sync);
    form.addEventListener("submit", function (e) {
      if (input.value.trim() !== want || !confirm("Action irréversible. Continuer ?"))
        e.preventDefault();
    });
  });
})();
