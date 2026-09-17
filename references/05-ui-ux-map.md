# 05 — reMarkable 2 UI/UX Map

Designer-usable map of the stock rM2 interface. Target canvas is
**1404 × 1872 portrait**. All paths verified against scout reports;
uncertain items are marked `[INFERENCE]` or `[MED]` (medium confidence —
confirm on-device before pixel-driving).

Paper Pro deltas are flagged inline and **never mixed** into rM2 procedures.
 > Evidence 2026-09-17/18: taps + swipes WORKING via `/tmp/rm-input`
 > over SSH (static helper, screen coords, Y flip internal), ~50 acts
 > every one screenshot-verified.
 > VERIFIED: home map (multi-scroll); tile tap opens doc at last-viewed
 > page; X top-right (~1345,50) closes doc AND PDF views; home grid
 > scrolls, restores byte-exact; 13-icon toolbar with tap positions
 > (§4.1); hamburger drawer contents; sort options + active-row
 > direction toggle + outside-tap dismiss; search overlay + keyboard +
 > Back; + button → Create dialog (Notebook/Folder/Quick sheet);
 > calendar pill → offline toast; tag sheet; ⋮ menu (Email/Convert and
 > Share/Present with Screen Share); page navigator + thumbnail jump =
 > deterministic page turn; Trash browser; Settings tree +
 > General/Display/Accessibility contents; tile labels track
 > last-viewed page; overlay round-trips reset grid scroll to top.
 > PAGE-CREATE STATUS: owner flow is double-swipe on last page (button
 > appears, second swipe creates; works notebook AND PDF). 6 synthetic
 > variants all byte-exact NO-OP on CONFIRMED last pages
 > (navigator-verified Notebook 19 p2/2, readalong33 p5/5): notebook
 > mid-page, notebook fast flick, PDF mid-page, PDF edge, notebook
 > double, PDF double. Likely cause: contact fidelity (constant
 > pressure/size/timing vs ramping finger). The button ALSO sits
 > permanently in the page navigator. Trigger + tap UNCONFIRMED —
 > do not script page creation.
 > NOT verified: add-page button tap, tool-switch taps, undo/redo,
 > layers panel, template-grid icon (no-op in PDF), Guides/Help/Wi-Fi/
 > Cloud/Security subs, per-file Trash delete/restore, auto-sleep
 > setting location, keyboard typing (photographed, never typed),
 > swipe-down-from-top (still DISPUTED, do not script).
 > RELIABILITY: one tap in ~50 was silently swallowed by Qt (ok-printed
 > but no effect). NEVER trust "ok" — verify every act by screenshot.

## 1. Canvas and hardware frame

- Panel: 1404 × 1872 portrait, monochrome e-ink, **no backlight**.
- Physical: 187 × 246 × 4.7 mm, 403.5 g, 1 GB RAM, 8 GB storage,
  3000 mAh (~2 weeks typical), USB-C lower-left edge,
  power button top-left edge, magnetic Marker dock on right edge,
  accessory pogo-port for Type Folio.
- Sleep/off images are exactly **1404 × 1872, 8-bit gray PNG**;
  they are **wiped on OS upgrade** (must be re-installed after update).
- Design safe area: full-bleed 1404 × 1872 portrait. Keep interactive
  chrome ≥ 60 px from edges (finger targets); body text ≥ 24 px
  equivalent; never rely on color — black/gray/white only.

## 2. Screen hierarchy

```
 My files (home)
 ├── Folder
 │   └── Folder / Document (recursive)
 ├── Notebook-or-PDF Document view
 │   ├── Canvas (template-or-PDF base + ink layers)
 │   ├── Left toolbar (13 icons: writing tools + eraser, select, layers, undo, redo, template grid, pages, tag, ⋮ more — see §4.1)
 │   ├── Top-right X (tap ~1345,50 closes to home — verified, doc + PDF views)
 │   └── Page navigator ("Go to page" thumbs — deterministic page turn)
└── Quick sheets (auto notebook pinned in My-files root)
Overlays (from any screen): Share/export · Document settings ·
    Page settings · Settings tree · Help · Search · Power menu
```

