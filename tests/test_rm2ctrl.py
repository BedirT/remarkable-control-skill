"""Host-only tests for the rm2ctrl CLI (no tablet needed)."""
import importlib.util
from importlib.machinery import SourceFileLoader

import pytest

rm2ctrl = SourceFileLoader("rm2ctrl", "rm2ctrl").load_module()

SVG = ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
       '<polyline points="10,10 30,10 30,30"/></svg>\n')


def test_speed_table_default_is_tracing_pace():
    assert rm2ctrl.load("rm_svg", "rm2ctrl-svg.py").SPEEDS[2] == (1.5, 12)


def test_draw_dry_prints_strokes_without_device(tmp_path, capsys):
    f = tmp_path / "t.svg"
    f.write_text(SVG)
    assert rm2ctrl.main(["draw", str(f)]) == 0
    out = capsys.readouterr().out
    assert any(line.startswith("S ") for line in out.splitlines())


def test_draw_speed_out_of_range_rejected():
    with pytest.raises(SystemExit) as e:
        rm2ctrl.main(["draw", "x.svg", "--speed", "9"])
    assert e.value.code == 2


def test_tap_out_of_range_rejected_before_device():
    with pytest.raises(SystemExit) as e:
        rm2ctrl.main(["tap", "2000", "100"])
    assert e.value.code == 2


def test_shot_dry_run_needs_no_device(capsys):
    assert rm2ctrl.main(["shot", "--dry-run"]) == 0
    capsys.readouterr()


def test_ssh_without_command_is_usage_error(capsys):
    assert rm2ctrl.main(["ssh"]) == 2
    capsys.readouterr()

def test_shot_strict_dry_run_needs_no_device(capsys):
    assert rm2ctrl.main(["shot", "--strict", "--dry-run"]) == 0
    capsys.readouterr()


def test_live_status_and_shot_without_daemon_need_no_device(tmp_path, capsys):
    d = str(tmp_path / "feed")
    assert rm2ctrl.main(["live", "status", "--dir", d]) == 1
    capsys.readouterr()
    assert rm2ctrl.main(["live", "shot", "--out", str(tmp_path / "s.png"),
                         "--dir", d]) == 1
    capsys.readouterr()


def test_live_shot_copies_local_frame_without_ssh(tmp_path):
    import json
    import os
    import time
    live = rm2ctrl.load("rm2ctrl_live", "rm2ctrl-live.py")
    d = tmp_path / "feed"
    d.mkdir()
    (d / "latest.png").write_bytes(b"FRAME")
    (d / "latest.raw").write_bytes(b"RAW")
    with open(d / "daemon.pid", "w") as f:
        f.write(str(os.getpid()))
    with open(d / "meta.json", "w") as f:
        json.dump({"seq": 7, "time": time.time(), "interval": 2}, f)
    out = str(tmp_path / "s.png")
    assert live.main(["shot", "--dir", str(d), "--out", out]) == 0
    assert open(out, "rb").read() == b"FRAME"
