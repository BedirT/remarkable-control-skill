#!/usr/bin/env python3
"""rm-swipe.py — synthesize one finger swipe on reMarkable 2 via uinput.

Runs ON the tablet (python-evdev installed). Interpolates STEPS frames
between (X1,Y1) and (X2,Y2) at ~12 ms each, then lifts and settles.
Matches on-device evtest captures (ABS+SYN only; BTN_TOUCH is advertised
in caps for compatibility but not emitted per frame).
Fixed tracking ID 43; do not run concurrent swipes (shared virtual device).

Settle note: e-ink needs ~0.5-1.0 s after lift before a screenshot
verify; see references/03-input-automation.md §7.

Usage:
    rm-swipe.py X1 Y1 X2 Y2 [--steps N] [--step-delay SECS] [--settle SECS] [--dry-run]
    rm-swipe.py --help
"""
import argparse
import math
import sys
import time
from signal import SIG_BLOCK, SIG_DFL, SIGINT, SIGPIPE, SIG_SETMASK, SIGTERM, pthread_sigmask, signal
W, H = 1404, 1872  # rM2 portrait pixels; Paper Pro: re-query, never reuse
MAX_STEPS = 200


class _LoudParser(argparse.ArgumentParser):
    """ArgumentParser that fails loudly when help/error output cannot be
    written (e.g. full disk): stdlib swallows OSError from --help writes
    and still exits 0, hiding the lost output."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._write_failed = False

    def _print_message(self, message, file=None):
        if not message:
            return
        if file is None:
            file = sys.stderr
        try:
            file.write(message)
        except (OSError, ValueError):
            # OSError: ENOSPC/EPIPE on the output stream. ValueError: stream
            # already closed. Either way the text is lost — flag it so exit()
            # below reports failure instead of success.
            self._write_failed = True

    def exit(self, status=0, message=None):
        if message:
            self._print_message(message, sys.stderr)
        if self._write_failed:
            try:
                sys.stderr.write(
                    "error: cannot write output (disk full or stream closed)\n")
            except (OSError, ValueError):
                pass  # reporting stream broken too; exit code still honest
            status = 1
        super().exit(status)


def parse_args(argv=None):
    p = _LoudParser(
        description="Synthesize one Type-B MT finger swipe on reMarkable 2 via uinput."
    )
    p.add_argument("x1", type=int, nargs="?", help="start X in [0, 1404)")
    p.add_argument("y1", type=int, nargs="?", help="start Y in [0, 1872)")
    p.add_argument("x2", type=int, nargs="?", help="end X in [0, 1404)")
    p.add_argument("y2", type=int, nargs="?", help="end Y in [0, 1872)")
    p.add_argument("--steps", type=int, default=24,
                   help=f"interpolated frames, [1, {MAX_STEPS}] (default: 24; steps x step-delay capped at 10s total)")
    p.add_argument("--step-delay", type=float, default=0.012,
                   help="seconds between frames, [0, 5] (default: 0.012; steps x step-delay capped at 10s total)")
    p.add_argument("--settle", type=float, default=0.8,
                   help="seconds to sleep after lift for e-ink settle, [0, 5] (default: 0.8)")
    p.add_argument("--dry-run", action="store_true",
                   help="print start/end/steps without touching /dev/uinput (no device needed)")
    return p.parse_args(argv)


def points(x1, y1, x2, y2, steps):
    """Interpolated integer points inclusive of both ends; pure, no device."""
    if steps < 1:
        raise ValueError(f"steps must be >= 1, got {steps}")
    return [(int(x1 + (x2 - x1) * i / steps),
             int(y1 + (y2 - y1) * i / steps)) for i in range(steps + 1)]


def main(argv=None):
    # Piped to a closed reader (e.g. --dry-run | head): die silently by
    # signal instead of a BrokenPipeError traceback.
    signal(SIGPIPE, SIG_DFL)
    args = parse_args(argv)
    if None in (args.x1, args.y1, args.x2, args.y2):
        print("error: X1 Y1 X2 Y2 are required (see --help)", file=sys.stderr)
        return 2
    for v, mx, n in ((args.x1, W, "X1"), (args.x2, W, "X2")):
        if not 0 <= v < mx:
            print(f"error: {n}={v} outside [0, {mx})", file=sys.stderr)
            return 2
    for v, mx, n in ((args.y1, H, "Y1"), (args.y2, H, "Y2")):
        if not 0 <= v < mx:
            print(f"error: {n}={v} outside [0, {mx})", file=sys.stderr)
            return 2
    if not 1 <= args.steps <= MAX_STEPS:
        print(f"error: --steps must be in [1, {MAX_STEPS}], got {args.steps}", file=sys.stderr)
        return 2
    for v, n in ((args.step_delay, "--step-delay"), (args.settle, "--settle")):
        if not math.isfinite(v) or not 0 <= v <= 5:
            print(f"error: {n} must be a finite number in [0, 5], got {v}", file=sys.stderr)
            return 2
    total = args.steps * args.step_delay
    if total > 10:
        print(f"error: total swipe time {total:.17g}s (steps x step-delay) exceeds 10s cap; reduce --steps or --step-delay", file=sys.stderr)
        return 2
    if (args.x1, args.y1) == (args.x2, args.y2):
        print("warning: zero-length swipe (start == end); emitting identical frames", file=sys.stderr)
    pts = points(args.x1, args.y1, args.x2, args.y2, args.steps)
    if args.dry_run:
        print(f"swipe ({args.x1},{args.y1}) -> ({args.x2},{args.y2}) "
              f"steps={args.steps} step_delay={args.step_delay}s")
        print(f"first={pts[0]} mid={pts[len(pts) // 2]} last={pts[-1]}")
        print(f"# lift, settle {args.settle}s, then verify with scripts/rm-capture.py --out screen.png")
        return 0

    try:
        from evdev import UInput, ecodes as e
    except ImportError:
        print("error: python-evdev not installed (pip install evdev  # Toltec/opkg name: pyevdev)", file=sys.stderr)
        return 1

    caps = {e.EV_KEY: [e.BTN_TOUCH],
            e.EV_ABS: [(e.ABS_MT_SLOT, (0, 1, 0, 0)),
                       (e.ABS_MT_TRACKING_ID, (0, 65535, 0, 0)),
                       (e.ABS_MT_POSITION_X, (0, W - 1, 0, 0)),
                       (e.ABS_MT_POSITION_Y, (0, H - 1, 0, 0)),
                       (e.ABS_MT_PRESSURE, (0, 255, 0, 0))]}
    ui = None
    pressed = False

    def _lift_quiet():
        nonlocal ui, pressed
        if not pressed:
            return
        if ui is None:
            pressed = False
            return
        try:
            ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 0xFFFFFFFF)  # lift
            ui.write(e.EV_SYN, e.SYN_REPORT, 0)
        except (OSError, AttributeError, ValueError):
            pass
        pressed = False

    def _on_term(signum, frame):
        pthread_sigmask(SIG_BLOCK, {SIGINT, SIGTERM})
        _lift_quiet()
        sys.exit(143)

    signal(SIGTERM, _on_term)
    try:
        ui = UInput(caps, name="rm2-touch-inject")
    except OSError as exc:
        print(f"error: cannot create uinput device ({exc}); need /dev/uinput + root + python-evdev", file=sys.stderr)
        return 1
    interrupted = False
    try:
        try:
            ui.write(e.EV_ABS, e.ABS_MT_SLOT, 0)
            ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 43)
            for i, (x, y) in enumerate(pts):
                ui.write(e.EV_ABS, e.ABS_MT_POSITION_X, x)
                ui.write(e.EV_ABS, e.ABS_MT_POSITION_Y, y)
                ui.write(e.EV_ABS, e.ABS_MT_PRESSURE, 60)
                ui.write(e.EV_SYN, e.SYN_REPORT, 0)
                if i == 0:
                    pressed = True
                if i < len(pts) - 1:
                    try:
                        time.sleep(args.step_delay)
                    except OSError as exc:
                        print(f"error: step delay interrupted ({exc})", file=sys.stderr)
                        interrupted = True
                        break
            pressed = False
            # Lift pair (lift write + trailing SYN) is one transaction: block
            # SIGINT/SIGTERM across both so a signal cannot land between them
            # and leave an uncommitted lift. Restored in finally; pending
            # signals then hit the existing handlers, which correctly no-op.
            mask = pthread_sigmask(SIG_BLOCK, {SIGINT, SIGTERM})
            try:
                ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 0xFFFFFFFF)  # lift (-1 sentinel, unsigned)
                ui.write(e.EV_SYN, e.SYN_REPORT, 0)
            finally:
                pthread_sigmask(SIG_SETMASK, mask)
        except OSError as exc:
            # Best effort: release the contact so the tablet is not left with
            # a stuck finger (the device may already be dead - ignore errors).
            try:
                ui.write(e.EV_ABS, e.ABS_MT_TRACKING_ID, 0xFFFFFFFF)  # lift
                ui.write(e.EV_SYN, e.SYN_REPORT, 0)
            except OSError:
                pass
            pressed = False
            print(f"error: uinput write failed ({exc}); is /dev/uinput still available?", file=sys.stderr)
        except KeyboardInterrupt:
            pthread_sigmask(SIG_BLOCK, {SIGINT, SIGTERM})
            _lift_quiet()
            print("error: interrupted", file=sys.stderr)
            return 130
    finally:
        ui.close()
    if interrupted:
        return 1
    try:
        time.sleep(args.settle)  # e-ink settle before screenshot verify
    except KeyboardInterrupt:
        _lift_quiet()
        print("error: interrupted", file=sys.stderr)
        return 130
    return 0



if __name__ == "__main__":
    sys.exit(main())
