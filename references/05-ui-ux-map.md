# 05 — reMarkable 2 UI/UX Map

Designer-usable map of the stock rM2 interface. Target canvas is
**1404 × 1872 portrait**. All paths verified against scout reports;
uncertain items are marked `[INFERENCE]` or `[MED]` (medium confidence —
confirm on-device before pixel-driving).

Paper Pro deltas are flagged inline and **never mixed** into rM2 procedures.

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
│   ├── Left toolbar (collapsible, 9 tools)
│   ├── Top doc menu (via swipe-down-from-top)
│   └── Bottom page navigator (+ add page)
└── Quick sheets (auto notebook pinned in My-files root)
Overlays (from any screen): Share/export · Document settings ·
    Page settings · Settings tree · Help · Search · Power menu
```

### 2.1 My files (home)

- Grid or list of folders + documents. Top row: hamburger menu,
  search icon, "new" (create notebook/folder), sort order.
- Left sidebar filters: **My files / Favorites / Notebooks / PDFs /
  Ebooks**. Selecting a filter scopes the grid.
- Bottom strip: WiFi icon (absent when offline), battery, storage/about
  shortcut. The GPLv3 password/IP page lives under
  Menu > Settings > Help > Copyright and licenses (OS < 3.9 or > 3.18;
  OS 3.9–3.18 takes a detour via an "About" entry inside Help).
- Quick-sheets entry point lives here (see §7).

### 2.2 Top bar, hamburger, search

| Element | Location | Opens |
|---|---|---|
| Hamburger (≡) | Top-left | Main menu: New notebook/folder, sort, view toggle, Settings, Help |
| Search (magnifier) | Top bar | Search overlay incl. handwriting search (needs Connect account) |
| New (+) | Top bar | Create notebook / folder / Quick-sheet page |
| Sort | Top bar | Name / modified / type ordering |
| WiFi / battery | Bottom strip | Status only (no action); offline ⇒ sync/Connect/Drive actions gated |

### 2.3 Document view

- **Canvas layers (bottom → top):** template-or-PDF base layer →
  one or more ink/pen layers → annotation layer (hide/show toggle) →
  selection/highlight overlays. PDF originals stay unmodified;
  strokes are stored as overlays.
- **Left toolbar:** collapsible vertical strip, 9 tools (see §4).
- **Top doc menu:** revealed by swipe-down-from-top; document title,
  Share, Document settings, Page settings, close.
- **Bottom page navigator:** page thumbnails / page number, swipe or
  tap to move, "+" adds a page (notebook) or blank page (PDF).

## 3. Overlays

| Overlay | Entry | Contents |
|---|---|---|
| Share / export | Top doc menu → Share | Export PDF/PNG, send via email/Drive/Connect (needs network + account) |
| Document settings | Top doc menu | Shapes-assist toggle, orientation, language for handwriting conversion |
| Page settings | Bottom navigator / doc menu | Per-page template pick, add/duplicate/reorder/delete page |
| Settings | Hamburger → Settings | Tree, see §9 (partial — gaps flagged) |
| Help | Hamburger → Help | Guides, Copyrights and licenses (SSH password + IPs under GPLv3 header) |
| Search | Top-bar magnifier | File-name search; handwriting-content search with Connect |
| Power menu | Long-press power button | Sleep, power off, restart, (cancel) |

## 4. Toolbar — 9 writing tools

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
| Swipe down from top edge | Document view | Closes document → back to My files (also reveals top doc menu on partial swipe) |
| Tap left / right edge | Reading Mode (PDF/EPUB) | Previous / next page |
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
  screenshot verify, never blind-tap.
- **Annotation layer:** separate hide/show toggle; hiding it shows the
  clean base document.
- **Folders vs tags:** hybrid organization — folders in the file tree
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
  → off**. Auto-sleep timeout is set in Settings `[MED exact values —
  capture on-device]`.
- Sleep PNG: exactly 1404 × 1872 8-bit gray; static screens are
  **reset on OS upgrade**.
- Wake: press power, open folio, or (over USB) any SSH activity does
  NOT wake the panel — verify wake by fresh screenshot.

## 10. Settings tree (PARTIAL — gaps flagged)

```
Settings
├── General — UI language (EN/DE/FR/ES), left-hand mode,
│              auto-sleep timeout [MED values], Account setup
├── WiFi — network list, connect, status
├── Storage — usage, USB web interface toggle, about
├── Update — check / install OS update
├── Security — device lock passcode/PIN
└── Help — guides, About [3.9–3.18 only],
           Copyrights and licenses → GPLv3 block
               (SSH root password + IP addresses)
[INFERENCE — full subtree below each node unverified:
 support site is JS-gated and the device manual 403'd at fetch time.
 Capture the complete tree on-device before baking pixel paths.]
```

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
