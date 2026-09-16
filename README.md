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

2. Capture the screen and check the bytes (`references/02-display-screenshot.md`):

   ```sh
   scripts/rm-screenshot.sh --out screen.png
   # raw equivalent (single-row simplification covers ONLY swtfb.01/fb0 rgb565le; :mem: eras need the 02 matrix or reStream/ScreenShare):
   # ssh -n <same fail-fast flags> root@10.11.99.1 "cat /dev/shm/swtfb.01" > fb.raw
   # ls -l fb.raw  # expect 5256576 bytes (1404*1872*2, 16-bit path)
   # ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 \
   #   -i fb.raw -vf "transpose=1" screen.png
   ```

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
  02-display-screenshot.md      framebuffer specs, fb paths, pix_fmt matrix, capture commands
  03-input-automation.md        tap/swipe scripts shipped; pen stroke + KEY_POWER via the 03 section-5 pattern (no dedicated script)
  04-files-content.md           xochitl tree, USB endpoints, rmapi, cloud / rmfakecloud
  05-ui-ux-map.md               screen hierarchy, gestures, 9-tool toolbar, states, e-ink design rules
  06-tooling-ecosystem.md       capture / input / file tool comparison with repo links + status
  07-autonomy-loop.md           zero-interruption observe-act-verify discipline, timeouts, recovery
scripts/                        runnable sh/py helpers for the loop above
```

## Contributing

Keep SKILL.md thin — detail belongs in `references/`, runnable code in
`scripts/`. Ground every command and path in on-device evidence; mark
anything unverified `[INFERENCE]` and flag Paper Pro deltas instead of
mixing them. See [SKILL.md](SKILL.md) safety rules before adding
anything that writes to the display pipeline or the xochitl tree.

License: see [LICENSE](LICENSE).
