# UI Redesign — cosmos design system (server-rendered)

> Design doc. Status: approved 2026-06-19. Implementation plan: see
> `docs/superpowers/plans/2026-06-19-ui-redesign-cosmos.md` (written next).

## Goal

Apply the user's **cosmos** design system (TailAdmin + Tailwind CSS v4, dark-first)
to the existing FastAPI + Jinja2 server-rendered web UI, and surface the **section**
level (card caption) in the gallery. Keep the app mono-container, server-rendered,
no SPA, no JS framework, no Node at runtime.

## Non-goals (YAGNI)

- No React/SPA (rejected as overkill for a 3-page single-family gallery).
- No Alpine.js or any JS framework — cosmos's interactive partials are NOT reused
  verbatim; we borrow only the visual vocabulary (Tailwind utilities + `@theme`
  tokens) and keep our own vanilla `app.js`.
- No cosmos sidebar/dashboard shell (2 content pages → a header is enough).
- No matrix mode, no charts/stats, no board filter (e.g. excluding APEIT). These
  stay in the backlog.

## Constraints

- **`core/` untouched.** Provable via `git diff main -- src/ent_exporter ':!web/'`
  returning empty. Only the `web/` package changes.
- **Containers only.** No host venv/pip. `make check` (ruff + pytest) stays the
  "done" bar and must not require Node.
- **Secrets unchanged.** Auth/HMAC cookie, chmod-600 config, write-only ENT
  password handling are not touched by this redesign.

## Architecture

### Overview

The redesign is **presentation-layer only** plus one data-shape change in
`web/gallery.py` (adding the section grouping level). Routes, `thumbnails`, `auth`,
`jobs`, `scheduler`, `settings_store` are unchanged. The legacy
`static/style.css` (hand-written) is replaced by a **pre-compiled, committed**
`static/cosmos.css`. Templates are rewritten using Tailwind utility classes that
mirror cosmos's look.

### CSS asset — pre-compiled, committed

cosmos ships two zero-framework paths; we use the **compiled Tailwind** path (the
user picked the full TailAdmin look over tokens-only):

- **Source (vendored):** `src/ent_exporter/web/assets/cosmos/cosmos.src.css`
  — a Tailwind v4 entrypoint:
  - `@import "tailwindcss";`
  - the cosmos `@theme` block (brand palette `--color-brand-*`, `--font-outfit`,
    breakpoints, `--text-theme-*`, `--shadow-theme-*`) copied from
    `cosmos_ui/packages/html/src/css/style.css`.
  - `@custom-variant dark (&:is(.dark *));`
  - `@source "../../templates";` so Tailwind scans our Jinja templates for the
    utility classes actually used (content-based generation).
- **Output (committed):** `src/ent_exporter/web/static/cosmos.css`. Served by the
  existing FastAPI `StaticFiles` mount at `/static/`. This file is the runtime
  source of truth.
- **Regeneration:** a `make css` target runs the Tailwind v4 compiler **in a
  throwaway Node container** (`node:22-alpine`, `npx @tailwindcss/cli`), reading
  `cosmos.src.css`, writing `static/cosmos.css`. Run manually whenever template
  classes change. **Node never enters the runtime image, `make check`, or CI.**
- The Outfit font is loaded via the Google Fonts `@import` already present in the
  cosmos `@theme` source; no font files vendored.

Rationale: a committed CSS keeps the Python-only runtime/CI untouched (no Node
build stage in the path that gates "done"), at the cost of a manual regen step
that is rare for this app. The regen is containerized to honor the
containers-only rule.

### Gallery section level (data-shape change)

Photos already land on disk as `board/AAAA-MM/<section>/<file>` (section grouping,
merged). The gallery currently flattens sections away (groups by month only). We
add the section level to the scan output.

New types in `web/gallery.py`:

```
@dataclass
class Photo:
    key: str   # posix path relative to the data root
    name: str

@dataclass
class SectionGroup:
    section: str            # folder name, e.g. "Sortie ferme" or "sans-titre"
    photos: list[Photo]

@dataclass
class MonthGroup:
    month: str              # "AAAA-MM"
    sections: list[SectionGroup]

@dataclass
class BoardGroup:
    board: str
    months: list[MonthGroup]
```

