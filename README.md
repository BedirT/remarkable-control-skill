# remarkable-control-skill

Autonomous control of a reMarkable 2 tablet: USB SSH access, screen
capture, touch/pen injection, file transfer, and a zero-interruption
observe → act → verify operating loop. No cloud pairing, no password
prompts, no human in the loop.

## Why this exists

Driving an e-ink tablet from an agent is unlike driving a phone or
desktop: the panel is 1404 × 1872 monochrome with 100–450 ms render
latency, input flows through kernel evdev nodes (not UI APIs), and every
state change must be proven by screenshot because nothing renders
instantly. This skill grounds each of those planes — access, display,
input, files, screen map, tooling, loop discipline — in verified
on-device paths so agents act deterministically instead of guessing.

Target is the **reMarkable 2**. Paper Pro differences (Developer Mode,
display stack, CPU arch) are flagged where they matter and never mixed
into rM2 procedures.

## Quickstart

1. Connect over USB and prove key auth (details: `references/01-access-auth.md`):

   ```sh
   scripts/rm-ssh.sh true   # expect exit 0; user root, port 22
   # raw equivalent (BatchMode + ConnectTimeout: never prompt, fail fast):
   # ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no \
   #   -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa root@10.11.99.1 true
   ```

2. Capture the screen — reverse-engineered, zero tablet setup (`references/02-display-screenshot.md` §2):

   ```sh
   scripts/rm-capture.py --out screen.png   # ~8 s, writes screen.png + screen.raw
   # Reads xochitl's own composed page (1404x1872 RGB32 QImage) over USB SSH.
   # No tablet-side setup, taps, refresh, or uploads. Pre/post rechecks abort on change.
   # Timing (3 runs, fw 20260827113527): 8.3 s — snapshot+hash 1.3 s, metadata+recheck+probe 3.7 s, transfer 1.0 s, PNG 0.1 s, final recheck 2.3 s.
   # Strict mode: stop on ABORT (02 §3); ScreenShare/photo only if the user allows a human step.
   # Why the checks: raw reads fail silent, so each check turns a wrong read into a loud abort.
   # Hash gate (wrong build = wrong addresses), object-type and shape checks (is it really the
   # screen image?), mapping check (/dev/fb0 looks valid but is stale), pre/post rechecks (the app
   # has restarted mid-run before — a torn frame is discarded, never saved), byte cap and deadline
   # (a bug can never dump forever), safe saving (a failed run never overwrites the last good shot).

3. Act exactly once — one file op (`references/04-files-content.md`)
   or one uinput tap/swipe/stroke (`references/03-input-automation.md`) —
   sleep 0.5–1 s for e-ink settle, then re-capture to verify
   (`references/07-autonomy-loop.md`).

Start every task at [SKILL.md](SKILL.md): it routes to the right
reference and states the safety rules.

## Structure

```text
SKILL.md                        thin router (<100 lines): connect, loop, safety
references/
  01-access-auth.md             USB/WiFi SSH, keys, password paths, Web UI, pairing avoidance
  02-display-screenshot.md      panel specs, capture method (§2), failure fallback (§3), safety, Paper Pro deltas
  03-input-automation.md        tap/swipe scripts shipped; pen stroke + KEY_POWER via the 03 section-5 pattern (no dedicated script)
  04-files-content.md           xochitl tree, USB endpoints, rmapi, cloud / rmfakecloud
  05-ui-ux-map.md               screen hierarchy, gestures, 9-tool toolbar, states, e-ink design rules
  06-tooling-ecosystem.md       capture / input / file tool comparison with repo links + status
  07-autonomy-loop.md           zero-interruption observe-act-verify discipline, timeouts, recovery
scripts/                        rm-capture.py (screen capture), rm-ssh.sh (SSH wrapper), rm-tap.py / rm-swipe.py (input)
```

## Contributing

Keep SKILL.md thin — detail belongs in `references/`, runnable code in
`scripts/`. Ground every command and path in on-device evidence; mark
anything unverified `[INFERENCE]` and flag Paper Pro deltas instead of
mixing them. See [SKILL.md](SKILL.md) safety rules before adding
anything that writes to the display pipeline or the xochitl tree.

License: see [LICENSE](LICENSE).