### 2.1 My files (home) — verified from live screenshot 2026-09-17

- Top bar: hamburger (top-left), reMarkable wordmark (center), status icons
  (top-right: sync diamond, charging bolt, battery). No search, new, or
  sort controls in the top bar.
- Below: "My files" title (left), sort control (right, reads "File size"
  with a dropdown chevron).
- Folder grid (4 columns): folder icon + name; long names truncate
  ("Reinforce... Learning").
- Document grid with page thumbnails: PDFs render first-page content,
  notebooks render ink. Label is name plus "Page X of N", or "N% read" for
  ebooks in progress.
 - Bottom-center floating pill, three icons with verified positions
  (orig coords at default scroll): search ~(580,1684), + ~(696,1683),
  calendar ~(813,1683). Search → full-screen search overlay (field,
  All/Relevance filters, on-screen keyboard, Back returns home).
  + → "Create new" dialog (Notebook / Folder / Quick sheet; + turns
  to ✕ while open, nothing created until chosen). Calendar → "No
  active internet connection" toast (needs cloud; tablet offline).
 - Tile tap OPENS the document at its last-viewed page. Tile labels
  track last-viewed page (2408.15232 went 1/39 → 5/39 after a page
  jump). Grid order follows the sort control; home has MULTIPLE scroll
  positions (folders-top, docs-grid) and overlay round-trips reset
  scroll to top — NEVER hardcode tile coords or assume scroll; locate
  the tile in a fresh screenshot, convert with ×1.19, tap its center.
 - NOT present on this firmware: left sidebar filters, top-row search/new
  buttons, bottom status strip. Earlier claims of those removed.

 ### 2.2 Hamburger drawer + sort — verified 2026-09-18

 Drawer (tap ~60,50) contents top→bottom: My files (header, selected),
 Filter by (>), Favorites (star), Tags, Import files / Currently
 offline (cloud), Trash, Guides, Settings (gear). Tap row to enter;
 My-files header or hamburger returns.

 Sort control ("File size" + chevron, ~(1330,180)): options Last
 modified, Last opened, Date created, Alphabetical (A-Z),
 File size (selected), Page count; View: four density icons (Medium
 grid selected). Tapping the ACTIVE row toggles sort DIRECTION for all
 criteria (A-Z ↔ Z-A icon flip — a real state change; re-tap to
 restore). Dismiss with no change by tapping outside (e.g. title).

 | Element | Location | Opens |
 |---|---|---|
 | Hamburger (≡) | Top-left | Drawer above [VERIFIED] |
 | Search (magnifier) | Bottom-center pill, left icon | Search overlay + keyboard [VERIFIED] |
 | New (+) | Bottom-center pill, middle icon | Create dialog: Notebook / Folder / Quick sheet [VERIFIED] |
 | Calendar | Bottom-center pill, right icon | Offline toast (cloud-gated) [VERIFIED] |
 | Sort | Under "My files" title, right | Options + direction toggle above [VERIFIED] |
 | WiFi / battery | Top-right status icons | Status only (no action) |

 ### 2.3 Document view — verified from live screenshots 2026-09-18

 - **Close:** X top-right (~1345,50) returns to home — doc AND PDF
  views (verified 6x). In page-navigator mode X is replaced by Back
  (top-left).
 - **Left toolbar:** 13-icon vertical strip, top→bottom: pen-dot (tool
  indicator), writing tool (A-nib icon, selected-underline), highlighter,
  T text, eraser, selection marquee, layers, undo, redo, template grid,
  pages, tag, ⋮ more. Active tool shows a dot; selected tool gets
  a black tile. Verified tap positions (orig): pages ≈(48,1505),
  tag ≈(48,1618), ⋮ ≈(48,1749). Template-grid icon is a NO-OP in PDF
  view (likely notebook-only).
 - **Top bar (doc view):** Back (in navigator mode), title center, and
  in navigator mode: pages-list icon, tag icon, share (paper-plane)
  icon right. No title bar on the canvas itself.
 - **Page navigator (PREFERRED page turn):** pages toolbar icon opens
  "Go to page" — thumbnail grid with page numbers, current page
  marked, Medium-grid density toggle top-right. Tapping a thumbnail
  jumps deterministically (verified p9 → p5). USE THIS, not swipes.
 - **Swipe page turn: NO-OP for synthetic swipes** (all byte-exact
  no-change on CONFIRMED last pages): notebook mid-page, notebook fast
  flick (12×8ms), PDF mid-page, PDF from right edge, notebook
  double-swipe, PDF double-swipe. Suspected cause: contact fidelity
  (constant pressure/size vs ramping finger).
 - **Add-page button:** black circle, white page-plus icon, mid-right
  (~1225,990) on blank last pages; ALSO permanently in the page
  navigator corner. Photographed ×3. Owner flow (double-swipe reveals,
  second swipe creates, notebook + PDF) works by finger but all 6
  synthetic variants no-op — trigger + tap UNCONFIRMED, do not script
  page creation.

