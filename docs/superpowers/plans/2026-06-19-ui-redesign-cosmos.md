# Cosmos UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the existing FastAPI+Jinja2 web UI with the cosmos design system (dark-first) and surface the section level in the gallery, with no SPA, no JS framework, and no Node at runtime.

**Architecture:** Presentation-layer only + one data-shape change in `web/gallery.py` (section grouping). A pre-compiled, committed `static/cosmos.css` (Tailwind v4 compiled once in a throwaway Node container via `make css`) replaces the hand-written `style.css`. Templates are rewritten with Tailwind utility classes mirroring cosmos; micro-interactivity (theme toggle, status polling) stays vanilla JS. `core/` is untouched.

**Tech Stack:** FastAPI, Jinja2, Tailwind CSS v4 (compiled offline), vanilla JS, pytest, Docker.

Spec: `docs/superpowers/specs/2026-06-19-ui-redesign-cosmos.md`.

---

## File Structure

- `src/ent_exporter/web/gallery.py` — add `SectionGroup`; `scan()` groups board→month→section→photos. (Task 1)
- `src/ent_exporter/web/assets/cosmos/cosmos.src.css` — Tailwind v4 entrypoint (vendored source, build-time only, not packaged). (Task 2)
- `src/ent_exporter/web/static/cosmos.css` — committed compiled CSS, served by StaticFiles. (Task 2)
- `Makefile` — `css` target (containerized Tailwind compile). (Task 2)
- `src/ent_exporter/web/templates/base.html` — cosmos shell, dark default, theme toggle. (Task 3)
- `src/ent_exporter/web/static/app.js` — theme toggle + existing polling. (Task 3)
- `src/ent_exporter/web/templates/gallery.html` — board→month→section rendering. (Task 4)
- `src/ent_exporter/web/templates/config.html`, `login.html` — cosmos form styling. (Task 5)
- `src/ent_exporter/web/static/style.css` — removed (replaced by cosmos.css). (Task 3)
- `tests/web/test_gallery.py`, `tests/web/test_app.py` — updated/extended.

---

## Task 1: Gallery section grouping

**Files:**
- Modify: `src/ent_exporter/web/gallery.py`
- Test: `tests/web/test_gallery.py`

- [ ] **Step 1: Rewrite the gallery tests for the new section structure**

Replace the whole body of `tests/web/test_gallery.py` with:

```python
from ent_exporter.web.gallery import scan, safe_resolve


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_scan_groups_by_board_month_section(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "Sortie" / "a.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "Arts" / "b.png")
    _touch(tmp_path / "PS" / "2026-05" / "sans-titre" / "c.jpg")
    _touch(tmp_path / ".thumbnails" / "PS" / "2026-06" / "Sortie" / "a.jpg.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "Sortie" / "notes.txt")  # non-image ignored

    boards = scan(tmp_path)
    assert [b.board for b in boards] == ["PS"]
    months = boards[0].months
    assert [m.month for m in months] == ["2026-06", "2026-05"]  # newest first
    assert [s.section for s in months[0].sections] == ["Arts", "Sortie"]  # alpha
    assert months[0].sections[0].photos[0].key == "PS/2026-06/Arts/b.png"
    assert months[1].sections[0].section == "sans-titre"


def test_scan_legacy_two_level_becomes_sans_titre(tmp_path):
    # board/month/file (no section folder) -> single "sans-titre" section.
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    boards = scan(tmp_path)
    sections = boards[0].months[0].sections
    assert [s.section for s in sections] == ["sans-titre"]
    assert sections[0].photos[0].key == "PS/2026-06/a.jpg"


def test_scan_sans_titre_sorted_last(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "Zoo" / "a.jpg")
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")  # -> sans-titre
    boards = scan(tmp_path)
    assert [s.section for s in boards[0].months[0].sections] == ["Zoo", "sans-titre"]


def test_scan_missing_root_is_empty(tmp_path):
    assert scan(tmp_path / "nope") == []


def test_safe_resolve_rejects_traversal(tmp_path):
    _touch(tmp_path / "PS" / "2026-06" / "a.jpg")
    assert safe_resolve(tmp_path, "PS/2026-06/a.jpg") is not None
    assert safe_resolve(tmp_path, "../secret") is None
    assert safe_resolve(tmp_path, "PS/2026-06/missing.jpg") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `make test` (or `pytest -q tests/web/test_gallery.py`)
Expected: FAIL — `AttributeError: 'MonthGroup' object has no attribute 'sections'`.

- [ ] **Step 3: Implement the section level in `gallery.py`**

Replace the whole content of `src/ent_exporter/web/gallery.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .thumbnails import THUMB_DIR

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SECTION_FALLBACK = "sans-titre"


