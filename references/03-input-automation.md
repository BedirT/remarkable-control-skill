# Input automation — reMarkable 2 (1404×1872)

Target: reMarkable 2 only. Paper Pro deltas are flagged `PAPER-PRO` inline —
never reuse rM2 node names, paths, or coordinate maxima there.

 Grounding: kernel event-codes / multi-touch-protocol / uinput docs,
 `remarkable.guide/devel/device/input.html`, svenar hexdump captures,
 oxide#48 node mapping, oxide `inject_evdev` + `evdevdevice` precedents,
 python-evdev / libevdev docs — plus LIVE EVIDENCE 2026-09-17: static ARM
 helper `scripts/rm-input/` driving taps and swipes on-device, every act
 screenshot-verified (tile open, X close, grid scroll + byte-exact
 restore). Tap + swipe: WORKING. Pen stroke / KEY_POWER: not implemented.

 ## 1. Device mapping (rM2) — probed live 2026-09-17 (`rm-input --probe`)

 | Node | Name | Function |
 |---|---|---|
 | `/dev/input/event0` | `30370000.snvs:snvs-powerkey` | Power button only (rM2 has NO home buttons; rM1 differed) |
 | `/dev/input/event1` | `Wacom I2C Digitizer` (`touchscreen0 -> event1`, misleading name) | Pen: hover, touch, pressure, tilt, eraser |
 | `/dev/input/event2` | `pt_mt` | Capacitive finger touch, Type-B MT |

`PAPER-PRO`: node numbers/names WILL differ (new SoC, changed DT
addresses). Rediscover via §2, do not reuse the by-path strings above.

## 2. Discovery — NEVER hardcode event numbers

 ```sh
 # Names for every node (EVIOCGNAME equivalent, no extra packages):
 grep -H . /sys/class/input/event*/device/name
 # Capabilities bitmask per node:
 cat /sys/class/input/event2/device/capabilities/*
 # Confirm hardware generation:
 cat /sys/devices/soc0/machine   # expect: reMarkable 2.0
 # Full caps + axis ranges, no tablet-side packages (static helper):
 /tmp/rm-input --probe
 ```

 Live `--probe` output (fw 20260827113527 — the touchscreen block is the
 contract the helper clones):

 ```
 /dev/input/event0 30370000.snvs:snvs-powerkey ev=00000003
   key: [3]=00100000
   abs:
 /dev/input/event1 Wacom I2C Digitizer ev=0000000b
   key: [10]=00001c03
   abs: [0]=0f000003
   absinfo 00: val=7124 min=0 max=20966 fuzz=0 flat=0 res=100
   absinfo 01: val=9771 min=0 max=15725 fuzz=0 flat=0 res=100
   absinfo 18: val=0 min=0 max=4095 fuzz=0 flat=0 res=0
   absinfo 19: val=86 min=0 max=255 fuzz=0 flat=0 res=0
   absinfo 1a: val=-2700 min=-9000 max=9000 fuzz=0 flat=0 res=0
   absinfo 1b: val=1800 min=-9000 max=9000 fuzz=0 flat=0 res=0
 /dev/input/event2 pt_mt ev=0000000f
   key: [1]=f8000000 [2]=00000007
   abs: [0]=02000000 [1]=06f38000
   absinfo 19: val=0 min=0 max=255 fuzz=0 flat=0 res=0
   absinfo 2f: val=0 min=0 max=31 fuzz=0 flat=0 res=0
   absinfo 30: val=0 min=0 max=255 fuzz=0 flat=0 res=0
   absinfo 31: val=0 min=0 max=255 fuzz=0 flat=0 res=0
   absinfo 34: val=0 min=-127 max=127 fuzz=0 flat=0 res=0
   absinfo 35: val=0 min=0 max=1403 fuzz=0 flat=0 res=0
   absinfo 36: val=0 min=0 max=1871 fuzz=0 flat=0 res=0
   absinfo 37: val=0 min=0 max=1 fuzz=0 flat=0 res=0
   absinfo 39: val=0 min=0 max=65535 fuzz=0 flat=0 res=0
   absinfo 3a: val=0 min=0 max=255 fuzz=0 flat=0 res=0
 node=/dev/input/event2 x=[0..1403] y=[0..1871] uinput=present
 ```


`evtest` output shape:

