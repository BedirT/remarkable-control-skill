#!/usr/bin/env python3
"""rm2ctrl-live.py -- persistent feed cache for instant agent screenshots.

The tablet is still the source, but the SSH + capture work happens in a
background daemon every few seconds. An agent `live shot` is then just a
local file copy, PC-fast.

State dir (default /tmp/rm2ctrl-live, override with RM_LIVE_DIR or --dir):
  latest.png  latest complete frame (atomic replace)
  latest.raw  matching raw sidecar
  meta.json   {seq, time, age, pid, interval, error}
  daemon.pid  running daemon pid
  daemon.log  daemon stdout/stderr

Usage:
  rm2ctrl-live.py start [--dir D] [--interval SECS]
  rm2ctrl-live.py shot --out screen.png [--dir D]
  rm2ctrl-live.py status [--dir D]
  rm2ctrl-live.py stop [--dir D]
  rm2ctrl-live.py daemon [--dir D] [--interval SECS]  # internal, spawned by start
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
CAPTURE = os.path.join(ROOT, "rm2ctrl-capture.py")
DEFAULT_DIR = os.environ.get("RM_LIVE_DIR", "/tmp/rm2ctrl-live")
DEFAULT_INTERVAL = 2.0


def state_dir(args_dir=None):
    d = args_dir or os.environ.get("RM_LIVE_DIR", DEFAULT_DIR)
    return os.path.abspath(d)


def paths(d):
    return {
        "dir": d,
        "png": os.path.join(d, "latest.png"),
        "raw": os.path.join(d, "latest.raw"),
        "meta": os.path.join(d, "meta.json"),
        "pid": os.path.join(d, "daemon.pid"),
        "log": os.path.join(d, "daemon.log"),
    }


def read_meta(p):
    try:
        with open(p["meta"], "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_meta(p, **kw):
    m = read_meta(p)
    m.update(kw)
    m["time"] = time.time()
    tmp = p["meta"] + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(m, f)
        os.replace(tmp, p["meta"])
    except OSError:
        pass
    return m


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def daemon_pid(p):
    try:
        with open(p["pid"], "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def cmd_start(args):
    d = state_dir(args.dir)
    os.makedirs(d, exist_ok=True)
    p = paths(d)
    old = daemon_pid(p)
    if old and pid_alive(old):
        print("live: already running pid=%d dir=%s" % (old, d))
        return 0
    interval = args.interval or DEFAULT_INTERVAL
    logf = open(p["log"], "ab", buffering=0)
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "daemon",
         "--dir", d, "--interval", str(interval)],
        stdin=subprocess.DEVNULL, stdout=logf, stderr=subprocess.STDOUT,
        start_new_session=True, close_fds=True)
    with open(p["pid"], "w") as f:
        f.write(str(proc.pid))
    write_meta(p, pid=proc.pid, interval=interval, seq=0, error=None)
    print("live: starting pid=%d dir=%s interval=%ss" % (proc.pid, d, interval))
    print("live: wait ~1 frame, then `rm2ctrl live shot --out screen.png`")
    return 0


def run_daemon(args):
    d = state_dir(args.dir)
    os.makedirs(d, exist_ok=True)
    p = paths(d)
    interval = args.interval or DEFAULT_INTERVAL
    with open(p["pid"], "w") as f:
        f.write(str(os.getpid()))
    seq = 0
    stop = []
    def _term(signum, frame):
        stop.append(True)
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    print("live daemon pid=%d dir=%s interval=%s" % (os.getpid(), d, interval),
          flush=True)
    while not stop:
        t0 = time.time()
        try:
            rc = subprocess.run(
                [sys.executable, CAPTURE,
                 "--out", p["png"], "--raw", p["raw"], "--force"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=max(30, interval + 30)).returncode
            if rc == 0:
                seq += 1
                write_meta(p, pid=os.getpid(), interval=interval,
                           seq=seq, error=None)
                print("frame %d ok %.1fs" % (seq, time.time() - t0), flush=True)
            else:
                write_meta(p, pid=os.getpid(), interval=interval,
                           seq=seq, error="capture rc=%d" % rc)
                print("frame failed rc=%d" % rc, flush=True)
        except Exception as ex:  # never exit on a bad frame
            write_meta(p, pid=os.getpid(), interval=interval,
                       seq=seq, error=str(ex)[:200])
            print("frame error: %s" % ex, flush=True)
        for _ in range(int(interval * 10)):
            if stop:
                break
            time.sleep(0.1)
    print("live daemon stopping", flush=True)
    return 0


def cmd_shot(args):
    d = state_dir(args.dir)
    p = paths(d)
    pid = daemon_pid(p)
    if not pid or not pid_alive(pid):
        print("live: no feed running in %s (pid %s dead). "
              "Start it with `rm2ctrl live start`, or one-time "
              "`rm2ctrl shot --out %s`." % (d, pid, args.out),
              file=sys.stderr)
        return 1
    if not os.path.isfile(p["png"]):
        print("live: feed warming up, no frame yet in %s. Retry in ~2s, "
              "or one-time `rm2ctrl shot`." % d, file=sys.stderr)
        return 1
    m = read_meta(p)
    seq = m.get("seq", 0)
    age = time.time() - m.get("time", time.time())
    interval = m.get("interval", DEFAULT_INTERVAL)
    out = args.out or "screen.png"
    if os.path.isdir(out):
        print("live: refusing directory output: %s" % out, file=sys.stderr)
        return 2
    try:
        shutil.copyfile(p["png"], out)
    except OSError as ex:
        print("live: copy failed: %s" % ex, file=sys.stderr)
        return 1
    if m.get("error"):
        print("live: warning: last daemon frame had an error (%s), "
              "serving last good frame." % m["error"])
    if age > max(10.0, interval * 3):
        print("live: warning: frame is %.0fs old (seq %s). Page may be "
              "static, or the feed may be stuck; check `rm2ctrl live status`."
              % (age, seq))
    print("live: saved %s from feed seq=%s age=%.1fs (local copy, no SSH)"
          % (out, seq, age))
    return 0


def cmd_status(args):
    d = state_dir(args.dir)
    p = paths(d)
    pid = daemon_pid(p)
    alive = bool(pid and pid_alive(pid))
    m = read_meta(p)
    age = time.time() - m.get("time", 0) if m.get("time") else -1
    print("dir: %s" % d)
    print("daemon: %s (pid %s)" % ("running" if alive else "stopped", pid))
    print("frame: seq=%s age=%s" % (m.get("seq", "none"),
                                    ("%.1fs" % age) if age >= 0 else "none"))
    if m.get("error"):
        print("last error: %s" % m["error"])
    print("files: %s %s" % (os.path.isfile(p["png"]), os.path.isfile(p["raw"])))
    return 0 if alive else 1


def cmd_stop(args):
    d = state_dir(args.dir)
    p = paths(d)
    pid = daemon_pid(p)
    if not pid or not pid_alive(pid):
        print("live: already stopped (dir %s)" % d)
        try:
            os.unlink(p["pid"])
        except OSError:
            pass
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as ex:
        print("live: stop failed: %s" % ex, file=sys.stderr)
        return 1
    for _ in range(50):
        if not pid_alive(pid):
            break
        time.sleep(0.1)
    if pid_alive(pid):
        print("live: pid %d did not stop, try kill -9" % pid, file=sys.stderr)
        return 1
    try:
        os.unlink(p["pid"])
    except OSError:
        pass
    print("live: stopped pid=%d (frames kept in %s)" % (pid, d))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="rm2ctrl-live",
                                 description="Persistent feed cache.")
    ap.add_argument("action",
                    choices=["start", "shot", "status", "stop", "daemon"])
    ap.add_argument("--dir", default=None)
    ap.add_argument("--out", default="screen.png")
    ap.add_argument("--interval", type=float, default=None)
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.action == "start":
        return cmd_start(a)
    if a.action == "daemon":
        return run_daemon(a)
    if a.action == "shot":
        return cmd_shot(a)
    if a.action == "status":
        return cmd_status(a)
    if a.action == "stop":
        return cmd_stop(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
