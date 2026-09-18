# 06 — Tooling Ecosystem

Comparison matrix for every tool class an autonomous rM2 controller may
meet. Status as of 2026-09-15, grounded in scout reports. Prefer the
"Use for" column over familiarity: each tool covers one plane (capture /
input / files), and mixing planes causes flakiness.

> Rule of thumb: **observe** with a capture tool, **act** with uinput or
> the file APIs, **verify** with a fresh screenshot. Never use a file
> tool to do a screen's job or an input injector to move bytes.

## 1. Screen capture / streaming

| Tool | Repo | Transport | Reported perf | Status | Use for |
|---|---|---|---|---|---|
| `scripts/rm2ctrl-capture.py` (this repo) | references/02-display-screenshot.md §2 | xochitl's composed QImage (1404×1872 RGB32) → raw dd over `rm2ctrl-ssh.sh` stdout → host PNG; pre/post rechecks | ~5 s per shot, ~16–30 SSH ops | Proven live 2026-09-16 on fw 20260827113527 | Headless single-shot capture with zero tablet setup; byte-exact repeats, tracks pen strokes |
| Official ScreenShare (+ rmview backend) | In-box firmware; https://github.com/bordaigorl/rmview | TLS VNC `:5900` + UDP `:5901` | Start ScreenShare on the tablet first (one manual tap) | Second option when 02 §2 fails; Paper Pro path |

Backend picker:

- 2026 fw (20260827113527) → `scripts/rm2ctrl-capture.py` (02 §2, no tablet step).
- If it fails → stop on ABORT in strict mode (02 §3); ScreenShare/photo only if the user allows a human step.
- USB (`10.11.99.1`) beats WiFi for every row.

## 2. Input injection

| Tool | Repo | Lang / needs | Status | Use for |
|---|---|---|---|---|
| libevdev (C read + uinput) | https://gitlab.freedesktop.org/libevdev/libevdev — docs http://www.freedesktop.org/software/libevdev/doc/latest | C, reMarkable toolchain | Maintained upstream | Robust on-device injector; prefer over raw ioctls |
 | python-evdev | https://github.com/gvalkov/python-evdev — docs https://python-evdev.readthedocs.io/ | Python; needs pip/opkg (`pyevdev`) on device | Maintained upstream | Superseded on stock fw (no Python on tablet): use `scripts/rm2ctrl-input/` helper instead; still fine for host-side prototyping |
| evemu (record / replay) | https://gitlab.freedesktop.org/libevdev/evemu | C tools, cross-compiled | Maintained upstream | `evemu-record` / `play` / `describe` gesture macros |
| evtest | https://gitlab.freedesktop.org/libevdev/evtest (or Toltec `opkg install evtest` (Toltec: OS <= 3.3.2)) | Binary on device | Maintained upstream | Capability dumps, absinfo maxima, live event watches |
| oxide `inject_evdev` | https://github.com/Eeems-Org/oxide/tree/master/applications/inject_evdev | C++ (Qt-era precedent) | Precedent, stable | String-to-evdev writer covering ABS/KEY/SYN/REL |
| rust `evdev` crate | https://docs.rs/evdev/latest/evdev/ | Rust | Maintained upstream | Alternative injector stack |
| node `evdev` | https://www.npmjs.com/package/evdev | Node | Community | Alternative injector stack |

 Ground truth behind all of them (probed live 2026-09-17): `event0` =
 `30370000.snvs:snvs-powerkey` (`KEY_POWER` only), `event1` = Wacom pen,
 `event2` = `pt_mt` Type-B multitouch; inject via
`/dev/uinput` virtual devices only — writing `/dev/input/eventN` does
not inject; `sendevent` is not shipped stock. Kernel references:
https://www.kernel.org/doc/html/v5.4/input/event-codes.html,
https://www.kernel.org/doc/html/v5.4/input/multi-touch-protocol.html,
https://www.kernel.org/doc/html/v5.4/input/uinput.html,
https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h,
https://github.com/reMarkable/linux.

## 3. File / content / cloud

