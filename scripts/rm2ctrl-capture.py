#!/usr/bin/env python3
"""rm2ctrl-capture.py -- headless screen capture from reMarkable 2 over USB SSH.

Read-only. No taps, refresh, uploads, ptrace, signals, or tablet changes.
Fixed addresses are gated on the proven firmware build (/etc/version plus
xochitl/QtGui binary hashes); anything else aborts. Outputs are staged to
temp files and published only after the post-transfer recheck passes.
Method (proven 2026-09-16): xochitl's EPFramebufferCarta1000 singleton
(static 0x1517084) owns an inherited 1404x1872 RGB32 QImage; the pixel
allocation sits in an ordinary readable mapping and is transferred with
one page-aligned raw dd over the existing SSH stdout.

Usage: scripts/rm2ctrl-capture.py [--out screen.png] [--raw frame.raw] [--force]
       [--host HOST] [--key PATH] [--timeout SECS]
       scripts/rm2ctrl-capture.py --dry-run | --help
Env: RM_HOST, RM_KEY, RM_CONNECT_TIMEOUT (flags override env; honored by
scripts/rm2ctrl-ssh.sh).
Must run from the skill root (uses ./scripts/rm2ctrl-ssh.sh).
"""
import os
import struct
import subprocess
import sys
import time
import tempfile
import zlib

W, H, FMT, BPL = 1404, 1872, 4, 5616
FRAME_N = W * H * 4
STATIC = 0x1517084
CARTA_VPTR = 0x120f738
PAIR_OFF, PAIR_LEN = 88, 28
IMGA_OFF = 88
D_OFF, HDR_LEN = 8, 0x38
W_OFF, H_OFF, PIX_OFF, FMT_OFF, BPL_OFF = 4, 8, 0x2C, 0x30, 0x34
EXE_BASE = 0x10000
SUPPORTED_FW = "20260827113527"
SUPPORTED_XOCHITL_SIZE = 22046100
SUPPORTED_XOCHITL_SHA256 = ("071d85beef3ef2d4cc0e11002140b27b"
                            "82a2cc04a2ed740a5669f591069b77df")
QTGUI_PATH = "/usr/lib/libQt6Gui.so.6"
SUPPORTED_QTGUI_SHA256 = ("93fe582cc61673342ca49e12306d7f689"
                          "860016582fa46ce135ffa280a972839")
BS = 4096
BYTE_CAP = 12 * 1024 * 1024
DEADLINE = 60.0

SSH = [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "rm2ctrl-ssh.sh")]
_first_probe = True


class Fail(Exception):
    pass


class Cap:
    def __init__(self):
        self.bytes = 0
        self.ops = 0
        self.t0 = time.time()

    def charge(self, n):
        self.ops += 1
        self.bytes += n
        if self.bytes > BYTE_CAP:
            raise Fail("12 MiB process-memory cap exceeded")
        if time.time() - self.t0 > DEADLINE:
            raise Fail("60 s deadline exceeded")

    def remaining(self):
        rem = DEADLINE - (time.time() - self.t0)
        if rem <= 1:
            raise Fail("60 s deadline exceeded")
        return rem


def u32(b, off=0):
    return struct.unpack_from("<I", b, off)[0]


def ssh_text(argv, cap, timeout=None):
    cap.charge(0)
    r = subprocess.run(argv, capture_output=True, text=True,
                       timeout=timeout or cap.remaining())
    if r.returncode != 0:
        raise Fail("ssh failed rc=%d: %s" % (r.returncode,
                                             r.stderr[-200:]))
    return r.stdout


