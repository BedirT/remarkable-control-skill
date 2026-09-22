# 02 — Display & Screenshot (reMarkable 2)

Capture is read-only and safe to poll. Never force an e-ink refresh to verify — screenshot the PNG instead.

## 1. Panel specs (rM2; never mix with Paper Pro)

- Resolution **1404 × 1872 portrait** (W × H).
- Pipeline: no hardware EPDC on rM2 — xochitl links SWTCON (software EPDC) wrapping a QImage; capture reads that image, never the e-ink controller.

## 2. Capture: `scripts/rm2ctrl-capture.py` (proven live 2026-09-16, fw 20260827113527)

```sh
rm2ctrl shot --out screen.png            # fast default: single check, ~3 SSH ops
rm2ctrl shot --strict --out screen.png   # backup: full hashes + rechecks, ~17 SSH ops, ~8 s
rm2ctrl live start                       # feed daemon, captures every ~2 s
rm2ctrl live shot --out screen.png       # instant local copy, no SSH
```

xochitl's EPFramebufferCarta1000 singleton (static `0x1517084`) owns an inherited 1404×1872 RGB32 QImage; the pixel allocation sits in an ordinary readable mapping. No tablet-side setup, taps, refresh, uploads, ptrace, or signals.

Chain (both modes): pidof xochitl → static → vptr must equal `0x120f738` (Carta1000) → 28-byte image pair at +88 → image A header `1404×1872 fmt=4 bpl=5616`. Then: 10,513,152-byte extent inside ONE `rw-p` mapping (never `/dev/fb0`) → one page-aligned raw `dd` (`bs=4096`) over `scripts/rm2ctrl-ssh.sh` stdout → slice → host PNG decode (B,G,R → RGB).

Fast mode (default): firmware + xochitl size gate, no sha256, batched metadata reads, no pre/post rechecks, no 64-byte probe. One snapshot, ~2 metadata SSH calls, one bulk transfer. SSH reuse is on by default (`RM_SSH_MUX=0` disables).

Strict mode (`--strict`): firmware + size + xochitl/QtGui hash gate, plus pre- and post-transfer rechecks (pid, exe mapping, static, vptr, pair, header) that abort on any change; includes the 64-byte probe. The recheck is not atomic, so one read is a candidate, not a verified current-panel image.

The static address, vptr, field offsets, and exe load bias are firmware-pinned constants, proven only on 20260827113527 — re-verify them after any update (re-derivation notes live outside the repo; ask the maintainer). Re-resolved every run: pid, helper pointer, pixel pointer.

Live feed (`scripts/rm2ctrl-live.py` via `rm2ctrl live`): a host daemon loops the fast path every `--interval` seconds (default 2) into `/tmp/rm2ctrl-live/latest.png` (atomic replace) plus `meta.json` (seq, time, error). `live shot` copies that file locally. It warns on stale frames but still serves static pages; it never silently falls back to an 8 s capture and never serves a frame after the daemon died. Keep the feed for loops; keep one-time `shot` for cold starts.

Budgets: 12 MiB process-memory cap, 60 s deadline (30 SSH ops). Timed 2026-09-16, 3 back-to-back strict runs on fw 20260827113527: 8.3 s each — snapshot+hash gate 1.3 s, metadata+pre-recheck+probe 3.7 s, 10.5 MB bulk transfer 1.0 s, PNG encode 0.1 s, final recheck+publish 2.3 s. Byte-exact repeat: two back-to-back runs produced identical SHA-256. Tracking: a fresh pen stroke appeared in exactly its region on the next capture. Output PNG is 1404×1872 portrait directly — no transpose needed.
## 3. If capture fails

Strict (unattended) mode: stop. Report the ABORT line as the diagnostic.
Do not retry in a loop and do not reach for another tool on your own —
no on-tablet fallback is worth trying on 2026 firmware (`/dev/fb0` is a
stale dark fill; stock `screenshot` likely kills xochitl — see §6).

Assisted alternatives, only when the user explicitly relaxes the
no-human-step rule, in order:

1. ScreenShare: the user starts ScreenShare on the tablet, then capture/view through a VNC viewer ([rmview](https://github.com/bordaigorl/rmview), `:5900`/`:5901`). One manual tap; throttled by the official stack.
2. The user sends a photo of the screen.

## 4. Safety (read-only capture)

- Capture (`dd` over `/proc/<pid>/mem`) issues no ioctl and cannot ghost or flash the panel — safe to poll.
- Risk lives only in *writing*: wrong waveform/flags cause ghosting or full-flash (`INIT`+`FULL` flashes B/W). Never send `MXCFB_SEND_UPDATE` from capture code.
- Verify by screenshot PNG + byte-size check (expect 10,513,152 B raw), never by forcing a refresh.

## 5. Paper Pro deltas

Different SoC/display stack — [INFERENCE] no xochitl-memory path there; use official ScreenShare. Re-verify resolution and node paths on-device; never reuse the 1404×1872 specs.

## 6. 2026 firmware facts (20260827113527; re-check after any update)

- No `/dev/shm/swtfb.01`. `/dev/fb0` serves a stale dark fill (mean ~21/255, asleep or awake) — not live pixels. Its xochitl mapping is not readable via `/proc/<pid>/mem` (Input/output error).
- Do NOT run stock `/usr/bin/screenshot` or `kill -USR2` xochitl: USR2 is not caught, so it likely kills xochitl.
