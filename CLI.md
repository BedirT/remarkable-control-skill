# `rm2ctrl`, reMarkable 2 control CLI

One command drives the tablet over USB SSH. It wraps the skill's
scripts (`scripts/rm2ctrl-capture.py`, `scripts/rm2ctrl-svg.py`,
`scripts/rm2ctrl-ssh.sh`, tablet-side `/tmp/rm2ctrl-input`) with stable flags,
so agents learn one tool instead of five scripts. The skill
([SKILL.md](SKILL.md)) stays the brain: it teaches *when* to run what
and how to verify. `rm2ctrl` is the hands.

## Install

```sh
git clone https://github.com/BedirT/remarkable-control-skill
cd remarkable-control-skill
chmod +x rm2ctrl
export PATH="$PWD:$PATH"   # or symlink rm2ctrl into ~/bin
rm2ctrl shot --dry-run         # prove the SSH path, no tablet changes
```

Needs: Python 3 (stdlib only), OpenSSH client, USB-connected
reMarkable 2 with key auth (see `references/01-access-auth.md`).
First tablet use also needs the input helper on the device:

```sh
scp scripts/rm2ctrl-input/rm2ctrl-input root@10.11.99.1:/tmp/rm2ctrl-input
```

## Connection flags (every subcommand)

```
--host HOST        SSH target (default root@10.11.99.1)
--key PATH         SSH identity file (default ~/.ssh/id_rsa_remarkable)
--timeout SECS     connect timeout 1..30 (default 5)
```

These override `RM_HOST` / `RM_KEY` / `RM_CONNECT_TIMEOUT`.

## Commands

### `rm2ctrl shot`, screenshot (read-only)

```sh
rm2ctrl shot [--out screen.png] [--raw frame.raw] [--force] [--dry-run]
```

Pulls xochitl's composed 1404×1872 page over SSH (~8 s). No taps,
no refresh, no tablet changes. `--dry-run` prints the plan without
touching the device. Strict hash gate: wrong firmware aborts loudly.

### `rm2ctrl tap`, finger tap

```sh
rm2ctrl tap X Y        # X 0..1403 left to right, Y 0..1871 top to bottom
```

Out-of-range coords are rejected before anything touches the device.
Always verify with `rm2ctrl shot` after.

### `rm2ctrl swipe`, finger swipe

```sh
rm2ctrl swipe X1 Y1 X2 Y2 [--steps 24] [--step-ms 12]
```

Natural finger profile by default (small touch size, eased pace,
the profile proven to trigger page creation in notebooks). Judge page
creation by UI state, never by canvas bytes.

### `rm2ctrl draw`, pen drawing from SVG

```sh
rm2ctrl draw FILE.svg [--box X Y W H] [--speed 1-5] [--press A[:B]]
  [--skip-fill COLOR]... [--skip-class NAME]... [--run]
```

Parses `<path>`/`<polyline>`/`<polygon>`, fits into the canvas box
(default margins), emits one pen-down stroke per subpath. Without
`--run` it prints strokes to stdout (dry). With `--run` it feeds the
`pend` daemon's FIFO: notebook page open, pen tool selected.

Skip invisible shapes whose outlines would tangle the drawing:

```sh
rm2ctrl draw logo.svg --run --box 200 500 1000 700 --skip-fill fff
```

### `rm2ctrl ssh`, escape hatch

```sh
rm2ctrl ssh -- <command>...     # raw command on the tablet
```

Prefer the four commands above. Raw SSH is for file ops and
diagnostics the CLI does not cover yet.

## Draw speed (`--speed 1-5`, default 2)

| Level | Pace | Feels like | Path error* |
|---|---|---|---|
| 1 careful | ~50 px/s | tracing with a ruler |, |
| 2 tracing | ~125 px/s | careful hand | ~1 px mean |
| 3 steady | ~300 px/s | normal writing | ~3 px mean |
| 4 quick | ~800 px/s | fast sketch | visible wobble |
| 5 device | max | fling | corners cut (17–20 px) |

\* Measured on the same logo: mean distance of drawn ink from the
true SVG path. Level 2 is the default because it is the slowest pace
that still finishes a page in reasonable time (~6 s per long stroke).

Rule of thumb: line art with curves → 1–2; straight test lines → 3;
never 4–5 for anything a human will look at.

## Observe–act–verify

```sh
rm2ctrl shot --out before.png
rm2ctrl tap 660 1445
rm2ctrl shot --out after.png     # e-ink needs ~1 s settle first
```

One action, then a screenshot. Never assume a tap landed.

## Exit codes

0 ok · 1 device/transfer failure (message on stderr) · 2 bad
arguments (usage error, nothing touched).
