"""Host-only tests for the rmk CLI (no tablet needed)."""
import importlib.util
from importlib.machinery import SourceFileLoader

import pytest

rmk = SourceFileLoader("rmk", "rmk").load_module()

SVG = ('<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
       '<polyline points="10,10 30,10 30,30"/></svg>\n')


def test_speed_table_default_is_tracing_pace():
    assert rmk.load("rm_svg", "rm-svg.py").SPEEDS[2] == (1.5, 12)


def test_draw_dry_prints_strokes_without_device(tmp_path, capsys):
    f = tmp_path / "t.svg"
    f.write_text(SVG)
    assert rmk.main(["draw", str(f)]) == 0
    out = capsys.readouterr().out
    assert any(line.startswith("S ") for line in out.splitlines())


def test_draw_speed_out_of_range_rejected():
    with pytest.raises(SystemExit) as e:
        rmk.main(["draw", "x.svg", "--speed", "9"])
    assert e.value.code == 2


def test_tap_out_of_range_rejected_before_device():
    with pytest.raises(SystemExit) as e:
        rmk.main(["tap", "2000", "100"])
    assert e.value.code == 2


def test_shot_dry_run_needs_no_device(capsys):
    assert rmk.main(["shot", "--dry-run"]) == 0
    capsys.readouterr()


def test_ssh_without_command_is_usage_error(capsys):
    assert rmk.main(["ssh"]) == 2
    capsys.readouterr()
