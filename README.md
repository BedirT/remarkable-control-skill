<h1 align="center">remarkable-control-skill</h1>

<p align="center">
  <img src="https://img.shields.io/badge/reMarkable-2-black" alt="reMarkable 2" />
  <img src="https://img.shields.io/badge/transport-USB_SSH-blue" alt="transport: USB SSH" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license: MIT" />
</p>

An agent skill for controlling a reMarkable 2 tablet. It was born out of
my own experiments and wanting some extra tooling on my reMarkable.

My motto for agentic development: your harness is only as strong as the
least observable end state you have. And the reMarkable 2 exposes no
screen recording of any kind. The only solution I could find out of the
box was ScreenShare, which needs a manual connection first and then lets
the agent work. Useless to me, because the development I was doing
restarts the tablet quite often and needs hands-off test suites.

There was no API for any of this, so I reverse-engineered the whole path
under my own guidance, with my AI agents doing the heavy lifting (Codex
Astra 6 and Meta Spark 1.3): how the screen is composed, where the
pixels live, and how to pull them out over plain SSH with nothing installed
on the tablet.

So I did the investigation by hand and built this skill: a complete suite
of tools and guidance for agents to reach the reMarkable 2 screen and all
the tooling around it, without needing any external search, screen capture
included. It also bakes in the working structures I use, so the
agent knows what works best, how to interact with the tablet, and how to
develop for it.

## Why this exists

Nothing on the tablet helps an agent. No screenshot API that survives, no
UI automation layer, no screen recording. What is actually there:

- **Display**: 1404x1872 monochrome e-ink with 100-450 ms render latency.
State can only be proven by capture, never assumed. The only stock way out
(ScreenShare) needs a manual tap and dies on restart.
 - **Input**: kernel evdev nodes, not UI APIs. A tiny static helper
   (`scripts/rm-input/`, copied to the tablet's `/tmp`) taps and swipes
   with screen coordinates; pen and keys are not done yet.
- **Platform**: one Qt 6 app (xochitl) owns the composed screen. It
restarts without warning, and every firmware moves its internals, so all
addresses are pinned per build and re-verified on every run.

This skill grounds each of those planes (access, display, input, files,
screen map, tooling, loop discipline) in on-device paths that were verified
live, so agents act deterministically instead of guessing.

Target is the **reMarkable 2**. Paper Pro differences (Developer Mode,
display stack, CPU arch) are flagged where they matter and never mixed
into rM2 procedures.

## Install

Copy-paste to your agent:

```text
Install the reMarkable 2 skill from https://github.com/BedirT/remarkable-control-skill:
clone it, follow the README quickstart to connect over USB SSH, and take a
first screen capture to prove the loop works.
```

## Quickstart

1. Connect over USB and prove key auth (details: `references/01-access-auth.md`):

   ```sh
   scripts/rm-ssh.sh true   # expect exit 0; user root, port 22
   # raw equivalent (BatchMode + ConnectTimeout: never prompt, fail fast):
   # ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no \
   #   -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa root@10.11.99.1 true
   ```

2. Capture the screen (reverse-engineered, zero tablet setup) (`references/02-display-screenshot.md` §2):

   ```sh
   scripts/rm-capture.py --out screen.png   # ~8 s, writes screen.png + screen.raw
   # Reads xochitl's own composed page (1404x1872 RGB32 QImage) over USB SSH.
   # No tablet-side setup, taps, refresh, or uploads. Pre/post rechecks abort on change.
   # Timing (3 runs, fw 20260827113527): 8.3 s total: snapshot+hash 1.3 s, metadata+recheck+probe 3.7 s, transfer 1.0 s, PNG 0.1 s, final recheck 2.3 s.
   # Strict mode: stop on ABORT (02 §3); ScreenShare/photo only if the user allows a human step.
   # Why the checks: raw reads fail silent, so each check turns a wrong read into a loud abort.
   # Hash gate (wrong build = wrong addresses), object-type and shape checks (is it really the
   # screen image?), mapping check (/dev/fb0 looks valid but is stale), pre/post rechecks (the app
   # has restarted mid-run before: a torn frame is discarded, never saved), byte cap and deadline
   # (a bug can never dump forever), safe saving (a failed run never overwrites the last good shot).

 3. Act exactly once: one file op (`references/04-files-content.md`)
   or one tap/swipe via `/tmp/rm-input` (`references/03-input-automation.md` §5):
 ```sh
 scp scripts/rm-input/rm-input root@10.11.99.1:/tmp/rm-input   # first use only
 scripts/rm-ssh.sh -- /tmp/rm-input tap 700 936; sleep 1       # tap center
 scripts/rm-capture.py --out verify.png                        # prove it
 ```
 See `references/07-autonomy-loop.md` for the full loop discipline.

Start every task at [SKILL.md](SKILL.md): it routes to the right
reference and states the safety rules.

## Structure

```text
SKILL.md                        thin router (<100 lines): connect, loop, safety
references/
  01-access-auth.md             USB/WiFi SSH, keys, password paths, Web UI, pairing avoidance
  02-display-screenshot.md      panel specs, capture method (§2), failure fallback (§3), safety, Paper Pro deltas
   03-input-automation.md        tap/swipe via /tmp/rm-input helper (§5); pen + keys not implemented
   04-files-content.md           xochitl tree, USB endpoints, rmapi, cloud / rmfakecloud
   05-ui-ux-map.md               screen hierarchy, gestures, 13-icon toolbar, states, e-ink design rules
   06-tooling-ecosystem.md       capture / input / file tool comparison with repo links + status
   07-autonomy-loop.md           zero-interruption observe-act-verify discipline, timeouts, recovery
 scripts/                        rm-capture.py (screen capture), rm-ssh.sh (SSH wrapper), rm-input/ (Rust uinput helper, static ARM build + source)
```

## Contributing

Keep SKILL.md thin: detail belongs in `references/`, runnable code in
`scripts/`. Ground every command and path in on-device evidence; mark
anything unverified `[INFERENCE]` and flag Paper Pro deltas instead of
mixing them. See [SKILL.md](SKILL.md) safety rules before adding
anything that writes to the display pipeline or the xochitl tree.


