# 07 — Autonomy Loop

The zero-interruption control pattern: how an agent drives a reMarkable 2
from a host with no human in the loop. USB + keys first, one action per
step, screenshot-verify everything, fail fast and recover deterministically.

## 1. Doctrine

1. **USB + keys first.** `root@10.11.99.1` over USB-Ethernet with a
   pre-installed key is the deterministic path — no passwords, no
   pairing codes, no prompts. WiFi SSH is secondary; cloud pairing is
   out of the autonomous path entirely.
 2. **One action, then verify.** Every step is exactly one tap/swipe
   (`/tmp/rm-input` over SSH, 03 §5) or one file operation, followed by
   a fresh screenshot plus a byte-level check. Never chain speculative
   actions.
3. **Fail fast, recover by table.** SSH probes, capture, and injection
   all have short timeouts (§4). On failure, run the matching recovery
   (§5) — never retry blindly, never prompt the user.
4. **Bytes before pixels.** If a goal is reachable by file push/pull
   (upload a PDF, fetch an archive), do that instead of driving the UI.
   Touch injection is for UI-only goals.

## 2. Preconditions (run once per session)

Timeouts are intentional: 2 s for the fail-fast probe, 5 s default for
bulk transfer. `scripts/rm-ssh.sh` honors `RM_CONNECT_TIMEOUT` (integer 1..30, default 5); `scripts/rm-capture.py` takes `--timeout` — the 2 s probe needs `--timeout 2` / `RM_CONNECT_TIMEOUT=2` or raw ssh/config.

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
│ OBSERVE: scripts/rm-capture.py → PNG+raw        │
│   --out verify.png (+ screen.raw 10513152 B)     │
│   (02 §2; on failure 02 §3)                      │
│          │                                      │
│ ACT (exactly one):                              │
│   a) file op: curl POST /upload / GET           │
│      /download/{guid}/pdf, or ssh+rsync         │
│      (stop xochitl before tree writes)          │
 │   b) input: one tap / swipe via                 │
 │      /tmp/rm-input over SSH (03 §5)             │
│          │                                      │
│ VERIFY: re-capture → PNG + raw; expect          │
│   10513152 B raw (02 §2); diff against          │
│   the pre-action frame for the expected         │
│   region change. Match → next step.             │
│   Mismatch → §5 recovery, then re-observe.      │
└─────────────────────────────────────────────────┘
```

Concrete verify example:

```sh
python3 scripts/rm-capture.py --out verify.png      # + verify.raw
ls -l verify.raw  # expect 10513152 bytes (1404*1872*4, 32-bit path)
```

Rules:

- Always capture to a **file** — never `ffplay`-only in autonomy; there is no human watching. Re-running `scripts/rm-capture.py` to the same paths needs `--force`.
- Always `trap` cleanup: close the injector / kill any viewer on exit.
- Capture with `scripts/rm-capture.py --out verify.png` (02 §2); on failure see 02 §3.
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
7. **Never hardcode** `/dev/input/eventN` numbers or WiFi IPs — enumerate (`EVIOCGNAME`, DHCP/GPLv3 page) at runtime.
8. **Never leave two framebuffer consumers running** (xochitl +
   second reader ⇒ lag + missed taps).

## 7. Minimal session script (reference)

```sh
#!/bin/sh
# zero-interruption rM2 session skeleton
set -e
SSH="ssh -n -o BatchMode=yes -o ConnectTimeout=2 -o PasswordAuthentication=no \
  -o PubkeyAcceptedKeyTypes=+ssh-rsa -o HostKeyAlgorithms=+ssh-rsa root@10.11.99.1"
$SSH true                                           # fail-fast probe
$SSH cat /sys/devices/soc0/machine                  # expect reMarkable 2.0
python3 scripts/rm-capture.py --out before.png        # observe (~5 s, + before.raw)
ls -l before.raw                                    # expect 10513152 bytes
# ... exactly one act (file op or single injection) ...
sleep 1                                             # e-ink settle
python3 scripts/rm-capture.py --out after.png         # verify
ls -l after.raw                                     # expect 10513152 bytes
```

Old capture rows don't apply on this firmware — the OBSERVE
step above is `scripts/rm-capture.py` (02 §2, no tablet step). Paper Pro:
ScreenShare + Developer Mode + `rm-ssh-over-wlan on` prerequisites.