```
Event: time ..., type 3 (EV_ABS), code 57 (ABS_MT_SLOT), value 0
Event: time ..., type 3 (EV_ABS), code 58 (ABS_MT_TRACKING_ID), value 7189
Event: time ..., type 3 (EV_ABS), code 53 (ABS_MT_POSITION_X), value 546
Event: time ..., type 3 (EV_ABS), code 54 (ABS_MT_POSITION_Y), value 800
Event: time ..., type 0 (EV_SYN), code 0 (SYN_REPORT), value 0
```

 Get axis minima/maxima from `/tmp/rm-input --probe` (§2 dump above) —
 no evtest on stock firmware. Touch X/Y map to screen pixels (§4 Y flip);
 pen X/Y are Wacom digitizer units (5-digit) and need scaling (§4).

Raw frame format (for log decoding only — never inject this way):
16-byte LE `struct input_event { timeval sec,usec; __u16 type,code;
__s32 value; }`, changes terminated by `EV_SYN/SYN_REPORT (0,0,0)`.
Bytes are LSB-first, e.g. `0300 0100 88210000` = type 3 `EV_ABS`,
code 1 `ABS_Y`, value 8584.

## 3. Event codes

Pen (event1):

```
EV_KEY BTN_TOOL_PEN (0x140)=1 / BTN_TOOL_RUBBER (0x141)=1  # tool in proximity
EV_KEY BTN_TOUCH (0x14a)=1/0                              # tip physically down
EV_ABS ABS_X (0x00), ABS_Y (0x01)
EV_ABS ABS_PRESSURE (0x18)  # idle 0, light ~3, firm ~163
EV_ABS ABS_DISTANCE (0x19)  # nonzero on hover, 0 at contact
EV_ABS ABS_TILT_X (0x1a), ABS_TILT_Y (0x1b)  # jittery, 32-bit wraparound seen — clamp/smooth
EV_SYN SYN_REPORT (0)
```

Touch (event2, Type-B slots): `ABS_MT_SLOT (0x2f)`,
`TRACKING_ID (0x39)`, `POSITION_X (0x35)`, `POSITION_Y (0x36)`,
`PRESSURE (0x3a)`, `TOUCH_MAJOR (0x30)`, `TOUCH_MINOR (0x31)`,
`ORIENTATION (0x34)`. New contact = fresh non-negative `TRACKING_ID`;
lift = `TRACKING_ID -1`. Empty-frame `SYN_MT_REPORT+SYN_REPORT` all-up
is Type-A legacy only — do not emit it.

Buttons (event0): `EV_KEY KEY_POWER (116)`: 1 = press, 0 = release,
2 = autorepeat. No `KEY_HOME` on rM2. Long-press suspend is
systemd/logind policy on top of this key.

## 4. Coordinate system

- Display: **1404 × 1872 portrait**. (Native panel is landscape
  1872×1404 with the pen at the bottom; Qt rotates to portrait.)
 - Touch device axes == screen pixels 1:1 in range, but device Y runs
   BOTTOM-up: raw `(57,61)` lands at screen bottom-left. PROVEN live
   2026-09-17 (raw tap opened the wrong tile; screenshot showed the
   flip; corrected mapping verified both directions). The helper takes
   SCREEN coords and applies `dev_y = 1871 - screen_y` internally —
   never pre-flip when using the scripts. No X inversion (rM1 needed
   `WIDTH-X`; rM2 does not).
- Pen: scale digitizer units to pixels at runtime, never hardcode maxima:

```python
px = raw_x * 1404 // x_max
py = raw_y * 1872 // y_max   # maxima from EVIOCGABS / evtest caps
```

