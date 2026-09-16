import json as _json
"""rm-tap.py — synthesize one finger tap on reMarkable 2 via uinput.

Runs ON the tablet (python-evdev installed). Type-B MT sequence:
SLOT -> TRACKING_ID -> POSITION_X/Y -> PRESSURE -> SYN_REPORT (down),
then TRACKING_ID -1 -> SYN_REPORT (up).
Matches on-device evtest captures (ABS+SYN only; BTN_TOUCH is advertised
in caps for compatibility but not emitted per frame).
Fixed tracking ID 42; do not run concurrent taps (shared virtual device).

Settle note: e-ink needs ~0.5-1.0 s after lift before a screenshot
verify; see references/03-input-automation.md §7.

Usage:
    rm-tap.py X Y [--dry-run] [--settle SECS]
    rm-tap.py --help
"""
import argparse
import math
import sys
import time
from signal import SIG_BLOCK, SIG_DFL, SIGINT, SIGPIPE, SIG_SETMASK, SIGTERM, pthread_sigmask, signal

W, H = 1404, 1872  # rM2 portrait pixels; Paper Pro: re-query, never reuse


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
        description="Synthesize one Type-B MT finger tap on reMarkable 2 via uinput."
    )
    p.add_argument("x", type=int, nargs="?", help="tap X in [0, 1404)")
    p.add_argument("y", type=int, nargs="?", help="tap Y in [0, 1872)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the event sequence without touching /dev/uinput (no device needed)")
    p.add_argument("--settle", type=float, default=0.8,
                   help="seconds to sleep after lift for e-ink settle, [0, 5] (default: 0.8)")
    return p.parse_args(argv)


def sequence(x, y, tracking_id=42, pressure=60):
    """Return the (code-tuple) event list for a tap; pure, testable, no device."""
    return [
        ("ABS_MT_SLOT", 0),
        ("ABS_MT_TRACKING_ID", tracking_id),
        ("ABS_MT_POSITION_X", x),
        ("ABS_MT_POSITION_Y", y),
        ("ABS_MT_PRESSURE", pressure),
        ("SYN_REPORT", 0),            # down
        ("ABS_MT_TRACKING_ID", -1),
        ("SYN_REPORT", 0),            # up
    ]


def main(argv=None):
    # Piped to a closed reader (e.g. --dry-run | head): die silently by
    # signal instead of a BrokenPipeError traceback.
    signal(SIGPIPE, SIG_DFL)
    args = parse_args(argv)
    if args.x is None or args.y is None:
        print("error: X and Y are required (see --help)", file=sys.stderr)
        return 2
    if not (0 <= args.x < W and 0 <= args.y < H):
        print(f"error: ({args.x}, {args.y}) outside 1404x1872", file=sys.stderr)
        return 2
    if not math.isfinite(args.settle) or not 0 <= args.settle <= 5:
        print(f"error: --settle must be a finite number in [0, 5], got {args.settle}", file=sys.stderr)
        return 2

    seq = sequence(args.x, args.y)
    if args.dry_run:
        for name, value in seq:
            print(f"EV_ABS/EV_SYN {name}={value}")
        print(f"# settle {args.settle}s, then verify with rm-screenshot.sh")
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
    abs_codes = {"ABS_MT_SLOT": e.ABS_MT_SLOT,
                 "ABS_MT_TRACKING_ID": e.ABS_MT_TRACKING_ID,
                 "ABS_MT_POSITION_X": e.ABS_MT_POSITION_X,
                 "ABS_MT_POSITION_Y": e.ABS_MT_POSITION_Y,
                 "ABS_MT_PRESSURE": e.ABS_MT_PRESSURE}
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
    try:
        try:
            syns = 0
            mask = None
            try:
                for name, value in seq:
                    if name == "SYN_REPORT":
                        ui.write(e.EV_SYN, e.SYN_REPORT, 0)
                        syns += 1
                        if syns == 1:
                            pressed = True
                        else:
                            pressed = False
                        if mask is not None:
                            # Paired SYN closing a masked lift: the commit is
                            # complete, so unblock and let pending signals deliver.
                            pthread_sigmask(SIG_SETMASK, mask)
                            mask = None
                    else:
                        v = 0xFFFFFFFF if value == -1 else value  # kernel -1 sentinel (unsigned)
                        if name == "ABS_MT_TRACKING_ID" and value == -1:
                            pressed = False
                            # Lift pair (this write + the trailing SYN) is one
                            # transaction: block SIGINT/SIGTERM across both so a
                            # signal cannot land between them and leave an
                            # uncommitted lift. Restored above on the happy path
                            # and in finally below; pending signals then hit the
                            # existing handlers, which correctly no-op.
                            mask = pthread_sigmask(SIG_BLOCK, {SIGINT, SIGTERM})
                        ui.write(e.EV_ABS, abs_codes[name], v)
            finally:
                if mask is not None:
                    pthread_sigmask(SIG_SETMASK, mask)
                    mask = None
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
            return 1
        except KeyboardInterrupt:
            pthread_sigmask(SIG_BLOCK, {SIGINT, SIGTERM})
            _lift_quiet()
            print("error: interrupted", file=sys.stderr)
            return 130
    finally:
        ui.close()
    try:
        time.sleep(args.settle)  # e-ink settle before screenshot verify
    except KeyboardInterrupt:
        _lift_quiet()
        print("error: interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