def snapshot(cap):
    out = ssh_text(SSH + ["--",
                          "P=$(/bin/pidof xochitl); echo \"PID=$P\";"
                          " echo \"STAT:\"; cat /proc/$P/stat;"
                          " echo \"---FW---\"; cat /etc/version;"
                          " stat -c %s /usr/bin/xochitl 2>/dev/null"
                          " || wc -c < /usr/bin/xochitl;"
                          " echo \"---MAPS---\"; cat /proc/$P/maps;"
                          " echo \"---TOOLS---\";"
                          " command -v dd od hexdump;"
                          " echo \"---SUMS---\";"
                          " sha256sum /usr/bin/xochitl " + QTGUI_PATH], cap)
    pid = int(out.split("\n", 1)[0].split("PID=")[1])
    pre, _, post = out.split("\n", 1)[1].partition("---MAPS---")
    statpart, _, fwpart = pre.partition("---FW---")
    statline = statpart.split("STAT:\n", 1)[1].strip().splitlines()[0]
    head, _, tail = statline.rpartition(") ")
    ident = (int(head.split("(")[0]), int(tail.split()[19]))
    if ident[0] != pid:
        raise Fail("pidof/stat pid mismatch: %d vs %d" % (pid, ident[0]))
    fwlines = fwpart.strip().splitlines()
    fw = fwlines[0].strip() if fwlines else ""
    try:
        xosize = int(fwlines[1].strip().split()[0])
    except (IndexError, ValueError):
        raise Fail("unreadable xochitl size probe")
    if fw != SUPPORTED_FW or xosize != SUPPORTED_XOCHITL_SIZE:
        raise Fail("unsupported build: fw=%s xochitl=%dB (want %s/%dB)"
                   % (fw, xosize, SUPPORTED_FW, SUPPORTED_XOCHITL_SIZE))
    maps_txt, _, tools_txt = post.partition("---TOOLS---")
    tools_txt, _, sums_txt = tools_txt.partition("---SUMS---")
    sums = {}
    for ln in sums_txt.splitlines():
        p = ln.split()
        if len(p) >= 2 and len(p[0]) == 64:
            sums[p[1].rsplit("/", 1)[-1]] = p[0].lower()
    if (sums.get("xochitl") != SUPPORTED_XOCHITL_SHA256
            or sums.get("libQt6Gui.so.6") != SUPPORTED_QTGUI_SHA256):
        raise Fail("unsupported build: binary hash mismatch "
                   "(xochitl/QtGui differ from proven layout sources)")
    found = set(ln.strip().rsplit("/", 1)[-1] for ln in tools_txt.split())
    if "hexdump" not in found:
        raise Fail("target tool missing: need hexdump"
                   " (BusyBox od cannot emit plain hex)")
    tool = "hexdump"
    exeline = "NOT FOUND"
    regions = []
    for line in maps_txt.splitlines():
        p = line.split()
        if len(p) < 5:
            continue
        s, e = (int(x, 16) for x in p[0].split("-"))
        regions.append((s, e))
        if (exeline == "NOT FOUND" and len(p) >= 6 and "/" in p[5]
                and p[5].rsplit("/", 1)[1] == "xochitl"
                and p[2] == "00000000" and p[1].startswith("r-x")):
            exeline = line.strip()
    if exeline == "NOT FOUND":
        raise Fail("missing executable mapping: /usr/bin/xochitl")
    if int(exeline.split()[0].split("-")[0], 16) != EXE_BASE:
        raise Fail("xochitl load bias changed")
    return ident, maps_txt, tool, regions, exeline


def covered(regions, addr, size):
    end = addr + size
    return size > 0 and end <= 0x100000000 and any(
        s <= addr and end <= e for (s, e) in regions)


def _block_pipe(pid, skip_words, count):
    return ("set -o pipefail 2>/dev/null;"
            " dd if=/proc/%d/mem bs=4 skip=%d count=%d"
            " | hexdump -v -e '1/1 \"%%02x\"'" % (pid, skip_words, count))