## 3. Overlays

 | Overlay | Entry | Contents |
 |---|---|---|
 | Share / export | Doc top bar paper-plane; ⋮ menu | ⋮ menu shows Email / Convert and Share / Present with Screen Share [VERIFIED] |
 | Tag sheet | Toolbar tag icon ≈(48,1618) | Existing tags listed (e.g. "thesis") + "+ New tag" [VERIFIED] |
 | Page navigator | Toolbar pages icon ≈(48,1505) | "Go to page" thumbs, current mark, density toggle; thumbnail tap jumps [VERIFIED] |
 | Document settings | Top doc menu | Shapes-assist toggle, orientation, language for handwriting conversion [INFERENCE] |
 | Settings | Hamburger → Settings | Tree, see §10 (verified top level + 3 subs) |
 | Trash | Hamburger → Trash | Full file browser (folders + docs + labels); per-file delete/restore untested [VERIFIED] |
 | Search | Pill magnifier ≈(580,1684) | Field + All/Relevance filters + keyboard; Back returns home [VERIFIED] |
 | Create | Pill + ≈(696,1683) | Notebook / Folder / Quick sheet dialog; + becomes ✕ [VERIFIED] |
 | Power menu | Long-press power button | Sleep, power off, restart, (cancel) [INFERENCE] |
 ## 4. Toolbar — 13-icon strip (9 writing tools + page tools)

 ### 4.1 Strip layout (verified order, top→bottom, 2026-09-17)

 1. pen-dot (active-tool indicator) · 2. writing tool (A-nib) ·
 3. highlighter · 4. T text · 5. eraser · 6. selection marquee ·
 7. layers · 8. undo · 9. redo · 10. template grid · 11. pages ·
 12. tag · 13. ⋮ more. (Earlier notes said 11=tag, 12=share — wrong:
 effect-verified 2026-09-18: ≈(48,1505) opens pages, ≈(48,1618) opens
 tag sheet.) Writing-tool icons 2–4 switch with the selected tool
 (only one visible at a time); the picker names below are the 9
 official tools.
 ### 4.2 The 9 writing tools

 Official set is 9 tools. Six names are report-confirmed; the remaining
 three are `[MED — confirm exact labels on-device]`.

| # | Tool | Thickness | Ink on rM2 | Notes |
|---|---|---|---|---|
| 1 | Ballpoint | S / M / L | Black / Gray / White | Constant-width everyday pen |
| 2 | Fineliner | S / M / L | Black / Gray / White | Constant-width precise line |
| 3 | Marker | S / M / L | Black / Gray / White | Heavy opaque stroke |
| 4 | Pencil | S / M / L | Black / Gray / White | Pressure-shaded sketch |
| 5 | Paintbrush | S / M / L | Black / Gray / White | Pressure-width stroke |
| 6 | Highlighter | S / M / L | Black / Gray (white n/a) | Snaps to text lines |
| 7 | Mechanical pencil `[MED]` | S / M / L | Black / Gray / White | Fine constant line |
| 8 | Calligraphy pen `[MED]` | S / M / L | Black / Gray / White | Angle-dependent nib |
| 9 | Shader / Filler `[MED]` | S / M / L | Black / Gray / White | Area fill — verify label on-device |

