# 07 — Autonomy Loop

The zero-interruption control pattern: how an agent drives a reMarkable 2
from a host with no human in the loop. USB + keys first, one action per
step, screenshot-verify everything, fail fast and recover deterministically.

## 1. Doctrine

1. **USB + keys first.** `root@10.11.99.1` over USB-Ethernet with a
   pre-installed key is the deterministic path — no passwords, no
   pairing codes, no prompts. WiFi SSH is secondary; cloud pairing is
   out of the autonomous path entirely.
2. **One action, then verify.** Every step is exactly one input event
   (tap / swipe / key) or one file operation, followed by a fresh
   screenshot plus a byte-level check. Never chain speculative actions.
3. **Fail fast, recover by table.** SSH probes, capture, and injection
   all have short timeouts (§4). On failure, run the matching recovery
   (§5) — never retry blindly, never prompt the user.
4. **Bytes before pixels.** If a goal is reachable by file push/pull
   (upload a PDF, fetch an archive), do that instead of driving the UI.
   Touch injection is for UI-only goals.

## 2. Preconditions (run once per session)

Timeouts are intentional: 2 s for the fail-fast probe, 5 s default for
bulk transfer. Both wrappers (`scripts/rm-ssh.sh` / `scripts/rm-screenshot.sh`) honor `RM_CONNECT_TIMEOUT` (integer 1..30, default 5) — the 2 s probe needs `RM_CONNECT_TIMEOUT=2` or raw ssh/config.

```sh
# key auth, no prompts, short timeouts, detached stdin
ssh -n -o BatchMode=yes -o ConnectTimeout=2 \
    -o PasswordAuthentication=no \
    -o PubkeyAcceptedKeyTypes=+ssh-rsa \
    -o HostKeyAlgorithms=+ssh-rsa \
    root@10.11.99.1 true || exit 1   # fail-fast probe
# expect: reMarkable 2.0 (same fail-fast flags on every ssh line)
ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no \
    -o PubkeyAcceptedKeyTypes=+ssh-rsa -o HostKeyAlgorithms=+ssh-rsa \
    root@10.11.99.1 cat /sys/devices/soc0/machine
```

Recommended `~/.ssh/config` alias (set up once, out of band):

```
host remarkable
  Hostname 10.11.99.1
  User root
  Port 22
  IdentityFile ~/.ssh/id_rsa_remarkable
  BatchMode yes
  ConnectTimeout 2
  PasswordAuthentication no
  PubkeyAcceptedKeyTypes +ssh-rsa
  HostKeyAlgorithms +ssh-rsa
```

Then every autonomous command is `ssh remarkable …` / `scp … :
…` / `curl http://10.11.99.1/…`. Key notes:

- Generate with `ssh-keygen -t rsa -f ~/.ssh/id_rsa_remarkable -N ''`
  (modern hosts default ed25519, unusable on rM2; safer: passphrase + ssh-agent, chmod 600, `rm-ssh-over-wlan off` when unneeded).
- `ssh-copy-id` on OpenSSH < 9.4 installs to the wrong path on-device;
  the reliable recipe is `tee -a /home/root/.ssh/authorized_keys`
  (mode 700 / 600) — see 01-access-auth.
- After every OS update the SSH host key regenerates: delete the stale
  `known_hosts` entry for `10.11.99.1` and re-accept, non-interactively.

## 3. The loop: observe → act → verify

