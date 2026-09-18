"""Host-only smoke tests for scripts/rm2ctrl-capture.py (no tablet needed)."""
import importlib.util
import os
import struct
import subprocess
import zlib
import pytest

CAP = importlib.util.spec_from_file_location(
    "rm2ctrl_capture", "scripts/rm2ctrl-capture.py")
rm2ctrl_capture = importlib.util.module_from_spec(CAP)
CAP.loader.exec_module(rm2ctrl_capture)


def parse_png(blob):
    assert blob[:8] == b"\x89PNG\r\n\x1a\n", "missing PNG signature"
    pos, chunks = 8, {}
    while pos < len(blob):
        (ln,) = struct.unpack(">I", blob[pos:pos + 4])
        typ = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + ln]
        (crc,) = struct.unpack(">I", blob[pos + 8 + ln:pos + 12 + ln])
        assert zlib.crc32(typ + data) & 0xFFFFFFFF == crc, \
            "bad CRC in %r" % typ
        chunks.setdefault(typ, []).append(data)
        pos += 12 + ln
        if typ == b"IEND":
            break
    return chunks, pos


def test_write_png_is_a_complete_valid_png(tmp_path):
    out = tmp_path / "t.png"
    w, h, stride = 3, 2, 12
    raw = bytes(range(h * stride))
    rm2ctrl_capture.write_png(str(out), w, h, stride, raw)
    blob = out.read_bytes()
    chunks, end = parse_png(blob)
    assert end == len(blob), "trailing bytes after IEND"
    assert struct.unpack(">IIBBBBB", chunks[b"IHDR"][0])[:2] == (w, h)
    pixels = zlib.decompress(b"".join(chunks[b"IDAT"]))
    assert len(pixels) == h * (1 + w * 4), "IDAT scanline size wrong"
    assert b"IEND" in chunks, "missing IEND terminator"


def test_write_png_channel_order_bgr_to_rgb(tmp_path):
    out = tmp_path / "c.png"
    rm2ctrl_capture.write_png(str(out), 1, 1, 4, bytes([30, 20, 10, 0]))
    chunks, _ = parse_png(out.read_bytes())
    scan = zlib.decompress(b"".join(chunks[b"IDAT"]))
    assert scan[0] == 0, "missing filter byte"
    assert bytes(scan[1:4]) == bytes([10, 20, 30]), "B,G,R not swapped"
    assert scan[4] == 0xFF, "alpha not forced opaque"


def test_cli_help_and_dry_run_need_no_device(capsys):
    assert rm2ctrl_capture.main(["--help"]) == 0
    assert rm2ctrl_capture.main(["--dry-run"]) == 0
    capsys.readouterr()


def test_cli_rejects_bad_argument():
    assert rm2ctrl_capture.main(["--bogus"]) == 2


def test_cli_refuses_to_clobber_without_force(tmp_path, capsys):
    out = tmp_path / "screen.png"
    out.write_bytes(b"mine")
    assert rm2ctrl_capture.main(["--out", str(out)]) == 1
    assert out.read_bytes() == b"mine", "existing file was touched"
    capsys.readouterr()


def test_cli_rejects_control_characters_in_path():
    assert rm2ctrl_capture.main(["--out", "a\x01b.png"]) == 2


def test_dry_run_creates_no_files(tmp_path):
    out = tmp_path / "new.png"
    assert rm2ctrl_capture.main(["--out", str(out), "--dry-run"]) == 0
    assert not out.exists()
    assert not tmp_path.joinpath("new.raw").exists()


def test_cli_rejects_bad_host():
    assert rm2ctrl_capture.main(["--host", "-evil"]) == 2
    assert rm2ctrl_capture.main(["--host", "a\x01b"]) == 2


def test_cli_rejects_bad_key_and_timeout(tmp_path):
    assert rm2ctrl_capture.main(["--key", str(tmp_path / "nope")]) == 2
    assert rm2ctrl_capture.main(["--key", str(tmp_path)]) == 2
    for bad in ("0", "31", "x", "-3"):
        assert rm2ctrl_capture.main(["--timeout", bad]) == 2