def read_block(cap, pid, regions, tool, addr, size):
    global _first_probe
    if addr % 4 or size % 4 or size <= 0:
        raise Fail("unaligned block request")
    if not covered(regions, addr, size):
        raise Fail("block 0x%x+0x%x outside mappings" % (addr, size))
    cap.charge(size)
    cap.charge(0)
    n = size // 4
    r = subprocess.run(SSH + ["--", _block_pipe(pid, addr // 4, n)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, timeout=cap.remaining())
    err = r.stderr[-200:]
    if r.returncode != 0:
        raise Fail("block read at 0x%x rc=%d: %s" % (addr, r.returncode, err))
    out = r.stdout
    if _first_probe:
        _first_probe = False
        print("transport tool=%s head=%r" % (tool, out[:120]))
    blob = "".join(out.split())[:n * 8]
    if len(blob) != n * 8:
        raise Fail("short block read at 0x%x: got %d of %d hex chars; %s"
                   % (addr, len(blob), n * 8, err))
    return bytes.fromhex(blob)


def maps_line_for(maps_txt, addr):
    for line in maps_txt.splitlines():
        p = line.split()
        if len(p) < 5:
            continue
        s, e = (int(x, 16) for x in p[0].split("-"))
        if s <= addr < e:
            return line.strip()
    return "NOT FOUND"


def raw_read(cap, pid, start, blocks):
    want = blocks * BS
    cap.charge(want)
    cmd = ("dd if=/proc/%d/mem bs=%d skip=%d count=%d"
           % (pid, BS, start // BS, blocks))
    r = subprocess.run(SSH + ["--", cmd], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=cap.remaining())
    err = r.stderr.decode("ascii", "replace")[-200:]
    if r.returncode != 0:
        raise Fail("raw read rc=%d: %s" % (r.returncode, err))
    if len(r.stdout) != want:
        raise Fail("short raw read: got %d of %d bytes; %s"
                   % (len(r.stdout), want, err))
    return r.stdout


def write_png(path, w, h, stride, raw):
    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    out = bytearray(b"\x89PNG\r\n\x1a\n")
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    enc = bytearray()
    for y in range(h):
        row = raw[y * stride:y * stride + w * 4]
        px = bytearray(w * 4)
        px[0::4] = row[2::4]
        px[1::4] = row[1::4]
        px[2::4] = row[0::4]
        px[3::4] = b"\xff" * w
        enc.append(0)
        enc += px
    out += chunk(b"IDAT", zlib.compress(bytes(enc)))
    out += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(out)


def recheck(cap, ident, helper, pair, dA, hdr, exeline):
    ident2, maps2, tool2, regions2, exeline2 = snapshot(cap)
    if ident2 != ident:
        raise Fail("process identity changed during run")
    pid = ident[0]
    if exeline2 != exeline:
        raise Fail("executable mapping moved during run")
    if u32(read_block(cap, pid, regions2, tool2, STATIC, 4)) != helper:
        raise Fail("changed during run: static pointer")
    if u32(read_block(cap, pid, regions2, tool2, helper, 4)) != CARTA_VPTR:
        raise Fail("changed during run: object type")
    if read_block(cap, pid, regions2, tool2, helper + PAIR_OFF,
                   PAIR_LEN) != pair:
        raise Fail("changed during run: image pair")
    if read_block(cap, pid, regions2, tool2, dA, HDR_LEN) != hdr:
        raise Fail("changed during run: image A metadata")
    print("recheck unchanged (not atomic)")

def stage(final):
    d = os.path.dirname(os.path.abspath(final))
    try:
        fd, tmp = tempfile.mkstemp(prefix=".rm-cap-", dir=d)
    except OSError as ex:
        raise Fail("cannot stage %s: %s" % (final, ex))
    os.close(fd)
    return tmp


def publish(tmp, final, force):
    if force:
        os.replace(tmp, final)
        return
    try:
        os.link(tmp, final)
    except FileExistsError:
        raise Fail("%s exists (use --force)" % final)
    os.unlink(tmp)

def capture(out_png, out_raw, force):
    cap = Cap()
    ident, maps_txt, tool, regions, exeline = snapshot(cap)
    pid = ident[0]
    print("pid=%d starttime=%d" % ident)
    print("t+%.1fs snapshot+hash gate" % (time.time() - cap.t0))
    helper = u32(read_block(cap, pid, regions, tool, STATIC, 4))
    if helper == 0:
        raise Fail("null helper pointer in static storage")
    vptr = u32(read_block(cap, pid, regions, tool, helper, 4))
    if vptr != CARTA_VPTR:
        raise Fail("object type mismatch: got 0x%x want 0x%x"
                   % (vptr, CARTA_VPTR))
    print("helper=0x%x type OK (Carta1000)" % helper)
    pair = read_block(cap, pid, regions, tool, helper + PAIR_OFF, PAIR_LEN)
    dA = u32(pair, IMGA_OFF - PAIR_OFF + D_OFF)
    if dA == 0:
        raise Fail("image A null data")
    hdr = read_block(cap, pid, regions, tool, dA, HDR_LEN)
    wdt, hgt = u32(hdr, W_OFF), u32(hdr, H_OFF)
    pix, fmt, bpl = u32(hdr, PIX_OFF), u32(hdr, FMT_OFF), u32(hdr, BPL_OFF)
    print("image A: %dx%d fmt=%d bpl=%d pix=0x%x" % (wdt, hgt, fmt, bpl,
                                                    pix))
    if (wdt, hgt, fmt, bpl) != (W, H, FMT, BPL):
        raise Fail("image A not 1404x1872 fmt4 bpl5616")
    line = maps_line_for(maps_txt, pix)
    if (line == "NOT FOUND" or not line.split()[1].startswith("r")
            or "/dev/fb0" in line
            or maps_line_for(maps_txt, pix + FRAME_N - 1) != line):
        raise Fail("pixel extent not in one ordinary readable mapping: "
                   "%s" % line)
    print("extent %d bytes in: %s" % (FRAME_N, line))
    recheck(cap, ident, helper, pair, dA, hdr, exeline)
    read_block(cap, pid, regions, tool, pix, 64)
    print("probe 64 bytes OK")
    print("t+%.1fs metadata+recheck+probe" % (time.time() - cap.t0))
    start = pix - pix % BS
    prefix = pix - start
    blocks = (prefix + FRAME_N + BS - 1) // BS
    if maps_line_for(maps_txt, start + blocks * BS - 1) != line:
        raise Fail("rounded interval leaves the mapping")
    blob = raw_read(cap, pid, start, blocks)
    print("t+%.1fs bulk transfer" % (time.time() - cap.t0))
    frame = blob[prefix:prefix + FRAME_N]
    tmp_png, tmp_raw = stage(out_png), stage(out_raw)
    try:
        with open(tmp_raw, "wb") as f:
            f.write(frame)
        write_png(tmp_png, W, H, BPL, frame)
        print("t+%.1fs png encode" % (time.time() - cap.t0))
        recheck(cap, ident, helper, pair, dA, hdr, exeline)
        publish(tmp_raw, out_raw, force)
        publish(tmp_png, out_png, force)
    except BaseException:
        for t in (tmp_png, tmp_raw):
            try:
                os.unlink(t)
            except OSError:
                pass
        raise
    print("saved %s + %s (%d bytes, %d ops, %.1fs)" % (
        out_png, out_raw, len(frame), cap.ops, time.time() - cap.t0))


def main(argv):
    out_png, out_raw, force = "screen.png", None, False
    host, key, timeout = None, None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--help":
            print(__doc__)
            return 0
        if a == "--dry-run":
            print("would: snapshot xochitl, read static 0x%x, verify "
                  "Carta1000 vptr, read image pair+header, probe 64B, "
                  "transfer %d bytes raw, write PNG" % (STATIC, FRAME_N))
            return 0
        if a == "--force":
            force = True
        elif a == "--out" and i + 1 < len(argv):
            i += 1
            out_png = argv[i]
        elif a == "--raw" and i + 1 < len(argv):
            i += 1
            out_raw = argv[i]
        elif a in ("--host", "--key", "--timeout") and i + 1 < len(argv):
            i += 1
            if a == "--host":
                host = argv[i]
            elif a == "--key":
                key = argv[i]
            else:
                timeout = argv[i]
        else:
            print("error: bad argument %r (see --help)" % a,
                  file=sys.stderr)
            return 2
        i += 1
    if host is not None:
        if host.startswith("-") or any(ord(c) < 32 for c in host):
            print("error: bad --host", file=sys.stderr)
            return 2
        os.environ["RM_HOST"] = host
    if key is not None:
        if (key.startswith("-") or any(ord(c) < 32 for c in key)
                or not os.path.isfile(key)):
            print("error: bad --key (must be a readable file)",
                  file=sys.stderr)
            return 2
        os.environ["RM_KEY"] = key
    if timeout is not None:
        if not timeout.isdigit() or not 1 <= int(timeout) <= 30:
            print("error: bad --timeout (integer 1..30)", file=sys.stderr)
            return 2
        os.environ["RM_CONNECT_TIMEOUT"] = timeout
    if out_raw is None:
        out_raw = os.path.splitext(out_png)[0] + ".raw"
    for p in (out_png, out_raw):
        if p.startswith("-") or any(ord(c) < 32 for c in p):
            print("error: bad output path", file=sys.stderr)
            return 2
        if os.path.islink(p):
            print("error: refusing symlink output: %s" % p, file=sys.stderr)
            return 2
        if os.path.exists(p) and not os.path.isfile(p):
            print("error: not a regular file: %s" % p, file=sys.stderr)
            return 2
        if os.path.exists(p) and not force:
            print("error: %s exists (use --force)" % p, file=sys.stderr)
            return 1
    r_png, r_raw = (os.path.realpath(p) for p in (out_png, out_raw))
    if r_png == r_raw:
        print("error: --out and --raw are the same file", file=sys.stderr)
        return 2
    keyp = os.environ.get("RM_KEY")
    if keyp is None:
        cand = os.path.join(os.environ.get("HOME", ""), ".ssh",
                            "id_rsa_remarkable")
        keyp = cand if os.path.isfile(cand) else None
    if keyp is not None:
        r_key = os.path.realpath(keyp)
        if r_png == r_key or r_raw == r_key:
            print("error: output aliases the SSH identity file",
                  file=sys.stderr)
            return 2
    try:
        capture(out_png, out_raw, force)
    except Fail as ex:
        print("ABORT: %s" % ex, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
