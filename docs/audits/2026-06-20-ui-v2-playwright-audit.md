# UI v2 — Playwright 1.60 audit & improvement plan

**Date:** 2026-06-20 · **Branch:** `feat/ui-v2` · **Method:** headless Chromium via
`mcr.microsoft.com/playwright:v1.60.0-noble` in a container, driving the running
demo (`ent-web-uiv2`, 174 real photos copied read-only, no credentials/state).
Captured: desktop (1440×900) + mobile (390×844), light + dark, full-page + viewport
JPEGs, plus console/pageerror/requestfailed listeners and a DOM diagnostic.

## Functional result: clean

| Check | Result |
|---|---|
| Console errors / warnings | **0** |
| Uncaught page errors | **0** |
| Failed/4xx network requests | **0** |
| Gallery / Config routes | 200 |
| Lightbox open / arrow-nav / Esc-close | OK |
| `GET /download` (whole library) | 200 `application/zip`, 80.2 MB |
| `GET /download/<board>/<month>/<section>` | 200 `application/zip` |
| Config exclude field present | yes |
| Horizontal overflow (desktop & mobile) | none (390=390) |
| Theme toggle (dark↔light, persisted) | OK |

Nothing is broken at the functional level. The remaining items are **finish/design**
quality and one genuine naming bug.

## Findings (ranked)

### 1. Section titles carried a trailing separator artifact — **FIXED**
`Écrit_`, `Explorer le monde_`, `En mathématiques_`: the title's trailing colon was
sanitized to `_` and never stripped. `section_folder` now `rstrip(" ._,-")`.
Commit `541558b`. Future syncs produce clean names; the demo confirms `Écrit`,
`Explorer le monde`.

### 2. Sparse sections (1–4 photos) leave a large empty card — **design**
A section with one photo renders one tile top-left in a full-width 5-column card,
~80% empty. Dense sections (9–33 photos) look excellent; only sparse ones feel
unbalanced. *Proposal:* switch the grid to `repeat(auto-fill, minmax(150px,1fr))`
with a tile `max-width`, so tiles keep a consistent comfortable size and sparse
sections read as intentional rather than broken; optionally lighten the card chrome
(border/padding) when a section has ≤2 photos.

### 3. Lightbox polish — **design**
Works, but the `bg-black/80` overlay lets the sticky header bleed through at 20%,
and there is no caption or position counter. *Proposal:* raise overlay opacity to
`/90`–`/95`, add a small bottom caption (`data-name`) and an `n / total` counter.

### 4. Sticky month header legibility — **design**
`top-[68px]` vs a 67px header leaves a 1px sliver; the blur band is faint and the
label is low-contrast where it overlaps a card's top edge. *Proposal:* `top-[67px]`,
a slightly stronger background, uppercase tracking, and a touch more contrast.

### 5. Long single-line titles truncate mid-word — **minor**
`Bonjour à tous et toutes, Le loto organisé par notre associa` is hard-cut at 60
chars. *Proposal (display-only):* keep the short folder name but render the title
with `line-clamp` + word-boundary truncation, or cut at the last space before 60.

### 6. Mobile header & per-section link wrapping — **minor**
The wordmark wraps to two lines on 390px and the per-section "Télécharger la section"
link wraps awkwardly. *Proposal:* shrink the brand on `sm`, and make the section
header wrap gracefully (icon-only download affordance on narrow screens).

### 7. Document-style photos cropped by `object-cover` — **minor / accept**
Portrait posters/forms (e.g. the loto flyer, the HelloAsso sheet) lose top/bottom in
the square grid. The lightbox shows them whole on click, so this is an acceptable
trade-off for a uniform grid. No change recommended.

## Suggested order of work (Phase C — polish)

1. (done) #1 naming artifact.
2. #2 gallery grid for sparse sections — highest visual impact.
3. #3 lightbox opacity + caption + counter.
4. #4 sticky month header.
5. #5 / #6 title truncation + mobile header — minor.

Each is a small, independently testable template/CSS change validated by a fresh
Playwright pass against the demo container. Re-run `make css` after class changes.