def test_cli_flags_reach_the_ssh_wrapper(tmp_path, monkeypatch):
    key = tmp_path / "id_test"
    key.write_bytes(b"k")
    seen = {}
    monkeypatch.setattr(rm2ctrl_capture, "capture",
                        lambda png, raw, force: seen.update(png=png, raw=raw))
    for var in ("RM_HOST", "RM_KEY", "RM_CONNECT_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)
    out = tmp_path / "s.png"
    rc = rm2ctrl_capture.main(["--out", str(out), "--host", "root@x",
                          "--key", str(key), "--timeout", "7"])
    assert rc == 0
    assert seen == {"png": str(out), "raw": str(tmp_path / "s.raw")}
    import os
    assert os.environ["RM_HOST"] == "root@x"
    assert os.environ["RM_KEY"] == str(key)
    assert os.environ["RM_CONNECT_TIMEOUT"] == "7"



def _frame_fakes(monkeypatch, ident2=None, recheck_fail=False,
                 short_raw=False):
    C = rm2ctrl_capture
    ident1 = (1234, 999)
    calls = {"snap": 0}

    def fake_snapshot(cap):
        calls["snap"] += 1
        ident = ident2 if (ident2 and calls["snap"] > 1) else ident1
        maps = "00007000-02000000 rw-p 00000000 00:00 0"
        return ident, maps, "hexdump", [(0x7000, 0x2000000)], "exe"

    def fake_read_block(cap, pid, regions, tool, addr, size):
        if size == 4 and addr == C.STATIC:
            return struct.pack("<I", 0x5000)
        if size == 4 and addr == 0x5000:
            return struct.pack("<I", C.CARTA_VPTR)
        if size == C.PAIR_LEN:
            pair = bytearray(size)
            off = C.IMGA_OFF - C.PAIR_OFF + C.D_OFF
            pair[off:off + 4] = struct.pack("<I", 0x6000)
            return bytes(pair)
        if size == C.HDR_LEN:
            hdr = bytearray(size)
            struct.pack_into("<I", hdr, C.W_OFF, 1404)
            struct.pack_into("<I", hdr, C.H_OFF, 1872)
            struct.pack_into("<I", hdr, C.PIX_OFF, 0x7000)
            struct.pack_into("<I", hdr, C.FMT_OFF, 4)
            struct.pack_into("<I", hdr, C.BPL_OFF, 5616)
            return bytes(hdr)
        return bytes(size)

    def fake_raw_read(cap, pid, start, blocks):
        if short_raw:
            raise C.Fail("short raw read: got 100 of %d bytes; "
                         % (blocks * 4096))
        return bytes(blocks * 4096)

    def fake_write_png(path, w, h, stride, raw):
        with open(path, "wb") as f:
            f.write(b"PNG")

    monkeypatch.setattr(C, "snapshot", fake_snapshot)
    monkeypatch.setattr(C, "read_block", fake_read_block)
    monkeypatch.setattr(C, "raw_read", fake_raw_read)
    monkeypatch.setattr(C, "write_png", fake_write_png)
    if recheck_fail:
        def boom(cap, ident, helper, pair, dA, hdr, exeline):
            raise C.Fail("simulated post-transfer change")
        monkeypatch.setattr(C, "recheck", boom)


def test_rejected_capture_publishes_nothing(tmp_path, monkeypatch):
    _frame_fakes(monkeypatch, recheck_fail=True)
    png, raw = str(tmp_path / "s.png"), str(tmp_path / "s.raw")
    with pytest.raises(rm2ctrl_capture.Fail):
        rm2ctrl_capture.capture(png, raw, True)
    assert list(tmp_path.iterdir()) == [], "temp files leaked"


def test_preexisting_outputs_survive_rejection(tmp_path, monkeypatch):
    _frame_fakes(monkeypatch, recheck_fail=True)
    png, raw = tmp_path / "s.png", tmp_path / "s.raw"
    png.write_bytes(b"old-png")
    raw.write_bytes(b"old-raw")
    with pytest.raises(rm2ctrl_capture.Fail):
        rm2ctrl_capture.capture(str(png), str(raw), True)
    assert png.read_bytes() == b"old-png"
    assert raw.read_bytes() == b"old-raw"


def test_changed_starttime_aborts(tmp_path, monkeypatch):
    _frame_fakes(monkeypatch, ident2=(1234, 1000))
    png, raw = str(tmp_path / "s.png"), str(tmp_path / "s.raw")
    with pytest.raises(rm2ctrl_capture.Fail, match="identity changed"):
        rm2ctrl_capture.capture(png, raw, True)
    assert list(tmp_path.iterdir()) == [], "rejected frame published"


def test_short_raw_read_aborts_without_files(tmp_path, monkeypatch):
    _frame_fakes(monkeypatch, short_raw=True)
    png, raw = str(tmp_path / "s.png"), str(tmp_path / "s.raw")
    with pytest.raises(rm2ctrl_capture.Fail, match="short raw read"):
        rm2ctrl_capture.capture(png, raw, True)
    assert list(tmp_path.iterdir()) == [], "partial frame published"


class _Run:
    def __init__(self, rc=0, out=b"", err=b""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _fake_run_factory(calls, rc=0, out="", err=""):
    def fake_run(argv, **kw):
        calls.append(argv)
        if kw.get("text"):
            text = out.decode("ascii", "replace") if isinstance(out,
                                                                bytes) else out
            return _Run(rc, text, err)
        return _Run(rc, out, err)
    return fake_run


def test_block_transport_error_uses_original_stderr_once(monkeypatch):
    calls = []
    fake = _fake_run_factory(calls, rc=1, err="dd: cannot skip: I/O error")
    monkeypatch.setattr("subprocess.run", fake)
    cap = rm2ctrl_capture.Cap()
    with pytest.raises(rm2ctrl_capture.Fail, match="cannot skip"):
        rm2ctrl_capture.read_block(cap, 1, [(0, 2 ** 32)], "hexdump", 4096, 4)
    assert len(calls) == 1, "reread process memory for diagnostics"


def test_short_block_read_reports_counts_without_reread(monkeypatch):
    calls = []
    fake = _fake_run_factory(calls, out="12")
    monkeypatch.setattr("subprocess.run", fake)
    cap = rm2ctrl_capture.Cap()
    with pytest.raises(rm2ctrl_capture.Fail, match="short block read"):
        rm2ctrl_capture.read_block(cap, 1, [(0, 2 ** 32)], "hexdump", 4096, 64)
    assert len(calls) == 1, "reread process memory for diagnostics"


def _snapshot_output(fw="20260827113527", size="22046100",
                     xohash=None, qthash=None):
    xohash = xohash or rm2ctrl_capture.SUPPORTED_XOCHITL_SHA256
    qthash = qthash or rm2ctrl_capture.SUPPORTED_QTGUI_SHA256
    stat = "1234 (xochitl) R" + " 0" * 25
    return ("\n".join(["PID=1234", "STAT:", stat, "---FW---", fw, size,
                       "---MAPS---",
                       "00010000-00020000 r-xp 00000000 b3:02 935 "
                       "/usr/bin/xochitl",
                       "---TOOLS---", "/usr/bin/dd", "/usr/bin/hexdump",
                       "---SUMS---",
                       "%s  /usr/bin/xochitl" % xohash,
                       "%s  /usr/lib/libQt6Gui.so.6" % qthash,
                       ""]))


def test_snapshot_accepts_supported_build(monkeypatch):
    calls = []
    monkeypatch.setattr("subprocess.run",
                        _fake_run_factory(calls, out=_snapshot_output()))
    ident, maps, tool, regions, exe = rm2ctrl_capture.snapshot(rm2ctrl_capture.Cap())
    assert ident == (1234, 0)
    assert tool == "hexdump"
    assert regions == [(0x10000, 0x20000)]


def test_snapshot_rejects_unknown_build(monkeypatch):
    calls = []
    bad = _snapshot_output(fw="20990101000000", size="1")
    monkeypatch.setattr("subprocess.run", _fake_run_factory(calls, out=bad))
    with pytest.raises(rm2ctrl_capture.Fail, match="unsupported build"):
        rm2ctrl_capture.snapshot(rm2ctrl_capture.Cap())


def test_output_aliasing_the_key_is_rejected(tmp_path):
    key = tmp_path / "id_test"
    key.write_bytes(b"k")
    rc = rm2ctrl_capture.main(["--out", str(key), "--key", str(key), "--force"])
    assert rc == 2


def test_identical_outputs_are_rejected(tmp_path):
    same = str(tmp_path / "same.raw")
    assert rm2ctrl_capture.main(["--out", same, "--raw", same]) == 2


def test_symlink_and_nonregular_outputs_are_rejected(tmp_path):
    real = tmp_path / "real.png"
    real.write_bytes(b"x")
    link = tmp_path / "link.png"
    link.symlink_to(real)
    assert rm2ctrl_capture.main(["--out", str(link), "--force"]) == 2
    assert rm2ctrl_capture.main(["--out", str(tmp_path)]) == 2


def test_publish_rejects_racing_writer_without_force(tmp_path, monkeypatch):
    final = tmp_path / "s.png"
    final.write_bytes(b"winner")
    tmp = tmp_path / "tmp"
    tmp.write_bytes(b"loser")
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    with pytest.raises(rm2ctrl_capture.Fail, match="exists"):
        rm2ctrl_capture.publish(str(tmp), str(final), False)
    assert final.read_bytes() == b"winner", "race overwrote live file"


def test_publish_no_force_and_force_paths(tmp_path):
    src = tmp_path / "a"
    src.write_bytes(b"frame")
    rm2ctrl_capture.publish(str(src), str(tmp_path / "b"), False)
    assert (tmp_path / "b").read_bytes() == b"frame"
    assert not src.exists(), "staging link left behind"
    dst = tmp_path / "c"
    dst.write_bytes(b"old")
    with pytest.raises(rm2ctrl_capture.Fail, match="exists"):
        rm2ctrl_capture.publish(str(tmp_path / "b"), str(dst), False)
    assert dst.read_bytes() == b"old"
    rm2ctrl_capture.publish(str(tmp_path / "b"), str(dst), True)
    assert dst.read_bytes() == b"frame"


def test_block_pipe_has_no_success_mask():
    pipe = rm2ctrl_capture._block_pipe(1, 0, 1)
    assert "pipefail" in pipe
    assert "; echo" not in pipe, "trailing echo masks pipeline status"


def test_block_pipe_reports_dd_failure_through_shell():
    pipe = rm2ctrl_capture._block_pipe(1, 999999999, 1)
    r = subprocess.run(["sh", "-c", pipe], capture_output=True, text=True,
                       timeout=15)
    assert r.returncode != 0, "pipeline swallowed the dd failure"
    assert r.stderr.strip() != "", "original dd diagnostic lost"


def test_block_error_reports_original_stderr_without_reread(monkeypatch):
    calls = []
    fake = _fake_run_factory(calls, rc=1,
                             err="dd: SIMULATED I/O error")
    monkeypatch.setattr("subprocess.run", fake)
    with pytest.raises(rm2ctrl_capture.Fail, match="SIMULATED I/O error"):
        rm2ctrl_capture.read_block(rm2ctrl_capture.Cap(), 1, [(0, 2 ** 32)],
                              "hexdump", 4096, 4)
    assert len(calls) == 1


def test_snapshot_rejects_same_size_different_binary(monkeypatch):
    calls = []
    bad = _snapshot_output(xohash="0" * 64)
    monkeypatch.setattr("subprocess.run", _fake_run_factory(calls, out=bad))
    with pytest.raises(rm2ctrl_capture.Fail, match="hash"):
        rm2ctrl_capture.snapshot(rm2ctrl_capture.Cap())


def test_snapshot_rejects_different_qtgui(monkeypatch):
    calls = []
    bad = _snapshot_output(qthash="f" * 64)
    monkeypatch.setattr("subprocess.run", _fake_run_factory(calls, out=bad))
    with pytest.raises(rm2ctrl_capture.Fail, match="hash"):
        rm2ctrl_capture.snapshot(rm2ctrl_capture.Cap())