```
┌─────────────────────────────────────────────────┐
│ OBSERVE: single-shot capture → PNG              │
│   ssh root@10.11.99.1 "cat /dev/shm/swtfb.01"   │
│     > fb.raw  (+ firmware matrix fallback,      │
│     reStream.sh probe order — never hardcode    │
│     one fb path) → ffmpeg → out.png             │
│          │                                      │
│ ACT (exactly one):                              │
│   a) file op: curl POST /upload / GET           │
│      /download/{guid}/pdf, or ssh+rsync         │
│      (stop xochitl before tree writes)          │
│   b) input: one uinput tap / swipe /            │
│      pen stroke / KEY_POWER via the             │
│      injector (12 ms frame interp)              │
│          │                                      │
│ VERIFY: fresh screenshot + byte check           │
│   re-capture → PNG; expect 5 256 576 B          │
│   for a 16-bit full frame; diff against        │
│   the pre-action frame for the expected         │
│   region change. Match → next step.             │
│   Mismatch → §5 recovery, then re-observe.      │
└─────────────────────────────────────────────────┘
```

Concrete verify example:

```sh
ssh -n root@10.11.99.1 "cat /dev/shm/swtfb.01" > fb.raw
ls -l fb.raw  # expect 5256576 bytes (1404*1872*2, 16-bit path)
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 \
  -i fb.raw -vf "transpose=1" verify.png
```

Rules:

- Always capture to a **file** (`-o cap.png/mp4`) and convert — never
  `ffplay`-only in autonomy; there is no human watching. Wrapper note: re-running `scripts/rm-screenshot.sh` to the same path needs `--force` (default ffmpeg `-n` refuses to clobber).
- Always `trap` cleanup: `kill $(pidof restream)` / close the injector
  on exit.
- Probe order for the framebuffer follows upstream `reStream.sh` (not
  `scripts/`): test `[ -f /dev/shm/swtfb.01 ]`, read `update.conf` for the firmware
  version, then select `fb_file / pix_fmt / size / transpose / skip`
  from the matrix (skips 8 / 2629636 / 4705256 by era). Do not hardcode
  one matrix row. `scripts/rm-screenshot.sh` implements the two
  always-safe rows (swtfb.01 else fb0, rgb565le) in one SSH connection;
  `:mem:` eras need the matrix or reStream/ScreenShare.
- For file uploads, `GET` the target folder listing FIRST — `POST
  /upload` lands in the last-listed folder (with `Origin:
  http://10.11.99.1` header).

## 4. Timing budget

| Phase | Value | Source / note |
|---|---|---|
| SSH fail-fast probe | `ConnectTimeout=2`, `BatchMode=yes` | Never block on a prompt |
| Input frame interpolation | **12 ms** between swipe/stroke frames | ~24 steps for a full swipe; deterministic gesture timing |
| Post-lift e-ink settle | **0.5–1.0 s** sleep, then verify | Panel needs to finish the waveform |
| Render latency assumption | **100–450 ms** before first re-capture | Never assume instant render |
| Screenshot byte check | Immediate (`ls -l`) | 5 256 576 B = 16-bit full frame; ~10.5 MB = 32-bit bgra path |
| Stream pipe latency | Hundreds of ms (ffmpeg + lz4 buffering) | Prefer single-shot `cat`+`ffmpeg` for verify; stream only for interaction |
| WiFi enable gate | One-time `rm-ssh-over-wlan on` over USB (rM2 OS > 3.20) | Persists on `/home` across updates |

## 5. Recovery table