| Tool | Repo | Lang | Status | Use for |
|---|---|---|---|---|
| rmapi | https://github.com/juruen/rmapi | Go | **UNMAINTAINED (archiving; discussion #313)**; experimental new-sync support (`get` works, `put` flaky) | Cloud shell + scripting while it lasts: `ls/get/mget/put/mput/geta/mkdir/rm/mv` |
| rmfakecloud | https://github.com/ddvk/rmfakecloud — setup https://ddvk.github.io/rmfakecloud/remarkable/setup/ | Go | **MAINTAINED (sync tested to SW 3.27.1)** | Self-hosted sync; WebDAV/FTP bridge; HWR; screen share; calendar ICS; webhook; PIN reset (rM1/2) |
| rmfakecloud-proxy | https://github.com/ddvk/rmfakecloud-proxy | Go/sh | Maintained (low churn) | Redirecting the tablet to a self-hosted cloud (Toltec `opkg install rmfakecloud-proxy` (Toltec: OS <= 3.3.2) or on-device installer) |
| rmscene | https://github.com/ricklupton/rmscene | Python | Maintained (v0.8.0, CRDT fixes) | Parsing v6 scene trees + text |
| rmc | https://github.com/ricklupton/rmc | Python | Maintained | v6 `.rm` → svg/pdf/md and md → rm |
| lines-are-beautiful | https://github.com/ax3l/lines-are-beautiful | C++ | **STALE (v3/v5 era)** | Legacy `.lines` parsing + format reference only |
| ReMarkableAPI | https://github.com/splitbrain/ReMarkableAPI | PHP | **UNMAINTAINED** | Reverse-engineered API endpoint documentation reference |
| Toltec | https://toltec-dev.org/ — packages https://github.com/toltec-dev/toltec | opkg | **PARTIAL (OS ≤ 3.3.2, no Paper Pro)** | On-device packages (evtest, restream, rm2fb, proxy) |
| rclone | https://rclone.org/overview/ | Go | **N/A — no reMarkable backend** (`/remarkable/` 404s) | Do NOT promise `rclone lsd remarkable:` — bridge via rmfakecloud WebDAV/FTP remotes instead |
| USB web interface extensions | https://github.com/rM-self-serve/webinterface-wifi (siblings: webinterface-onboot, webinterface-upload-button) | Shell | Community-maintained | WiFi exposure (+auth/SSL), serve-on-boot, upload button |

Negative results worth knowing: there is **no official public cloud
API** (developer.remarkable.com covers on-device SDK/Qt/SSH only) and
**no rclone backend** — both verified by direct 404/negative fetch, not
inference. The stock USB web UI (`http://10.11.99.1/`) is the primary
autonomy file path: `GET /documents/`, `GET /documents/{guid}`,
`GET /download/{guid}/pdf`, `GET /download/{guid}/rmdoc` (v3.9+),
`POST /upload` (multipart, `Origin: http://10.11.99.1`, lands in the
last-listed folder — list the target folder first), `GET
/thumbnail/{guid}`, `GET /log.txt`, `POST /search/{keyword}` (beta).

## 4. Ecosystem indexes

| Index | URL | Note |
|---|---|---|
| awesome-reMarkable | https://github.com/reHackable/awesome-reMarkable | 7.7k★ curated index (ddvk-hacks, rmkit, guides); start here for anything not above |
| Community access guide | https://remarkable.guide/ | SSH, USB web UI, developer-mode, recovery procedures |
| jms1 reference | https://remarkable.jms1.info/ | Definitions, file types, fonts, filesystem, eraser, network |
| Developer portal | https://developer.remarkable.com/documentation/developer-mode | Paper Pro dev-mode + recovery tooling |

## 5. Recommended minimal kit (autonomy default)

1. **Observe:** `scripts/rm2ctrl-capture.py` → PNG + 10 513 152 B raw (02 §2).
2. **Act (bytes):** USB web UI (`curl` against `10.11.99.1`) or SSH +
   rsync against `/home/root/.local/share/remarkable/xochitl/`
   (stop xochitl before writing the tree, restart after).
 3. **Act (pixels):** `/tmp/rm2ctrl-input` over `scripts/rm2ctrl-ssh.sh` (static
   `scripts/rm2ctrl-input/` uinput helper, scp'd to /tmp on first use;
   pen stroke + keys not implemented).
4. **Render ink:** rmscene / rmc for v6; `rmapi geta` only for basic
   PDF+annotations while rmapi lasts.
5. **Self-host (optional):** rmfakecloud + proxy for sync/WebDAV/FTP;
   re-enable the proxy after every OS update.