- Pressure/distance/tilt are auxiliary — set plausible values, not exact
  ones. Eraser end = `BTN_TOOL_RUBBER` instead of `BTN_TOOL_PEN`.

 ## 5. Injection — static helper over uinput (WORKING, verified 2026-09-17)

 Writing bytes to `/dev/input/eventN` does NOT inject (read-only from an
 app's view). The supported path is `scripts/rm-input/`: a small Rust
 helper, statically linked for ARMv7 (`armv7-unknown-linux-musleabihf`),
 no tablet-side packages — stock firmware has no Python, no evtest, no
 `sendevent`. It creates a `/dev/uinput` virtual device cloning the real
 `pt_mt` caps (§2 block: all MT axes with probed ranges), emits full
 Type-B frames (SLOT + TRACKING_ID + POSITION_X/Y + PRESSURE 60 +
 TOOL_FINGER; swipe contact is finger-sized — MINOR alternating 8/17,
 MAJOR sparse every 3rd frame — because MAJOR/MINOR 40 is
 palm-rejected in doc view, proven by ablation 2026-09-18; taps keep
 40, they work everywhere), and destroys the node. Call it directly
 over the existing SSH session — no host wrapper, no Python involved.
 Args are SCREEN coords; the Y flip (§4) is applied inside the helper.

 ```sh
 # First use: copy it over (nothing installed, lives in /tmp):
 scp scripts/rm-input/rm-input root@10.11.99.1:/tmp/rm-input
 scripts/rm-ssh.sh -- chmod +x /tmp/rm-input
 # Then drive it (1 s sleep covers the e-ink settle before verifying):
 scripts/rm-ssh.sh -- /tmp/rm-input tap 513 1176; sleep 1
 scripts/rm-ssh.sh -- /tmp/rm-input swipe 700 1300 700 700 24 12; sleep 1
 scripts/rm-ssh.sh -- /tmp/rm-input --probe    # on-tablet caps dump
 scripts/rm-ssh.sh -- /tmp/rm-input replay     # verbatim owner finger pair
 ```

 Finger replay (page creation, VERIFIED 2/2 2026-09-18): the owner's
 double-swipe was recorded passively (`cat /dev/input/event2`, 154
 events, parsed host-side as 16-byte evdev structs) and baked into the
 helper as `replay` — device coords, relative-ms timing, no arguments.
 The real profile vs the old flat swipe: pressure RAMPS 69→114→90
 (not const 60); TOUCH_MAJOR mostly absent, 8/17 when present (not
 const 40); MINOR alternates 8/17; ORIENTATION 1-4 present (helper now
 advertises axis 0x34); NO tool-type, NO slot, NO BTN_TOUCH events;
 eased path ~440 px in 160-250 ms with a 2.5 s pair gap. Run it on a
 last-page canvas, then judge by NAVIGATOR page count (+1 per pair) —
 creation navigates to the new blank, so canvas bytes still match.

 Two timing lessons, both learned the hard way live:

 - 1 s device settle after `UI_DEV_CREATE` before the first event —
   Qt's inotify rescan must see the node or the gesture is silently
   dropped (150 ms was NOT enough; zero-frame taps did nothing). Built
   into the helper; never skip it.
 - 0.5 s linger after lift before `UI_DEV_DESTROY` (also in the helper),
   plus ~1 s host-side sleep for e-ink before the verify screenshot.
 - Page turning: prefer the "Go to page" navigator thumbnails (05 §2.3)
 over swipes — flat-profile synthetic swipes scroll the home grid but
 are NO-OP in doc view (×6). Page CREATION works via `replay` (see
 §5). And never trust "ok": one tap in ~50 was silently swallowed by
 Qt with no effect — verify every act.
 Bounds (enforced inside the helper — out-of-range input errors out,
 nonzero exit): tap X in [0, 1404), Y in [0, 1872); swipe adds STEPS
 in [1, 200], STEP_MS in [0, 5000]. Fixed tracking IDs (42 tap /
 43 swipe, 601/602 replay) — no concurrent runs.

 Rebuild the helper (prebuilt binary ships at `scripts/rm-input/rm-input`):

 ```sh
 cd scripts/rm-input
 RUSTFLAGS="-C link-self-contained=yes -C linker=rust-lld" \
   cargo build --target armv7-unknown-linux-musleabihf
 ```

 Live ink path is the `pend` daemon (§5b): one held pen node,
 strokes via `/tmp/pen.fifo`, SVG via `scripts/rm-svg.py --run`.
 (`pen`/`penraw`/`penpoly` one-shots still exist as protocol
 spares; the app never reads them.)
 Power control headless: `systemctl suspend` over SSH instead.

 ## 5b. Pen injection (WORKING 2026-09-18 — persistent node + env override)

 The Wacom I2C Digitizer was fully probed (`--probe`: X 0..20966,
 Y 0..15725 res 100, PRESSURE 0..4095, DISTANCE 0..255,
 TILT ±9000; keys TOOL_PEN/TOOL_RUBBER/TOUCH/STYLUS/STYLUS2;
 ids bus 0x18 vendor 0x2d1f product 0x0095 version 0x1231).
 The helper clones all of it. Qt has NO evdev tablet handler in
 this build (zero `evdevtablet` strings in libQt6Gui) — xochitl
 reads the pen through its own Digitizer thread, path from the
 `XOCHITL_DIGITIZER_PATH` env var (found via binary strings).

 Three hard lessons, each proven live:

 1. Hotplug pen nodes are IGNORED. xochitl opens hotplug finger
    clones instantly but never a pen node (0 opens over a 52 s
    hold, nor during live strokes). ~12 strokes through transient
    nodes: zero ink.
 2. Ink must flow through the HELD node. `pend` creates ONE pen
    device and reads strokes from `/tmp/pen.fifo`
    (`S STEPS STEP_MS P0 P1 X1 Y1 [X2 Y2 ...]`, screen coords,
    pressure ramps P0→P1 along the stroke, 1..4095, P0==P1 flat;
    `Q` quits; every stroke acked in the log as `S ok`). Proven
    live 2026-09-18: flat ladder 500/1500/2500/3800 shows four
    distinct weights plus a 200→4000 swell on ballpoint.
    Transient `pen`/`penraw`/`penpoly` nodes never reach the
    app — protocol spares only.
 3. Screen→digitizer mapping is digX = (1871−y)×11.199,
    digY = x×11.199 — the SAME Y flip as touch (5/5 dots exact,
    ±3 px). Hypothesis-no-flip drew mirrored; fixed in `map_pen`.

 Session recipe (needs one xochitl restart; real pen is dead while
 the override points at the clone — restore promptly):
 `setsid nohup /tmp/rm-input pend … &`, note its eventN,
 `systemctl set-environment XOCHITL_DIGITIZER_PATH=/dev/input/eventN`,
 `systemctl restart xochitl`, verify `/proc/<pid>/fd` shows the
 node, draw, then `systemctl unset-environment
 XOCHITL_DIGITIZER_PATH` (separate command — `--unset` is invalid)
 + `reset-failed` + restart and verify event1 is held again.
 Keep restarts clear of StartLimitBurst=4/600s
 (OnFailure=remarkable-fail.service); `reset-failed` first.

 Real-pen ground truth (passive `cat /dev/input/event1` while the
 owner draws): contact frame is TOUCH=1 + changed axes +
 PRESSURE jump (no ramp, ~2900) + DISTANCE 8→0; tilt sparse;
 100–200 Hz; no MSC/STYLUS traffic.


## 6. xochitl coexistence

xochitl (Qt) holds all three nodes open. uinput events merge at kernel
level, so xochitl WILL react — desired for UI automation. To suppress
side effects during raw pen capture/replay:

 - (a) Short critical sections: exclusive `EVIOCGRAB` ioctl on the node
   (oxide evdevdevice `lock()`/`unlock()` + `clear_buffer()` flood
   precedent). Prefer this.
- (b) Full takeover: `systemctl stop xochitl` (also stop `genie` if
  installed), then `systemctl start xochitl`
  (`daemon-reload; reset-failed xochitl; restart xochitl` recovery,
  Toltec FAQ pattern).

Hazard: two concurrent readers (xochitl + oxide/rm2fb) cause ~0.75 s lag
+ missed taps — never leave two consumers running. `QT_QPA_EVDEV_*` can
remap, but stop/grab is deterministic and autonomy-friendly.

## 7. Settle + screenshot verify (zero-interruption rule)

E-ink needs ~100–450 ms per refresh; ghosting lies. After every inject:

1. Sleep 0.5–1.0 s after lift (swipe: after the final `SYN_REPORT`).
2. Capture via `scripts/rm-capture.py --out verify.png` and confirm the expected UI
   state from the PNG — never assume the tap landed, never force an
   e-ink refresh to "check".
3. On mismatch: re-run discovery (§2), check orientation (§4), retry
   once before escalating.

## 8. Sources

- https://remarkable.guide/devel/device/input.html
- https://blog.svenar.nl/posts/exploring_remarkable_input_events/
- https://github.com/Eeems-Org/oxide/issues/48
- https://www.kernel.org/doc/html/v5.4/input/event-codes.html
- https://www.kernel.org/doc/html/v5.4/input/multi-touch-protocol.html
- https://www.kernel.org/doc/html/v5.4/input/uinput.html
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h
- https://www.freedesktop.org/wiki/Software/libevdev/
- https://github.com/gvalkov/python-evdev
- https://github.com/Eeems-Org/oxide/tree/master/applications/inject_evdev
- https://github.com/reMarkable/linux