Shared rules:

- Thickness is always exactly **S / M / L** — no numeric sizes.
- Ink color on rM2 is **black / gray / white ONLY**. Any color UI is a
  Paper Pro surface — never drive it on rM2.
- Eraser: area marquee + whole-page modes. Firmware ≥ 3.8 performs
  **true stroke removal**; pre-3.8 painted white overpaint instead.
- Selection (lasso/marquee): move / resize / copy / cut / paste;
  convert selection to typed text (MyScript).
- Undo / redo buttons; layers visibility toggle; Marker Plus flip =
  eraser end (`BTN_TOOL_RUBBER`).
- Perfect shapes: draw then **hold stroke-end** — circle / triangle /
  square snap in, then scale / rotate with two fingers.

## 5. Gesture table

 | Gesture | Context | Effect |
 |---|---|---|
 | Tap document tile | My files grid | Opens doc at last-viewed page [VERIFIED] |
 | Tap X top-right (~1345,50) | Doc / PDF view | Closes to home [VERIFIED 6x] |
 | Back top-left | Navigator / search / settings | Returns to previous screen [VERIFIED] |
 | Vertical swipe | My files grid | Scrolls; reverse swipe restores byte-exact [VERIFIED] |
 | Hamburger (~60,50) | Home | Drawer: My files/Filter/Favorites/Tags/Import/Trash/Guides/Settings [VERIFIED] |
 | Sort chevron (~1330,180) | Home | Options + View density; tapping ACTIVE row toggles direction (state change!) [VERIFIED] |
 | Tap outside | Open dropdown/dialog | Dismisses with no change [VERIFIED] |
 | Pill search ~(580,1684) | Home | Search overlay + keyboard [VERIFIED] |
 | Pill + ~(696,1683) | Home | Create dialog: Notebook/Folder/Quick sheet [VERIFIED] |
 | Pill calendar ~(813,1683) | Home | Offline toast (cloud-gated) [VERIFIED] |
 | Toolbar pages ≈(48,1505) | Doc view | "Go to page" navigator [VERIFIED] |
 | Navigator thumbnail | Navigator | Jumps to that page (verified p9→p5) [VERIFIED] |
 | Toolbar tag ≈(48,1618) | Doc view | Tag sheet: existing tags + New tag [VERIFIED] |
 | Toolbar ⋮ ≈(48,1749) | Doc view | Menu: Email / Convert and Share / Present with Screen Share [VERIFIED] |
 | Toolbar template-grid | PDF view | NO-OP (likely notebook-only) [VERIFIED] |
 | Synthetic swipe (mid/fast/edge/double ×6) | Confirmed last pages (notebook p2/2, PDF p5/5) | NO-OP, byte-exact every time [VERIFIED] |
 | Add-page button (~1225,990 canvas; navigator corner) | Blank last page / navigator | Photographed ×3; owner double-swipe flow works by finger; synthetic trigger + tap UNCONFIRMED — do not script |
 | Swipe down from top edge | Document view | [DISPUTED by owner — do not script] Alleged: closes document / reveals menu. Contradictory as written; needs screenshot proof. |
| Tap corner | Document view | Toggles bookmark on current page |
| Long-press corner | Document view | Edits bookmark description |
| Two-finger swipe left/right | Document view | Switch document / cycle recent files |
| Long-press recent entry | Recent list | Restores last deleted file (pre-sync only) |
| Hold stroke-end ~1 s | Canvas while drawing | Perfect-shape snap (circle/triangle/square), then scale/rotate |
| Lasso / marquee | Canvas with selection tool | Select strokes → move/resize/copy/cut/paste/convert |
| Marker Plus flip | Canvas | Eraser without toolbar switch |
| Folio magnets close | Any | Auto sleep; open wakes `[MED timings]` |
| Press power | Any | Sleep / wake |
| Long-press power | Any | Power menu (sleep / off / restart) |

