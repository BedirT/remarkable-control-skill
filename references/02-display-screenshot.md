# 02 — Display & Screenshot (reMarkable 2)

Capture is read-only and safe to poll. Never force an e-ink refresh to verify — screenshot the PNG instead.

Sources: [reStream](https://github.com/rien/reStream) ([reStream.sh](https://raw.githubusercontent.com/rien/reStream/master/reStream.sh), [main.rs](https://raw.githubusercontent.com/rien/reStream/master/src/main.rs)), [rmview](https://github.com/bordaigorl/rmview), [rM-vnc-server](https://github.com/pl-semiotics/rM-vnc-server), [remarkable2-framebuffer](https://github.com/ddvk/remarkable2-framebuffer) ([swtfb.cpp](https://github.com/ddvk/remarkable2-framebuffer/blob/master/src/shared/swtfb.cpp)), [libremarkable](https://github.com/canselcik/libremarkable), [SSH guide](https://remarkable.guide/guide/access/ssh.html), [Toltec](https://toltec-dev.org/).

## 1. Panel specs (rM2; never mix with Paper Pro)

- Resolution **1404 × 1872 portrait** (W × H). Grounded in `dimensions.rs` (`DISPLAYWIDTH=1404, DISPLAYHEIGHT=1872`), `swtfb.cpp` (`maxWidth=1404, maxHeight=1872`), `xofb/main.cpp`. (rM1 is 1408 × 1872.)
- Pipeline: no hardware EPDC on rM2 — xochitl links SWTCON (software EPDC) wrapping a QImage; capture reads that image, never the e-ink controller.

## 2. Framebuffer paths (probe, don't hardcode)

Newer firmware moves the live image; select the path at runtime:

| Path | When present | Format |
|---|---|---|
| `/dev/shm/swtfb.01` | older fw (QImage shared mem) | `rgb565le`, 2 Bpp |
| `/dev/fb0` | rM1, or rM2 with rm2fb-client shim | `rgb565le`, 2 Bpp |
| `:mem:` = `/proc/<xochitl-pid>/mem` at the `/dev/fb0`-mapped address + skip | newer fw (offsets vary, see §4) | `gray8` / `gray16be` / `bgra` by fw |
| `/dev/shm/xofb` | ddvk `xofb` LD_PRELOAD hook installed | `rgb565`, 2 Bpp |

```sh
SSH="ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa"
$SSH root@10.11.99.1 'cat /sys/devices/soc0/machine'   # expect: reMarkable 2.0
$SSH root@10.11.99.1 '[ -f /dev/shm/swtfb.01 ] && echo swtfb || echo no-swtfb'
PID=$($SSH root@10.11.99.1 '/bin/pidof xochitl'); case "$PID" in ''|*[!0-9]*) exit 1;; esac
$SSH root@10.11.99.1 "grep /dev/fb0 /proc/$PID/maps"
```

Wrapper exit mapping (`scripts/rm-screenshot.sh`): remote exit 3 prints `no framebuffer node (no /dev/shm/swtfb.01, no /dev/fb0)` — the firmware serves another layout, so use the §4 pix_fmt matrix or reStream/ScreenShare. Any other nonzero ssh exit prints `error: ssh failed (rc=…)` instead — network, key-auth, or host-key trouble, not a layout issue. A convert failure prints `error: ffmpeg failed (rc=N) …` and exits 1.

## 3. Single-shot capture (the verify step)

```sh
# shared-mem path (fastest one-shot, if present); same fail-fast flags as above
# (BatchMode + ConnectTimeout: never hang on a password/host-key prompt)
ssh -n <fail-fast flags> remarkable "cat /dev/shm/swtfb.01" > fb.raw
ls -l fb.raw   # expect 5256576 bytes (1404*1872*2)
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 -i fb.raw -vf "transpose=1" out.png
```

```sh
# /dev/fb0 path (rM1, or rM2 with rm2fb shim)
/usr/bin/ssh -n <fail-fast flags> remarkable "dd if=/dev/fb0 bs=5256576 count=1 2>/dev/null" > fb0.raw
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 -i fb0.raw -vf "transpose=1" fb0.png
```

Byte-size check: a full 16-bit frame MUST be **5,256,576 B** (1404×1872×2); a 32-bit `bgra` frame is ~10.5 MB. Short reads = stale/torn capture — retake, never "fix" by refreshing the panel.

Wrapper (`scripts/rm-screenshot.sh --out screen.png [--host HOST] [--key PATH] [--force] [--dry-run]`, defaults from `RM_HOST`/`RM_KEY`): `--out`/`--host` must not start with `-`, `--out`/`--host`/`--key` must not contain control characters (violations exit 2), `--key` must be a readable regular file (fifos, directories, and devices are refused), and `--out` must never resolve to the same file as `--key` (refused even with `--force`: captures must not overwrite the identity file). Re-running to the same path needs `--force`; by default an existing `--out` is refused and ffmpeg runs with `-n`, while `--force` overwrites via `-y`. Concurrent runs to the same path are safe: publish claims atomically, so exactly one wins and losers exit 1 without `--force` (last-writer-wins with `--force`).

## 4. `:mem:` pix_fmt matrix (firmware-dependent)

From `reStream.sh` + `src/main.rs` (`rm2_fb_offset` parses `/proc/<pid>/maps` for the `/dev/fb0` line). Pick exactly one row:

| Firmware | pix_fmt | Size | Transpose / filter | Skip |
|---|---|---|---|---|
| ancient | `gray8` | 1404x1872, 1 Bpp | `transpose=2` | 8 |
| ≥ 3.7 | `gray16be` | 1404x1872, 2 Bpp | `curves=all='0/0 0.125/1 1/1',transpose=3` (only 1/8 brightness, hence gain) | 8 |
| ≥ 3.24 | `bgra` | 1872x1404 (W/H swapped), 4 Bpp | `transpose=2` | 2629636 |
| ≥ 3.27.1.0 | `bgra` | 1872x1404 (W/H swapped), 4 Bpp | `transpose=1` | 4705256 |

```sh
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt gray16be -s 1404x1872 -i mem.raw -vf "curves=all='0/0 0.125/1 1/1',transpose=3" out.png
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt bgra -s 1872x1404 -i mem32.raw -vf "transpose=1" out.png
ffmpeg -vcodec rawvideo -f rawvideo -pix_fmt gray8 -s 1404x1872 -i mem8.raw -vf "transpose=2" out.png
```

On-device native dump alternative: libremarkable `examples/screenshot.rs` (`dump_region` → rgb565le → sRGB888 → PNG); needs the Toltec display/rm2fb server on rM2.

## 5. Stream selection: reStream vs VNC vs ScreenShare

| Tool | Transport | Use when |
|---|---|---|
| [reStream](https://github.com/rien/reStream) (`restream.arm.static` + `reStream.sh`) | on-device Rust reader → lz4 → SSH stdout (or raw TCP `:16789` with `-u`); host ffmpeg/ffplay | deterministic streaming over USB; `-o cap.mp4` to record, `-p` portrait, `-u` for more fps / less CPU, `-m` throughput measure |
| rmview + rM-vnc-server (`:5900`, ZRLE, damage-tracked) | RFB/VNC, optional SSH tunnel | fw ≤ 2.8; USB gives negligible latency, smooth drawing; WiFi + SSH tunnel stutters |
| rmview + official ScreenShare | TLS VNC `:5900` + UDP `:5901` timestamp challenge | fw ≥ 2.9 (VNC-server/rm2fb fail there); start ScreenShare on tablet first, then connect; throttled by official stack |

```sh
# verify the binary hash after download (unpinned binaries run as root on the tablet)
scp restream.arm.static remarkable:/home/root/restream
# sha256sum restream.arm.static  # compare against the release you audited
ssh -n <fail-fast flags> remarkable 'chmod +x /home/root/restream'
./reStream.sh -s 10.11.99.1    # landscape ffplay
./reStream.sh -p                # portrait
./reStream.sh -o cap.mp4        # record
```

Rule: single-shot `cat` + ffmpeg for verify; stream only for interaction. Always capture to file, never ffplay-only in autonomy.

## 6. Safety (read-only capture)

- Capture (`cat` / `dd` / mmap) issues no ioctl and cannot ghost or flash the panel — safe to poll.
- Risk lives only in *writing*: wrong waveform/flags cause ghosting or full-flash (`INIT`+`FULL` flashes B/W). Never send `MXCFB_SEND_UPDATE` from capture code; rm2fb-server is the only writer and must version-match its address table.
- Verify by screenshot PNG + byte-size check (§3), never by forcing a refresh.

## 7. Paper Pro deltas

Toltec states no Paper Pro support; rm2fb address tables are rM2-xochitl-specific (different SoC/display stack) — [INFERENCE] no rm2fb/VNC-server path there; use official ScreenShare. Re-verify resolution and node paths on-device; never reuse the 1404×1872 matrix.