@dataclass
class Photo:
    key: str  # posix path relative to the data root
    name: str


@dataclass
class SectionGroup:
    section: str
    photos: list[Photo] = field(default_factory=list)


@dataclass
class MonthGroup:
    month: str
    sections: list[SectionGroup] = field(default_factory=list)


@dataclass
class BoardGroup:
    board: str
    months: list[MonthGroup] = field(default_factory=list)


def _section_sort_key(section: str) -> tuple[bool, str]:
    # Real sections alpha-first; the "sans-titre" fallback always last.
    return (section == SECTION_FALLBACK, section.casefold())


def scan(root: Path | str) -> list[BoardGroup]:
    root = Path(root)
    if not root.is_dir():
        return []
    boards: list[BoardGroup] = []
    for board_dir in sorted(
        p for p in root.iterdir() if p.is_dir() and p.name != THUMB_DIR
    ):
        # month -> section -> [Photo]. Photos live as board/month/file (legacy)
        # or board/month/section/file (section grouping). The section is the
        # third path component when present, else the "sans-titre" fallback.
        by_month: dict[str, dict[str, list[Photo]]] = {}
        for f in board_dir.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = f.relative_to(root)
            if THUMB_DIR in rel.parts or len(rel.parts) < 3:
                continue
            month = rel.parts[1]
            section = rel.parts[2] if len(rel.parts) >= 4 else SECTION_FALLBACK
            by_month.setdefault(month, {}).setdefault(section, []).append(
                Photo(key=rel.as_posix(), name=f.name)
            )
        months = []
        for m in sorted(by_month, reverse=True):
            sections = [
                SectionGroup(
                    section=s,
                    photos=sorted(by_month[m][s], key=lambda p: p.key),
                )
                for s in sorted(by_month[m], key=_section_sort_key)
            ]
            months.append(MonthGroup(month=m, sections=sections))
        if months:
            boards.append(BoardGroup(board=board_dir.name, months=months))
    return boards


