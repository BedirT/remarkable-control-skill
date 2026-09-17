#!/usr/bin/env python3
"""rm-svg.py — SVG line art to reMarkable pen strokes.

Parses <path>/<polyline>/<polygon> from an SVG file, fits the drawing
into a canvas rectangle, and emits one FIFO `S` stroke line per
subpath (pen-down stroke). Curves (C/S/Q/T) are flattened to
polylines; implicit repeated coords are consumed; every M starts a
new stroke (pen lift between subpaths). A (arc) is skipped with a
stderr warning.

Usage:
    python3 scripts/rm-svg.py drawing.svg [--box X Y W H] [--press A[:B]]
    [--skip-class NAME] [--skip-fill COLOR]
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
    toks = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", d)
    subs, cur, start, i = [], [], None, 0
    x = y = 0.0

    def lineto(px, py):
        nonlocal x, y
        x, y = px, py
        cur.append((x, y))

    CMD = "MmLlHhVvCcSsQqTtAaZz"
    prev_c2 = None  # 2nd control point of previous C/S (abs) for S reflection
    prev_q = None  # control point of previous Q/T (abs) for T reflection
    while i < len(toks):
        t = toks[i]
        i += 1
        if t in "Mm":
            if cur:
                subs.append(cur)
                cur = []
            dx, dy = float(toks[i]), float(toks[i + 1])
            i += 2
            if t == "m":
                dx, dy = x + dx, y + dy
            x, y = dx, dy
            start = (x, y)
            cur.append(start)
            prev_c2 = prev_q = None
            while i + 1 < len(toks) and toks[i] not in CMD:
                dx, dy = float(toks[i]), float(toks[i + 1])
                i += 2
                if t == "m":
                    dx, dy = x + dx, y + dy
                lineto(dx, dy)
        elif t in "Ll":
            while i + 1 < len(toks) and toks[i] not in CMD:
                dx, dy = float(toks[i]), float(toks[i + 1])
                i += 2
                if t == "l":
                    dx, dy = x + dx, y + dy
                lineto(dx, dy)
            prev_c2 = prev_q = None
        elif t in "Hh":
            while i < len(toks) and toks[i] not in CMD:
                dx = float(toks[i])
                i += 1
                lineto(x + dx if t == "h" else dx, y)
            prev_c2 = prev_q = None
        elif t in "Vv":
            while i < len(toks) and toks[i] not in CMD:
                dy = float(toks[i])
                i += 1
                lineto(x, y + dy if t == "v" else dy)
            prev_c2 = prev_q = None
        elif t in "Cc":
            while i + 5 < len(toks) and toks[i] not in CMD:
                g = [float(toks[i + k]) for k in range(6)]
                i += 6
                if t == "c":
                    p1 = (x + g[0], y + g[1])
                    p2 = (x + g[2], y + g[3])
                    p3 = (x + g[4], y + g[5])
                else:
                    p1, p2, p3 = (g[0], g[1]), (g[2], g[3]), (g[4], g[5])
                for pt in cubic((x, y), p1, p2, p3):
                    lineto(*pt)
                prev_c2, prev_q = p2, None
        elif t in "Ss":
            while i + 3 < len(toks) and toks[i] not in CMD:
                g = [float(toks[i + k]) for k in range(4)]
                i += 4
                p1 = (2 * x - prev_c2[0], 2 * y - prev_c2[1]) if prev_c2 else (x, y)
                if t == "s":
                    p2 = (x + g[0], y + g[1])
                    p3 = (x + g[2], y + g[3])
                else:
                    p2, p3 = (g[0], g[1]), (g[2], g[3])
                for pt in cubic((x, y), p1, p2, p3):
                    lineto(*pt)
                prev_c2, prev_q = p2, None
        elif t in "Qq":
            while i + 3 < len(toks) and toks[i] not in CMD:
                g = [float(toks[i + k]) for k in range(4)]
                i += 4
                if t == "q":
                    q = (x + g[0], y + g[1])
                    r = (x + g[2], y + g[3])
                else:
                    q, r = (g[0], g[1]), (g[2], g[3])
                p1 = (x + 2 * (q[0] - x) / 3, y + 2 * (q[1] - y) / 3)
                p2 = (r[0] + 2 * (q[0] - r[0]) / 3, r[1] + 2 * (q[1] - r[1]) / 3)
                for pt in cubic((x, y), p1, p2, r):
                    lineto(*pt)
                prev_q, prev_c2 = q, None
        elif t in "Tt":
            while i + 1 < len(toks) and toks[i] not in CMD:
                dx, dy = float(toks[i]), float(toks[i + 1])
                i += 2
                r = (x + dx, y + dy) if t == "t" else (dx, dy)
                q = (2 * x - prev_q[0], 2 * y - prev_q[1]) if prev_q else (x, y)
                p1 = (x + 2 * (q[0] - x) / 3, y + 2 * (q[1] - y) / 3)
                p2 = (r[0] + 2 * (q[0] - r[0]) / 3, r[1] + 2 * (q[1] - r[1]) / 3)
                for pt in cubic((x, y), p1, p2, r):
                    lineto(*pt)
                prev_q, prev_c2 = q, None
        elif t in "Aa":
            n = 0
            while i + 6 < len(toks) and toks[i] not in CMD:
                i += 7
                n += 1
            if n:
                print(f"warning: {n} arc segment(s) skipped (A unsupported)",
                      file=sys.stderr)
            prev_c2 = prev_q = None
        elif t in "Zz":
            if start is not None:
                lineto(*start)
            if cur:
                subs.append(cur)
                cur = []
                start = None
            prev_c2 = prev_q = None
    if cur:
        subs.append(cur)
    return [s for s in subs if len(s) > 1]

def stroke_cmds(sub, proj, press0, press1, flip_y=False):
    """One FIFO `S` line per subpath (single pen-down pass).

    Pressure ramps press0->press1 along the whole subpath.
    Coords are correct screen pixels. flip_y compensates a legacy
    pend build whose map is y-inverted (deviation, not the rule).
    """
    out = []
    for path in sub:
        pts = [proj(x, y) for x, y in path]
        if flip_y:
            pts = [(x, SCREEN_H - 1 - y) for x, y in pts]
        # Split very long subpaths so no FIFO line nears the 4KB read
        # (200 pts ~= 2KB). Chunk joints share the endpoint; each is
        # its own pen-down, so fewer chunks = fewer touchdown seams.
        for k in range(0, len(pts), 200):
            chunk = pts[k:k + 201]
            if len(chunk) < 2:
                continue
            total = sum(
                math.hypot(b[0] - a[0], b[1] - a[1])
                for a, b in zip(chunk, chunk[1:])
            )
            steps = max(2, min(2000, int(total / 25) + 1))
            coords = " ".join(f"{int(x)} {int(y)}" for x, y in chunk)
            out.append(f"S {steps} 12 {press0} {press1} {coords}")
    return out




def class_fills(root):
    """Map CSS class -> fill value from <style> blocks (flat regex)."""
    fills = {}
    for el in root.iter():
        if el.tag.split("}")[-1] == "style" and el.text:
            for m in re.finditer(r"\.([\w-]+)\s*\{[^}]*?fill\s*:\s*([^;}]+)",
                                 el.text):
                fills[m.group(1)] = m.group(2).strip().lower()
    return fills


def shape_fill(el, class_fills):
    """Resolved fill for a shape: direct attr, else class lookup."""
    f = el.get("fill")
    if f:
        return f.strip().lower()
    for c in el.get("class", "").split():
        if c in class_fills:
            return class_fills[c]
    return ""


def shapes(root, skip=()):
    """Yield point-subpaths from path/polyline/polygon elements.

    Shapes whose class or resolved fill is in `skip` are dropped
    (background silhouettes tangle line art with outlines that do
    not exist in the drawing). Normalizes #fff-style values.
    """
    fills = class_fills(root)
    skip = {s.strip().lower().lstrip("#") for s in skip}

    def norm(v):
        v = v.strip().lower().lstrip("#")
        return {"ffffff": "fff", "white": "fff"}.get(v, v)

    skip = {norm(s) for s in skip}
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("path", "polyline", "polygon"):
            continue
        if el.get("class", "").strip().lower() in skip:
            continue
        if norm(shape_fill(el, fills)) in skip:
            continue
        if tag == "path" and el.get("d"):
            yield from parse_path(el.get("d"))
        elif tag in ("polyline", "polygon"):
            pts = re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?",
                             el.get("points", ""))
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
    box = [150, 200, SCREEN_W - 300, SCREEN_H - 400]
    press0, press1, run, flip_y = 1500, 1500, False, False
    skip = []
    i = 1
    while i < len(argv):
        if argv[i] == "--box":
            box = [int(v) for v in argv[i + 1:i + 5]]
            i += 5
        elif argv[i] == "--press":
            pair = argv[i + 1].split(":")
            press0 = int(pair[0])
            press1 = int(pair[1]) if len(pair) > 1 else press0
            i += 2
        elif argv[i] == "--run":
            run = True
            i += 1
        elif argv[i] == "--flip-y":
            flip_y = True
        elif argv[i] in ("--skip-class", "--skip-fill"):
            skip.append(argv[i + 1])
            i += 2
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
    subs = list(shapes(root, skip))
    if not subs:
        print("no drawable paths found", file=sys.stderr)
        return 1
    cmds = stroke_cmds(subs, proj, press0, press1, flip_y)
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
