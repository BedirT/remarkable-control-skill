#!/usr/bin/env python3
"""rm-svg.py — SVG line art to reMarkable pen strokes.

Parses <path>/<polyline>/<polygon> from an SVG file, fits the drawing
into a canvas rectangle, and emits one FIFO `S` stroke line per
subpath (pen-down stroke). Curves (C/S/Q/T/A) are flattened to
polylines; every M starts a new stroke (pen lift between subpaths).

Usage:
    python3 scripts/rm-svg.py drawing.svg [--box X Y W H] [--press N]
    python3 scripts/rm-svg.py drawing.svg --run [--box ...] [--press ...]

--run feeds each stroke to the `pend` daemon's /tmp/pen.fifo over the
existing USB SSH session (otherwise lines print to stdout). Needs the
pend session live (03 §5b), the notebook page open with a pen tool
selected; strokes land in SCREEN coords (1404x1872 portrait).
--flip-y compensates a legacy inverted pend build (deviation, not the
rule — current builds take plain screen coords).

SVG y grows downward, same as the screen: no axis flip needed.
"""
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

SCREEN_W, SCREEN_H = 1404, 1872
SSH = ["./scripts/rm-ssh.sh", "--"]


def fit(viewbox, box):
    """Scale+offset mapping viewBox (x,y,w,h) into box, aspect kept."""
    vx, vy, vw, vh = viewbox
    bx, by, bw, bh = box
    s = min(bw / vw, bh / vh)
    ox = bx + (bw - vw * s) / 2 - vx * s
    oy = by + (bh - vh * s) / 2 - vy * s
    return lambda x, y: (x * s + ox, y * s + oy)


def cubic(p0, p1, p2, p3, tol=0.75):
    """Flatten one cubic bezier to points (recursive subdivision)."""
    mx = (p0[0] + 3 * p1[0] + 3 * p2[0] + p3[0]) / 8
    my = (p0[1] + 3 * p1[1] + 3 * p2[1] + p3[1]) / 8
    dx = (p0[0] + p3[0]) / 2
    dy = (p0[1] + p3[1]) / 2
    if math.hypot(mx - dx, my - dy) < tol:
        return [p3]
    l1 = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    m = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    r2 = ((p2[0] + p3[0]) / 2, (p2[1] + p3[1]) / 2)
    l2 = ((l1[0] + m[0]) / 2, (l1[1] + m[1]) / 2)
    r1 = ((m[0] + r2[0]) / 2, (m[1] + r2[1]) / 2)
    mid = ((l2[0] + r1[0]) / 2, (l2[1] + r1[1]) / 2)
    return cubic(p0, l1, l2, mid, tol) + cubic(mid, r1, r2, p3, tol)


def parse_path(d):
    """Split path data into subpaths of absolute (x, y) points."""
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    subs, cur, start, i = [], [], None, 0
    x = y = 0.0

    def lineto(px, py):
        nonlocal x, y
        x, y = px, py
        cur.append((x, y))

    while i < len(toks):
        t = toks[i]
        i += 1
        if t == "M":
            if cur:
                subs.append(cur)
                cur = []
            x, y = float(toks[i]), float(toks[i + 1])
            i += 2
            start = (x, y)
            cur.append(start)
            while i + 1 < len(toks) and toks[i] not in "MmLlHhVvCcSsQqTtAaZz":
                lineto(float(toks[i]), float(toks[i + 1]))
                i += 2
        elif t == "m":
            if cur:
                subs.append(cur)
                cur = []
            x, y = x + float(toks[i]), y + float(toks[i + 1])
            i += 2
            start = (x, y)
            cur.append(start)
            while i + 1 < len(toks) and toks[i] not in "MmLlHhVvCcSsQqTtAaZz":
                lineto(x + float(toks[i]), y + float(toks[i + 1]))
                i += 2
        elif t in "L":
            lineto(float(toks[i]), float(toks[i + 1]))
            i += 2
        elif t == "l":
            lineto(x + float(toks[i]), y + float(toks[i + 1]))
            i += 2
        elif t == "H":
            lineto(float(toks[i]), y)
            i += 1
        elif t == "h":
            lineto(x + float(toks[i]), y)
            i += 1
        elif t == "V":
            lineto(x, float(toks[i]))
            i += 1
        elif t == "v":
            lineto(x, y + float(toks[i]))
            i += 1
        elif t in "Cc":
            rel = t == "C"
            nums = []
            while i < len(toks) and toks[i] not in "MmLlHhVvCcSsQqTtAaZz":
                nums.append(float(toks[i]))
                i += 1
            for k in range(0, len(nums) - 5, 6):
                g = nums[k:k + 6]
                if rel:
                    p1 = (x + g[0], y + g[1])
                    p2 = (x + g[2], y + g[3])
                    p3 = (x + g[4], y + g[5])
                else:
                    p1, p2, p3 = (g[0], g[1]), (g[2], g[3]), (g[4], g[5])
                for pt in cubic((x, y), p1, p2, p3):
                    lineto(*pt)
        elif t in "Qq":
            rel = t == "Q"
            # Degree-elevate quadratic to cubic, then flatten.
            nums = []
            while i < len(toks) and toks[i] not in "MmLlHhVvCcSsQqTtAaZz":
                nums.append(float(toks[i]))
                i += 1
            for k in range(0, len(nums) - 3, 4):
                g = nums[k:k + 4]
                q = (x + g[0], y + g[1]) if rel else (g[0], g[1])
                r = (x + g[2], y + g[3]) if rel else (g[2], g[3])
                p1 = (x + 2 * (q[0] - x) / 3, y + 2 * (q[1] - y) / 3)
                p2 = (r[0] + 2 * (q[0] - r[0]) / 3, r[1] + 2 * (q[1] - r[1]) / 3)
                for pt in cubic((x, y), p1, p2, r):
                    lineto(*pt)
        elif t in "Zz":
            if start is not None:
                lineto(*start)
            if cur:
                subs.append(cur)
                cur = []
                start = None
    if cur:
        subs.append(cur)
    return [s for s in subs if len(s) > 1]