No side buttons exist on rM2 (rM1 had middle/home keys — do not script
them). Long-press suspend behavior is systemd/logind policy on top of
`KEY_POWER`, not a separate key code.

## 6. Notebook / PDF / EPUB semantics

- **Notebook:** ordered pages, each page has its own template; pages can
  be added, duplicated, reordered, deleted. Ink stored per page as
  `.rm` stroke files.
- **PDF:** original file kept unmodified; strokes stored as overlay
  layers on top. Inserted pages are **blank without template**.
  Hyperlinks inside PDFs work (tap to follow).
- **EPUB:** converted to PDF internally on import. **Reformat
  regenerates the PDF and orphans existing strokes** — stock firmware
  shows a warning; automation MUST confirm destructive reformats via
  plus favorites/tags; official guide recommends folders for structure,
  tags/favorites for cross-cutting sets.

## 7. Quick sheets rules

- Quick sheets is an **auto-created notebook pinned in the My-files
  root** — the scratch pad.
- Tapping its entry **appends a fresh page** to the same notebook.
- It **cannot be renamed, moved, or deleted** — never script those
  actions against it.
- Use it for throwaway capture in autonomy flows (zero navigation cost,
  no naming step).

## 8. Type Folio states

- Exclusive **pogo-pin accessory** — no charging, no Bluetooth pairing.
- Three working positions: upright / high / near-flat, plus folded-back
  (typing disabled when folded).
- Attaching rotates the display into the **typing view** with minimal
  text formatting and variable-length pages.
- Fallbacks when no Folio: on-screen keyboard, or desktop/mobile apps +
  Connect for longer text.
- Autonomy note: never assume a keyboard is present; prefer file-push
  (`POST /upload`, `rmapi put`) over on-device typing.

## 9. Power, sleep, battery

- 3000 mAh, ~2-week typical use, **no backlight** — fully dark ⇒ off,
  not "dim".
 - States: **awake → light-sleep banner → deep-sleep (`suspended.png`)
  → off**. Auto-sleep timeout is NOT in Settings → Display (only a
  "Visible content" standby toggle there) — location still unknown.
- Sleep PNG: exactly 1404 × 1872 8-bit gray; static screens are
  **reset on OS upgrade**.
- Wake: press power, open folio, or (over USB) any SSH activity does
  NOT wake the panel — verify wake by fresh screenshot.

 ## 10. Settings tree — verified top level + 3 subs (fw 3.28, 2026-09-18)

 ```
 Settings (drawer → Settings)
 ├── General — Account row (signed-in user), Software Version
 │              (e.g. 3.28.0.172), Language and keyboard, Battery %,
 │              Storage (used/total), Flight-mode toggle, Restart button,
 │              Turn off button
 ├── Wi-Fi — [NOT OPENED]
 ├── Cloud — [NOT OPENED]
 ├── Security — [NOT OPENED]
 ├── Display — single toggle: "Visible content — Show your open
 │              document or overview when in standby" (off). NO sleep
 │              timeout here.
 ├── Accessibility — Toolbar position Portrait Left / Landscape Left
 │              (drag the hide/show button to move it); Handedness
 │              Right/Left; Readability Standard/Large. (Nothing changed;
 │              read-only visit.)
 └── Help — [NOT OPENED]
 ```

 Harness notes: Back (top-left) walks one level up. Toolbar position is
 a setting — never assume left-edge toolbar in pixel paths; confirm
 from a screenshot (this tablet: left).

## 11. Empty, offline, error states

| State | Appearance | Automation rule |
|---|---|---|
| Empty folder | Empty grid / blank template page, no error | Treat as success-with-zero-items, not failure |
| Offline (no WiFi) | No WiFi icon; sync/Connect/Drive/email actions gated or hidden | Never attempt cloud actions; prefer USB/SSH path |
| Missing glyphs | Tofu boxes (□) in titles | Install Noto coverage + `fc-cache` + restart xochitl |
| EPUB image-drop bug (fw 3.0.5.56) | Images missing after import | Pre-convert with Calibre before upload |
| Full root partition (`df /` = 100%) | SSH password screen goes blank | `journalctl --vacuum-size=1M` over SSH, then re-read password |
| Factory reset | Keys wiped, SSH password regenerated | Re-install keys + re-record password before continuing |