`scan()` walks each board recursively, and for every image keyed
`board/month/.../file`:

- `month = rel.parts[1]`.
- `section = rel.parts[2]` **if** the photo is nested at depth ≥ 4
  (`board/month/section/file`); otherwise (2-level legacy `board/month/file`)
  `section = "sans-titre"`.
- Photos are grouped `month → section`. Months sorted newest-first; sections
  sorted alphabetically with `sans-titre` last; photos sorted by key.

Backward compatible: a 2-level tree yields a single `sans-titre` section per month.

### Templates

All under `web/templates/`, rewritten with Tailwind utility classes (cosmos look),
dark-first.

- **`base.html`**: `<html class="dark" lang="fr">`. A pre-paint inline `<head>`
  script applies the persisted theme before first paint (no flash). cosmos sticky
  header (`dark:bg-gray-900`, brand "📸 ent_exporter", nav Galerie / Configuration)
  with a **light/dark toggle** button on the right. `<main>` centered container.
  Links `cosmos.css` (not the old `style.css`).
- **`gallery.html`**: toolbar with a `brand-500` "Synchroniser maintenant" button
  (disabled when not configured or running) and a status badge (`#status`).
  Renders `board → month → section`. Each **section** is a cosmos card
  (`rounded-2xl border border-gray-200 dark:border-gray-800 dark:bg-white/[0.03]`)
  with the section name as heading and a responsive image grid
  (`grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3`, images
  `rounded-xl object-cover`). Empty state preserved.
- **`config.html`**: same fields/semantics; inputs styled cosmos
  (`rounded-lg border focus:ring-3 focus:ring-brand-500/10`). The "password already
  saved — leave blank" hint and the restart-applies note are preserved verbatim.
- **`login.html`**: cosmos-styled password form, centered card.

### Dark mode + toggle (vanilla)

- Server renders `<html class="dark">` (dark default).
- Inline `<head>` script (runs before paint): if `localStorage.theme === "light"`,
  remove `.dark`; else ensure `.dark`. Prevents flash-of-wrong-theme.
- `app.js` gains a toggle handler: on click, flip `.dark` on `<html>` and write
  `localStorage.theme = "light" | "dark"`. Existing status-polling logic unchanged.

## Error handling

No new failure modes. The CSS is a static file; if `cosmos.css` is missing the page
degrades to unstyled HTML (acceptable, and caught by the smoke test). The gallery
scan keeps its current behavior (missing root → empty list).

## Testing

- **`tests/web/test_gallery.py`** (updated): new structure
  `board.months[].sections[].photos`. Cases:
  - 2-level legacy tree → one `sans-titre` section per month (back-compat).
  - 3-level section tree → photos grouped under their section folder; sections
    sorted alpha with `sans-titre` last; months newest-first.
  - thumbnails dir and non-image files ignored (kept from current tests).
  - traversal safety (`safe_resolve`) unchanged.
- **`tests/web/test_app.py`** (smoke, extend or add): `/`, `/config`, `/login`
  return 200 and the rendered HTML references `/static/cosmos.css` and
  `class="dark"`.
- `make check` green (ruff + pytest). `core` untouched diff empty.

## File structure

- Create: `src/ent_exporter/web/assets/cosmos/cosmos.src.css`
- Create (committed build artifact): `src/ent_exporter/web/static/cosmos.css`
- Modify: `src/ent_exporter/web/gallery.py` (add `SectionGroup`, section grouping)
- Modify: `src/ent_exporter/web/templates/{base,gallery,config,login}.html`
- Modify: `src/ent_exporter/web/static/app.js` (theme toggle)
- Remove: `src/ent_exporter/web/static/style.css` (replaced by `cosmos.css`)
- Modify: `Makefile` (add `css` target — containerized Tailwind compile)
- Modify: `tests/web/test_gallery.py`; add/extend `tests/web/test_app.py`
- Ensure packaging ships `static/cosmos.css` + templates in the wheel (already
  configured for templates/static; verify `cosmos.css` is included).

## Open questions

None. Build approach (pre-compiled committed CSS), section surfacing (yes), and
theme (dark default + light/dark toggle, no matrix mode) are decided.
