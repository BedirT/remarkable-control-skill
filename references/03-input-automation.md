# Input automation — reMarkable 2 (1404×1872)

Target: reMarkable 2 only. Paper Pro deltas are flagged `PAPER-PRO` inline —
never reuse rM2 node names, paths, or coordinate maxima there.

Grounding: kernel event-codes / multi-touch-protocol / uinput docs,
`remarkable.guide/devel/device/input.html`, svenar hexdump captures,
oxide#48 node mapping, oxide `inject_evdev` + `evdevdevice` precedents,
python-evdev / libevdev docs.

## 1. Device mapping (rM2)

| Node | Name / by-path | Function |
|---|---|---|
| `/dev/input/event0` | `gpio-keys` / `by-path/platform-gpio-keys-event` | Power button only (rM2 has NO home buttons; rM1 differed) |
| `/dev/input/event1` | Wacom digitizer / `by-path/platform-30a20000.i2c-event-mouse`; also `touchscreen0 -> event1` (misleading name) | Pen: hover, touch, pressure, tilt, eraser |
| `/dev/input/event2` | Cypress TTSP / `by-path/platform-30a40000.i2c-event` | Capacitive finger touch, Type-B MT |

`PAPER-PRO`: node numbers/names WILL differ (new SoC, changed DT
addresses). Rediscover via §2, do not reuse the by-path strings above.

## 2. Discovery — NEVER hardcode event numbers

```sh
# Names for every node (EVIOCGNAME equivalent, no extra packages):
grep -H . /sys/class/input/event*/device/name
# Capabilities bitmask per node:
cat /sys/class/input/event2/device/capabilities/*
# Canonical symlink check (event1 on rM2, event0 on rM1):
readlink /dev/input/touchscreen0
# Confirm hardware generation:
cat /sys/devices/soc0/machine   # expect: reMarkable 2.0
# Full caps + axis ranges (needs evtest: Toltec/entware `opkg install evtest`,
# or python-evdev's evtest.py clone):
evtest /dev/input/event2
```

`evtest` output shape:

```
Event: time ..., type 3 (EV_ABS), code 57 (ABS_MT_SLOT), value 0
Event: time ..., type 3 (EV_ABS), code 58 (ABS_MT_TRACKING_ID), value 7189
Event: time ..., type 3 (EV_ABS), code 53 (ABS_MT_POSITION_X), value 546
Event: time ..., type 3 (EV_ABS), code 54 (ABS_MT_POSITION_Y), value 800
Event: time ..., type 0 (EV_SYN), code 0 (SYN_REPORT), value 0
```

Get axis minima/maxima from the `evtest` caps dump or `EVIOCGABS`
ioctl at runtime. Touch X/Y map to screen pixels; pen X/Y are Wacom
digitizer units (5-digit) and need scaling (§4).

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
- Touch `ABS_MT_POSITION_X` ∈ [0, 1404), Y ∈ [0, 1872) — rM2 needs no
  X-inversion (rM1 needed `WIDTH-X`); Y may still need `HEIGHT-Y` in raw
  replay stacks (Qt handles it). Verify orientation on-device with a tap
  + screenshot before scripting a flow.
- Pen: scale digitizer units to pixels at runtime, never hardcode maxima:

```python
px = raw_x * 1404 // x_max
py = raw_y * 1872 // y_max   # maxima from EVIOCGABS / evtest caps
```

- Pressure/distance/tilt are auxiliary — set plausible values, not exact
  ones. Eraser end = `BTN_TOOL_RUBBER` instead of `BTN_TOOL_PEN`.

## 5. Injection — uinput is the ONLY supported path