def stroke_cmds(sub, proj, press, flip_y=False):
    """One FIFO `S` line per subpath (single pen-down pass).

    Coords are correct screen pixels. flip_y compensates a legacy
    pend build whose map is y-inverted (deviation, not the rule).
    """
    out = []
    for path in sub:
        pts = [proj(x, y) for x, y in path]
        if flip_y:
            pts = [(x, SCREEN_H - 1 - y) for x, y in pts]
        # Split very long subpaths so no call exceeds ~60 points.
        for k in range(0, len(pts), 60):
            chunk = pts[k:k + 61]
            if len(chunk) < 2:
                continue
            total = sum(
                math.hypot(b[0] - a[0], b[1] - a[1])
                for a, b in zip(chunk, chunk[1:])
            )
            steps = max(2, min(2000, int(total / 25) + 1))
            coords = " ".join(f"{int(x)} {int(y)}" for x, y in chunk)
            out.append(f"S {steps} 12 {press} {coords}")
    return out




def shapes(root):
    """Yield point-subpaths from path/polyline/polygon elements."""
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "path" and el.get("d"):
            yield from parse_path(el.get("d"))
        elif tag in ("polyline", "polygon"):
            pts = re.findall(r"-?\d*\.?\d+", el.get("points", ""))
            nums = [float(p) for p in pts]
            sub = list(zip(nums[::2], nums[1::2]))
            if tag == "polygon" and sub:
                sub.append(sub[0])
            if len(sub) > 1:
                yield sub


def main(argv):
    if not argv or "-h" in argv or "--help" in argv:
        print(__doc__.strip().splitlines()[0])
        print("See script header for usage.")
        return 2
    path = argv[0]
    box = [100, 200, SCREEN_W - 200, SCREEN_H - 400]
    press, run, flip_y = 1500, False, False
    i = 1
    while i < len(argv):
        if argv[i] == "--box":
            box = [int(v) for v in argv[i + 1:i + 5]]
            i += 5
        elif argv[i] == "--press":
            press = int(argv[i + 1])
            i += 2
        elif argv[i] == "--run":
            run = True
            i += 1
        elif argv[i] == "--flip-y":
            flip_y = True
            i += 1
        else:
            i += 1
    root = ET.parse(path).getroot()
    vb = root.get("viewBox")
    if vb:
        viewbox = tuple(float(v) for v in vb.split())
    else:
        w = float(root.get("width", SCREEN_W).rstrip("px"))
        h = float(root.get("height", SCREEN_H).rstrip("px"))
        viewbox = (0.0, 0.0, w, h)
    proj = fit(viewbox, box)
    subs = list(shapes(root))
    if not subs:
        print("no drawable paths found", file=sys.stderr)
        return 1
    cmds = stroke_cmds(subs, proj, press, flip_y)
    print(f"{len(subs)} subpaths -> {len(cmds)} strokes", file=sys.stderr)
    if run:
        import time
        for c in cmds:
            # One line per writer-open; the daemon draws it on the
            # node xochitl holds. Sleep past the stroke duration.
            r = subprocess.run(SSH + [f"echo {c!r} > /tmp/pen.fifo; sleep 1"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(r.stderr.strip(), file=sys.stderr)
                return 1
            time.sleep(2)
    else:
        for c in cmds:
            print(c)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