| Symptom | Cause | Recovery |
|---|---|---|
| `no matching host key type … Their offer: ssh-rsa` | Modern OpenSSH vs Dropbear | Add `PubkeyAcceptedKeyTypes +ssh-rsa` + `HostKeyAlgorithms +ssh-rsa` (config above) |
| Host-key mismatch after update | OS update regenerates host key | Remove stale `known_hosts` entry for `10.11.99.1` / WiFi IP, re-accept, continue |
| SSH password screen blank / `df /` = 100% | Root partition full | `journalctl --vacuum-size=1M` over SSH, then re-read password |
| WiFi SSH refused on OS > 3.20 | SSH-over-WLAN gate | Over USB: `rm-ssh-over-wlan on`, then use the WiFi IP |
| Proxy / hosts reverted after update | OS replaces root partition | Re-enable rmfakecloud-proxy + `/etc/hosts` entries after every update |
| Sleep PNG / templates gone after update | Static screens + root partition reset | Re-install sleep PNG + custom templates, restart xochitl |
| UI unresponsive to injection | xochitl wedged or double-consumer lag (xochitl + second reader ⇒ ~0.75 s lag, missed taps) | `systemctl restart xochitl` (`daemon-reload; reset-failed xochitl; restart xochitl` if needed); never leave two framebuffer consumers running |
| Need exclusive input for a critical section | xochitl holds all nodes open | Short `EVIOCGRAB` / `grab_context()` grab, or full `systemctl stop xochitl` (+ stop `genie` if installed), then start again |
| Factory reset occurred | Keys wiped, password regenerated | Re-install keys + re-record password before continuing — full session bootstrap |
| `put` flaky / sync mismatch | rmapi new-sync-protocol migration | Back up first; prefer USB/SSH path over cloud for authoritative moves |
| `no framebuffer node` from `scripts/rm-screenshot.sh` (remote exit 3) | Firmware serves another layout — no swtfb.01/fb0 | Use the 02 pix_fmt matrix or reStream/ScreenShare; `error: ssh failed (rc=…)` instead means network/keys/host-key — different row |

## 6. Never-prompt rules

1. **Never depend on the 8-char cloud pairing code** in the autonomous
   path (needs screen typing at my.remarkable.com → tablet). Document
   it, don't drive it.
2. **Never depend on the device lock PIN** — separate from SSH, not
   scriptable; rmfakecloud documents PIN reset for rM1/rM2 only.
3. **Never run SSH without `BatchMode=yes` + `ConnectTimeout`** —
   a hanging password prompt is a stuck agent.
4. **Never `ffplay`-only** — always record/convert to a file and check
   bytes.
5. **Never force an e-ink refresh from capture code**
   (`MXCFB_SEND_UPDATE`); capture is read-only `mmap`/`dd`/`cat`.
   rm2fb-server is the only writer and must version-match.
6. **Never confirm a destructive reformat** (EPUB reformat orphans
   strokes; delete/reset wipes data) without a fresh screenshot showing
   the exact warning dialog.
7. **Never hardcode** `/dev/input/eventN` numbers, framebuffer
   matrix rows, or WiFi IPs — enumerate (`EVIOCGNAME`, `reStream.sh`
   probe, DHCP/GPLv3 page) at runtime.
8. **Never leave two framebuffer consumers running** (xochitl +
   oxide/rm2fb reader ⇒ lag + missed taps).

## 7. Minimal session script (reference)

```sh
#!/bin/sh
# zero-interruption rM2 session skeleton (single-row simplification covers ONLY swtfb.01/fb0 rgb565le; :mem: eras need the 02 matrix or reStream/ScreenShare,
# or just call scripts/rm-screenshot.sh which probes swtfb.01 else fb0)
set -e
SSH="ssh -n -o BatchMode=yes -o ConnectTimeout=2 -o PasswordAuthentication=no \
  -o PubkeyAcceptedKeyTypes=+ssh-rsa -o HostKeyAlgorithms=+ssh-rsa root@10.11.99.1"
$SSH true                                           # fail-fast probe
$SSH cat /sys/devices/soc0/machine                  # expect reMarkable 2.0
$SSH "cat /dev/shm/swtfb.01" > before.raw           # observe
ls -l before.raw                                    # byte check
# ... exactly one act (file op or single injection) ...
sleep 1                                             # e-ink settle
$SSH "cat /dev/shm/swtfb.01" > after.raw            # verify
ls -l after.raw
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 \
  -i after.raw -vf "transpose=1" after.png
```

Firmware ≥ 2.9 note: capture rows that need VNC-server/rm2fb fail there
— switch the OBSERVE step to the ScreenShare backend (start ScreenShare
on the tablet first; the one sanctioned manual step). Paper Pro: same,
plus Developer Mode + `rm-ssh-over-wlan on` prerequisites.