Writing bytes to `/dev/input/eventN` does NOT inject (read-only from an
app's view). Create a `/dev/uinput` virtual device with matching
`EV_KEY`+`EV_ABS` bits + absinfo, then `write()` frames. `sendevent`
(Android toolbox) is NOT shipped on stock rM2; libevdev-C via the
reMarkable toolchain always works; oxide `inject_evdev` is the on-device
precedent. python-evdev needs `pip install evdev` on the host for syntax
checks (Toltec/opkg on-device package name: `pyevdev`).

Tap (python-evdev, touch-node clone):

```python
from evdev import UInput, ecodes as e
caps = {e.EV_KEY: [e.BTN_TOUCH],
        e.EV_ABS: [(e.ABS_MT_SLOT, (0, 1, 0, 0)),
                   (e.ABS_MT_TRACKING_ID, (0, 65535, 0, 0)),
                   (e.ABS_MT_POSITION_X, (0, 1403, 0, 0)),
                   (e.ABS_MT_POSITION_Y, (0, 1871, 0, 0)),
                   (e.ABS_MT_PRESSURE, (0, 255, 0, 0))]}
ui = UInput(caps, name='rm2-touch-inject')
x, y = 702, 936
ui.write(e.EV_ABS, e.ABS_MT_SLOT, 0)
ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 42)
ui.write(e.EV_ABS, e.ABS_MT_POSITION_X, x)
ui.write(e.EV_ABS, e.ABS_MT_POSITION_Y, y)
ui.write(e.EV_ABS, e.ABS_MT_PRESSURE, 60)
ui.write(e.EV_SYN, e.SYN_REPORT, 0)                          # down
ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 0xFFFFFFFF)         # up (-1)
ui.write(e.EV_SYN, e.SYN_REPORT, 0)
ui.close()
```

Swipe (same device, interpolated frames, deterministic timing):

```python
import time
steps, t0, t1 = 24, (200, 1500), (1200, 400)
ui.write(e.EV_ABS, e.ABS_MT_SLOT, 0)
ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 43)
for i in range(steps + 1):
    x = int(t0[0] + (t1[0] - t0[0]) * i / steps)
    y = int(t0[1] + (t1[1] - t0[1]) * i / steps)
    ui.write(e.EV_ABS, e.ABS_MT_POSITION_X, x)
    ui.write(e.EV_ABS, e.ABS_MT_POSITION_Y, y)
    ui.write(e.EV_ABS, e.ABS_MT_PRESSURE, 60)
    ui.write(e.EV_SYN, e.SYN_REPORT, 0)
    if i < steps:
        time.sleep(0.012)   # ~12 ms between frames, none after the final frame before lift; then settle 0.5-1.0 s after lift, verify by screenshot
ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 0xFFFFFFFF)
ui.write(e.EV_SYN, e.SYN_REPORT, 0)
```

Pen stroke: same pattern on pen caps (`BTN_TOOL_PEN=1, BTN_TOUCH=1,
ABS_X/Y, ABS_PRESSURE 0..~2000, ABS_TILT_X/Y`) with per-frame
`SYN_REPORT`; hover = `BTN_TOOL_PEN=1, BTN_TOUCH=0, ABS_DISTANCE>0`.

Power key (or headless `systemctl suspend` instead):

```python
ui.write(e.EV_KEY, e.KEY_POWER, 1)
ui.write(e.EV_SYN, e.SYN_REPORT, 0)
time.sleep(0.1)
ui.write(e.EV_KEY, e.KEY_POWER, 0)
ui.write(e.EV_SYN, e.SYN_REPORT, 0)
```

Ready-made scripts: `scripts/rm-tap.py` (tap), `scripts/rm-swipe.py`
(swipe) — both support `--dry-run` for host-side validation, plus
`--settle` (tap) and `--steps` / `--step-delay` / `--settle` (swipe).
Bounds: `--steps` in [1, 200], `--settle` / `--step-delay` finite in
[0, 5], with `steps × step-delay` capped at 10 s total (over → exit 2); zero-length swipes warn; fixed tracking IDs (42 tap / 43 swipe),
no concurrent runs. BTN_TOUCH is advertised in caps for compatibility;
per-frame emission is ABS+SYN only, matching on-device evtest captures.

## 6. xochitl coexistence

xochitl (Qt) holds all three nodes open. uinput events merge at kernel
level, so xochitl WILL react — desired for UI automation. To suppress
side effects during raw pen capture/replay:

- (a) Short critical sections: exclusive `EVIOCGRAB`
  (`with dev.grab_context()` in python-evdev; oxide evdevdevice
  `lock()`/`unlock()` + `clear_buffer()` flood precedent). Prefer this.
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
2. Capture via `scripts/rm-screenshot.sh` and confirm the expected UI
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