def safe_resolve(root: Path | str, key: str) -> Path | None:
    """Resolve a gallery key under root, refusing traversal. None if invalid."""
    root = Path(root).resolve()
    candidate = (root / key).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        return None
    if not candidate.is_file():
        return None
    return candidate
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `make test`
Expected: PASS (all `tests/web/test_gallery.py` green; the rest of the suite still green — `test_app.py::test_gallery_renders` only checks `"PS" in r.text`, unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/gallery.py tests/web/test_gallery.py
git commit -m "feat(web): surface card section level in gallery scan"
```

---

## Task 2: cosmos CSS pipeline (vendored source + make css + committed cosmos.css)

**Files:**
- Create: `src/ent_exporter/web/assets/cosmos/cosmos.src.css`
- Create (committed build artifact): `src/ent_exporter/web/static/cosmos.css`
- Modify: `Makefile`

- [ ] **Step 1: Create the Tailwind v4 entrypoint**

Create `src/ent_exporter/web/assets/cosmos/cosmos.src.css`:

```css
/* cosmos UI — Tailwind v4 entrypoint for ent_exporter.
   Compile with `make css` (throwaway Node container). The output
   ../../static/cosmos.css is the committed runtime source of truth.
   Only the cosmos brand accent + Outfit font + class-based dark variant
   are customized; everything else uses Tailwind v4 defaults (YAGNI). */
@import url("https://fonts.googleapis.com/css2?family=Outfit:wght@100..900&display=swap")
  layer(base);

@import "tailwindcss";

@source "../../templates";

@custom-variant dark (&:is(.dark *));

@theme {
  --font-outfit: Outfit, system-ui, sans-serif;

  --color-brand-50: #ecf3ff;
  --color-brand-100: #dde9ff;
  --color-brand-300: #9cb9ff;
  --color-brand-500: #465fff;
  --color-brand-600: #3641f5;
  --color-brand-700: #2a31d8;
  --color-brand-800: #252dae;
}
```

- [ ] **Step 2: Add the `css` target to the Makefile**

Add to `Makefile` — extend the `.PHONY` line and append the target:

```makefile
.PHONY: check lint test shell build css

# Compile the committed cosmos.css from the vendored Tailwind v4 source.
# Runs the Tailwind v4 CLI in a throwaway Node container (no host Node, no
# Node at runtime). Re-run only when template classes change; commit the output.
CSS_SRC = src/ent_exporter/web/assets/cosmos/cosmos.src.css
CSS_OUT = src/ent_exporter/web/static/cosmos.css
css:
	docker run --rm -v "$(CURDIR)":/app -w /app node:22-alpine \
	  npx --yes @tailwindcss/cli@4 -i $(CSS_SRC) -o $(CSS_OUT) --minify
	@echo "✅ Wrote $(CSS_OUT)"
```

- [ ] **Step 3: Generate the committed CSS**

Run: `make css`
Expected: prints `✅ Wrote src/ent_exporter/web/static/cosmos.css`. (First run pulls `node:22-alpine` and fetches `@tailwindcss/cli` via npx — needs network.)

- [ ] **Step 4: Verify the output is real CSS with the brand utility**

Run: `grep -c 'bg-brand-500\|--tw-' src/ent_exporter/web/static/cosmos.css`
Expected: a non-zero count (the compiled CSS contains generated utilities). The file should be several KB.

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/assets/cosmos/cosmos.src.css src/ent_exporter/web/static/cosmos.css Makefile
git commit -m "build(web): cosmos.css pipeline (vendored Tailwind v4 source + make css)"
```

---

## Task 3: base.html cosmos shell + dark default + theme toggle

**Files:**
- Modify: `src/ent_exporter/web/templates/base.html`
- Modify: `src/ent_exporter/web/static/app.js`
- Remove: `src/ent_exporter/web/static/style.css`
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Add a failing smoke test for the cosmos shell**

Append to `tests/web/test_app.py`:

```python
def test_base_uses_cosmos_css_and_dark_default(env):
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "/static/cosmos.css" in r.text
    assert 'class="dark"' in r.text
    assert "/static/style.css" not in r.text
    assert 'id="theme-toggle"' in r.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest -q tests/web/test_app.py::test_base_uses_cosmos_css_and_dark_default`
Expected: FAIL — current `base.html` references `/static/style.css` and has no `class="dark"`.

- [ ] **Step 3: Rewrite `base.html`**

Replace the whole content of `src/ent_exporter/web/templates/base.html` with:

```html
<!doctype html>
<html lang="fr" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}ent_exporter{% endblock %}</title>
  <script>
    // Apply the persisted theme before first paint (no flash). Dark is default.
    (function () {
      try {
        if (localStorage.theme === "light")
          document.documentElement.classList.remove("dark");
        else document.documentElement.classList.add("dark");
      } catch (e) {}
    })();
  </script>
  <link rel="stylesheet" href="/static/cosmos.css">
</head>
<body class="min-h-screen bg-gray-50 font-outfit text-gray-800 dark:bg-gray-900 dark:text-white/90">
  <header class="sticky top-0 z-50 flex items-center gap-4 border-b border-gray-200 bg-white px-5 py-4 dark:border-gray-800 dark:bg-gray-900">
    <a href="/" class="text-lg font-bold">📸 ent_exporter</a>
    <nav class="flex gap-4 text-sm">
      <a href="/" class="hover:text-brand-500">Galerie</a>
      <a href="/config" class="hover:text-brand-500">Configuration</a>
    </nav>
    <button id="theme-toggle" type="button" aria-label="Basculer le thème"
      class="ml-auto rounded-lg border border-gray-200 px-3 py-1.5 text-sm dark:border-gray-800">
      <span class="hidden dark:inline">☀️</span><span class="inline dark:hidden">🌙</span>
    </button>
  </header>
  <main class="mx-auto max-w-5xl px-5 py-6">{% block content %}{% endblock %}</main>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Rewrite `app.js` to add the theme toggle (keep polling)**

Replace the whole content of `src/ent_exporter/web/static/app.js` with:

```javascript
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
```

- [ ] **Step 5: Remove the obsolete style.css**

Run: `git rm src/ent_exporter/web/static/style.css`

- [ ] **Step 6: Run the smoke test + full suite**

Run: `make test`
Expected: PASS — `test_base_uses_cosmos_css_and_dark_default` green; rest of suite green.

- [ ] **Step 7: Commit**

```bash
git add src/ent_exporter/web/templates/base.html src/ent_exporter/web/static/app.js tests/web/test_app.py
git commit -m "feat(web): cosmos shell, dark default + theme toggle"
```

---

## Task 4: gallery.html cosmos restyle with section level

**Files:**
- Modify: `src/ent_exporter/web/templates/gallery.html`
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Add a failing test for section rendering**

Append to `tests/web/test_app.py`:

```python
def test_gallery_renders_section_heading(env):
    _touch(env / "PS" / "2026-06" / "Sortie ferme" / "a.jpg")
    client, _, _ = _client(env)
    r = client.get("/")
    assert r.status_code == 200
    assert "Sortie ferme" in r.text
    assert "/thumb/PS/2026-06/Sortie ferme/a.jpg" in r.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest -q tests/web/test_app.py::test_gallery_renders_section_heading`
Expected: FAIL — current `gallery.html` iterates `month.photos`, which no longer exists, so the section name is never rendered (template raises or omits it).

- [ ] **Step 3: Rewrite `gallery.html`**

Replace the whole content of `src/ent_exporter/web/templates/gallery.html` with:

```html
{% extends "base.html" %}
{% block content %}
<section class="mb-6 flex items-center gap-4">
  <form method="post" action="/sync">
    <button type="submit"
      class="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-gray-400"
      {% if not configured or status.state == "running" %}disabled{% endif %}>
      Synchroniser maintenant
    </button>
  </form>
  <span id="status" data-state="{{ status.state }}"
        class="text-sm text-gray-500 dark:text-gray-400">{{ status.state }}</span>
</section>
{% if not configured %}
<p class="mb-4 rounded-lg bg-amber-100 px-4 py-3 text-sm text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
  Identifiants ENT manquants — renseigne-les dans <a class="underline" href="/config">Configuration</a>.
</p>
{% endif %}
{% for board in boards %}
<h2 class="mb-3 text-xl font-semibold text-gray-800 dark:text-white/90">{{ board.board }}</h2>
{% for month in board.months %}
<h3 class="mb-2 mt-4 text-sm font-medium text-gray-500 dark:text-gray-400">{{ month.month }}</h3>
{% for section in month.sections %}
<div class="mb-4 rounded-2xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
  <h4 class="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">{{ section.section }}</h4>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
    {% for photo in section.photos %}
    <a href="/photo/{{ photo.key }}">
      <img loading="lazy" src="/thumb/{{ photo.key }}" alt="{{ photo.name }}"
           class="h-40 w-full rounded-xl object-cover">
    </a>
    {% endfor %}
  </div>
</div>
{% endfor %}
{% endfor %}
{% else %}
<p class="text-gray-500 dark:text-gray-400">Aucune photo pour l'instant. Lance une synchronisation.</p>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: Run the test + full suite**

Run: `make test`
Expected: PASS — `test_gallery_renders_section_heading` green; `test_app.py::test_gallery_renders` still green; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/ent_exporter/web/templates/gallery.html tests/web/test_app.py
git commit -m "feat(web): cosmos gallery with section grouping rendered"
```

---

## Task 5: config.html + login.html cosmos restyle

**Files:**
- Modify: `src/ent_exporter/web/templates/config.html`
- Modify: `src/ent_exporter/web/templates/login.html`
- Test: `tests/web/test_app.py`

- [ ] **Step 1: Add failing smoke tests for the restyled forms**

Append to `tests/web/test_app.py`:

```python
def test_config_page_is_cosmos_styled(env):
    client, _, _ = _client(env)
    r = client.get("/config")
    assert r.status_code == 200
    assert "focus:ring-brand-500/10" in r.text  # cosmos input styling present
    assert 'name="login"' in r.text


def test_login_page_is_cosmos_styled(env, monkeypatch):
    monkeypatch.setenv("ENT_WEB_PASSWORD", "secret")
    client, _, _ = _client(env)  # rebuilds app with login route mounted
    r = client.get("/login")
    assert r.status_code == 200
    assert "rounded-2xl" in r.text  # cosmos card present
    assert 'name="password"' in r.text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest -q tests/web/test_app.py::test_config_page_is_cosmos_styled tests/web/test_app.py::test_login_page_is_cosmos_styled`
Expected: FAIL — current templates lack the cosmos class markers.

- [ ] **Step 3: Rewrite `config.html`**

Replace the whole content of `src/ent_exporter/web/templates/config.html` with:

```html
{% extends "base.html" %}
{% block content %}
<h2 class="mb-4 text-xl font-semibold text-gray-800 dark:text-white/90">Configuration</h2>
<form method="post" action="/config" class="flex max-w-md flex-col gap-4">
  <label class="flex flex-col gap-1 text-sm">Identifiant ENT
    <input type="text" name="login" value="{{ login }}" autocomplete="username"
      class="rounded-lg border border-gray-300 bg-transparent px-3 py-2.5 text-sm focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700">
  </label>
  <label class="flex flex-col gap-1 text-sm">Mot de passe ENT {% if has_password %}<em class="text-gray-400">(déjà enregistré — laisser vide pour ne pas changer)</em>{% endif %}
    <input type="password" name="password" autocomplete="new-password" placeholder="••••••••"
      class="rounded-lg border border-gray-300 bg-transparent px-3 py-2.5 text-sm focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700">
  </label>
  <label class="flex flex-col gap-1 text-sm">Fréquence de synchronisation (heures, 0 = manuel)
    <input type="number" name="sync_interval_hours" min="0" value="{{ sync_interval_hours }}"
      class="rounded-lg border border-gray-300 bg-transparent px-3 py-2.5 text-sm focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700">
    <small class="text-gray-400">La fréquence s'applique au <strong>redémarrage</strong> du service.</small>
  </label>
  <button type="submit"
    class="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600">Enregistrer</button>
</form>
{% endblock %}
```

- [ ] **Step 4: Rewrite `login.html`**

Replace the whole content of `src/ent_exporter/web/templates/login.html` with:

```html
{% extends "base.html" %}
{% block content %}
<div class="mx-auto mt-10 max-w-sm rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
  <h2 class="mb-4 text-xl font-semibold text-gray-800 dark:text-white/90">Connexion</h2>
  {% if error %}<p class="mb-3 rounded-lg bg-red-100 px-4 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:text-red-300">Mot de passe incorrect.</p>{% endif %}
  <form method="post" action="/login" class="flex flex-col gap-4">
    <label class="flex flex-col gap-1 text-sm">Mot de passe
      <input type="password" name="password" autofocus
        class="rounded-lg border border-gray-300 bg-transparent px-3 py-2.5 text-sm focus:border-brand-300 focus:outline-none focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700">
    </label>
    <button type="submit"
      class="rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-600">Entrer</button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Run the tests + full suite**

Run: `make test`
Expected: PASS — both new tests green; full suite green.

- [ ] **Step 6: Regenerate cosmos.css against the final templates and commit**

The templates now reference their final set of utility classes. Regenerate so the
committed CSS includes every class actually used:

Run: `make css`
Expected: prints `✅ Wrote …/cosmos.css`.

```bash
git add src/ent_exporter/web/templates/config.html src/ent_exporter/web/templates/login.html src/ent_exporter/web/static/cosmos.css tests/web/test_app.py
git commit -m "feat(web): cosmos config + login forms; rebuild cosmos.css"
```

---

## Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm core is untouched**

Run: `git diff main -- src/ent_exporter ':!src/ent_exporter/web'`
Expected: empty output (no change outside `web/`).

- [ ] **Step 2: Full check (lint + tests)**

Run: `make check`
Expected: ruff clean, all tests pass.

- [ ] **Step 3: Build the web image and confirm cosmos.css ships in the wheel**

Run: `docker build -f runtimes/docker/Dockerfile.web -t beneylu-photo-sync:web-dev .`
Then: `docker run --rm beneylu-photo-sync:web-dev sh -c "python -c 'import ent_exporter.web, pathlib, importlib.util; p=pathlib.Path(importlib.util.find_spec(\"ent_exporter\").submodule_search_locations[0])/\"web\"/\"static\"/\"cosmos.css\"; print(\"cosmos.css present:\", p.exists())'"`
Expected: `cosmos.css present: True`.

- [ ] **Step 4: Commit any final fixups (if needed)**

```bash
git add -A && git commit -m "chore(web): final verification fixups" || echo "nothing to commit"
```

---

## Self-Review

**1. Spec coverage**
- "core untouched" → Task 6 Step 1. ✓
- "pre-compiled committed cosmos.css + make css containerized" → Task 2. ✓
- "section level board→month→section→photos" → Task 1 (data) + Task 4 (render). ✓
- "no Alpine / no JS framework, vanilla app.js" → Task 3 (app.js stays vanilla). ✓
- "dark default + light/dark toggle, no-flash" → Task 3 (`class="dark"`, pre-paint script, toggle). ✓
- "base/gallery/config/login restyled" → Tasks 3, 4, 5. ✓
- "style.css removed" → Task 3 Step 5. ✓
- "packaging ships cosmos.css" → glob `static/*` already covers it; verified Task 6 Step 3. ✓
- "tests: gallery section-awareness + smoke" → Task 1 tests + Tasks 3/4/5 smoke tests. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows full content. ✓

**3. Type consistency:** `BoardGroup.months` → `MonthGroup.sections` → `SectionGroup.photos` → `Photo.key/name` used consistently in `gallery.py` (Task 1) and `gallery.html` (Task 4). `SECTION_FALLBACK = "sans-titre"` matches the rendered/asserted `"sans-titre"`. `cosmos.css`/`/static/cosmos.css` consistent across Tasks 2–5. ✓
