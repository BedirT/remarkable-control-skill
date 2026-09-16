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
| reStream (+ `restream.arm.static`) | https://github.com/rien/reStream | On-device Rust reader (fb / `:mem:`) → lz4 → SSH stdout, or raw TCP `nc :16789` with `-u` | Streaming video; pipe latency in the hundreds of ms (ffmpeg buffering + lz4 CPU); `-u` raises fps / lowers CPU `[INFERENCE ~5–15 fps USB]` | v1.5.0 lineage; fw branches for 3.7 / 3.24 / 3.27; Toltec + vellum packages (Toltec: OS <= 3.3.2); semi-active | Continuous interaction streams; `./reStream.sh -p` portrait, `-o cap.mp4` record, `-m` throughput check |
| rmview — VNC-server backend | https://github.com/bordaigorl/rmview | RFB/VNC to rM-vnc-server `:5900` (libvncserver ZRLE, damage-tracked, REMARKABLE_ENCODING 5000; optional SSH tunnel) | Author-tested best of breed; negligible latency + smooth drawing over USB; WiFi + SSH tunnel stutters | Active; auto / screenshare / vncserver backends; ships `bin/rM2-vnc-server-standalone` | Interactive sessions on fw ≤ 2.8; live view + PNG save + pen tracking |
| rmview — ScreenShare backend | https://github.com/bordaigorl/rmview | Official ScreenShare: TLS VNC `:5900` + UDP `:5901` timestamp broadcast; auth `sha256(ts + sha256(auth0-userid))`, userid from devicetoken JWT | Throttled by official stack `[INFERENCE ~5–10 fps]` | Active; **only path on fw ≥ 2.9** (compat table: VNC / rm2fb fail there) | Only forward-compatible capture choice; also the Paper Pro path |
| rM-vnc-server (tablet server) | https://github.com/pl-semiotics/rM-vnc-server | libvncserver + damage tracking (rM1 `mxc_epdc_fb_damage`; rM2 libqsgepaper-snoop `LD_PRELOAD`) | Same as VNC row (server side) | Prebuilt releases; **rM2 broken on fw ≥ 2.9** — use ScreenShare there | Server half of the VNC path on old firmware |
| rm2fb server / client / shim + xofb | https://github.com/ddvk/remarkable2-framebuffer | On-device IPC: `LD_PRELOAD librm2fb_server.so` into xochitl + `librm2fb_client.so` shim via shm (`/dev/shm/swtfb.*`, `/dev/shm/xofb` rgb565) + message queues; xofb hooks the QImage ctor | Not a streamer — enabler (N/A fps) | Beta; per-fw hardcoded addresses (`config.cpp` 2.4.0 → 2.15.x + `/etc/rm2fb.conf` override); Toltec package (Toltec: OS <= 3.3.2); new-fw support tracked in issue #18 | Making third-party display code work on rM2; prerequisite for libremarkable-on-rM2 |
| libremarkable framebuffer | https://github.com/canselcik/libremarkable | On-device Rust: `mmap(/dev/fb0)` + `MXCFB_SEND_UPDATE` / `WAIT_FOR_UPDATE_COMPLETE` ioctls (rM1) or SwtfbClient (rM2, needs rm2fb server); `examples/screenshot.rs` dumps rgb565le → PNG | N/A (single-shot dump) | Active (MSRV 1.80); rM2 path needs Toltec display / rm2fb server | On-device native screenshots; writing custom on-tablet agents |
| Official ScreenShare (in-box feature) | In-box firmware; driven via rmview backend | Same TLS-VNC as ScreenShare row | Same | In-box on current fw; only forward-compatible Paper Pro choice `[INFERENCE]` | Zero-install capture once started on the tablet (one manual tap) |

Backend picker:

- fw ≥ 2.9 or Paper Pro → ScreenShare backend (start ScreenShare on
  the tablet first — the one manual step).
- fw ≤ 2.8 → VNC-server or reStream.
- rm2fb / VNC-server on ≥ 2.9 is a dead end.
- USB-RNDIS (`10.11.99.1`) beats WiFi for every row; single-shot
  `cat` + `ffmpeg` beats streaming for verify steps.

## 2. Input injection

| Tool | Repo | Lang / needs | Status | Use for |
|---|---|---|---|---|
| libevdev (C read + uinput) | https://gitlab.freedesktop.org/libevdev/libevdev — docs http://www.freedesktop.org/software/libevdev/doc/latest | C, reMarkable toolchain | Maintained upstream | Robust on-device injector; prefer over raw ioctls |
| python-evdev | https://github.com/gvalkov/python-evdev — docs https://python-evdev.readthedocs.io/ | Python; needs pip/opkg (`pyevdev`) on device | Maintained upstream | `UInput`, `grab_context`, `evtest.py` clone; fastest scripting path |
| evemu (record / replay) | https://gitlab.freedesktop.org/libevdev/evemu | C tools, cross-compiled | Maintained upstream | `evemu-record` / `play` / `describe` gesture macros |
| evtest | https://gitlab.freedesktop.org/libevdev/evtest (or Toltec `opkg install evtest` (Toltec: OS <= 3.3.2)) | Binary on device | Maintained upstream | Capability dumps, absinfo maxima, live event watches |
| oxide `inject_evdev` | https://github.com/Eeems-Org/oxide/tree/master/applications/inject_evdev | C++ (Qt-era precedent) | Precedent, stable | String-to-evdev writer covering ABS/KEY/SYN/REL |
| rust `evdev` crate | https://docs.rs/evdev/latest/evdev/ | Rust | Maintained upstream | Alternative injector stack |
| node `evdev` | https://www.npmjs.com/package/evdev | Node | Community | Alternative injector stack |

Ground truth behind all of them: `event0` = gpio-keys (`KEY_POWER`
only), `event1` = Wacom pen, `event2` = Type-B multitouch; inject via
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

1. **Observe:** reStream single-shot or ScreenShare backend (by
   firmware) → PNG → byte-size check (5 256 576 B for a 16-bit full
   frame).
2. **Act (bytes):** USB web UI (`curl` against `10.11.99.1`) or SSH +
   rsync against `/home/root/.local/share/remarkable/xochitl/`
   (stop xochitl before writing the tree, restart after).
3. **Act (pixels):** python-evdev / libevdev uinput injector
   (tap/swipe scripts shipped; pen stroke + KEY_POWER via the 03 section-5 pattern (no dedicated script)).
4. **Render ink:** rmscene / rmc for v6; `rmapi geta` only for basic
   PDF+annotations while rmapi lasts.
5. **Self-host (optional):** rmfakecloud + proxy for sync/WebDAV/FTP;
   re-enable the proxy after every OS update.