## 12. Fonts

- **Noto** — UI font, all-languages coverage. Lives under standard
  fontconfig dirs; add weights there, rebuild with `fc-cache`, restart
  xochitl.
- **EB Garamond** — serif for reading, **latin-only**. Non-latin text
  set in it falls back or boxes — check CJK/emoji titles.
- On-device keyboard has unicode limits; avoid emoji/CJK in file names
  created on-device.

## 13. E-ink design DO / DON'T (for developers)

DO:

- High-contrast static layouts; black on white, generous whitespace.
- Design to the 1404 × 1872 portrait safe area; ≥ 60 px edge margins.
- Thick monochrome icons and ≥ 24 px-equivalent type.
- Deterministic waits + screenshot verify after every state change
  (panel needs ~0.5–1 s to settle; render latency ~100–450 ms).
- Confirm destructive actions (reformat, delete, reset) against a fresh
  screenshot.

DO NOT:

- Animate, hover-preview, or color-code meaning (no backlight, B/W only).
- Use small gray body text (ghosts and washes out).
- Fire rapid successive refreshes (ghosting; full-flash INIT cycles).
- Assume instant render — always wait, then verify.
- Put emoji/CJK in on-device titles (missing glyphs ⇒ boxes).
- Drive Paper Pro color/frontlight controls on rM2.

## 14. Paper Pro deltas (flagged, never mixed)

- Color ink + frontlight (`/sys/class/backlight/rm_frontlight`) —
  rM2 has neither.
- SSH needs **Developer Mode first** (forces factory reset, voids
  warranty for defects it causes, shows boot warning) + same
  `rm-ssh-over-wlan on` gate.
- Rootfs read-only + OverlayFS on parts of `/etc` (`mount -o
  remount,rw /` + `umount -R /etc` dance; overlays return on reboot).
- Different CPU arch — rM1/rM2 binaries need recompilation; Toltec
  unsupported; rm2fb/VNC-server address tables do not apply.
- Recovery is official (support Software-recovery article + Linux-host
  recovery tool); rM2 recovery needs a custom pogo jig + SBU1/SBU2
  short — avoid needing it.

## Sources

- Official specs: https://remarkable.com/products/remarkable-2
- Type Folio: https://remarkable.com/products/remarkable-2/type-folio
- Writing tools: https://remarkable.com/explore/article/level-up-writing-skills
- Perfect shapes: https://remarkable.com/explore/article/how-to-draw-perfect-shapes
- Folders vs tags: https://remarkable.com/explore/article/folders-vs-tags-organization-guide
- Annotation layers: https://remarkable.com/explore/article/7-ways-to-annotate-documents
- Typing: https://remarkable.com/explore/article/integrate-typing-and-handwriting
- Templates: https://remarkable.com/explore/article/made-for-getting-started
- Gesture map (ddvk hacks): https://github.com/ddvk/remarkable-hacks
- Notebook/page/layer model + Quick sheets + sleep PNG:
  https://remarkable.jms1.info/definitions.html
- Template tech (1404 × 1872 PNG/SVG): https://remarkable.jms1.info/faq/file-types.html
- Fonts: https://remarkable.jms1.info/info/fonts.html
- Filesystem / UUID sidecars: https://remarkable.jms1.info/info/filesystem.html
- Eraser semantics: https://remarkable.jms1.info/faq/eraser.html
- Network / Help path: https://remarkable.jms1.info/info/network.html
- Physical layout: https://remarkable.jms1.info/faq/cases.html
- Ecosystem index: https://github.com/reHackable/awesome-reMarkable
- Community guide: https://remarkable.guide/ — Toltec: https://toltec-dev.org/
