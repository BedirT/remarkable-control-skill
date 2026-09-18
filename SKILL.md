---
name: remarkable-control
description: Autonomous reMarkable 2 control over USB SSH, connect, observe-act-verify, capture screen, inject input, manage files. Use when driving, screenshotting, or transferring content on a reMarkable 2 tablet.
---

# reMarkable 2 Control

Zero-interruption autonomy for reMarkable 2 (1404×1872) over USB. No cloud pairing, no password prompts, no forced refreshes in the loop.

## When to use

 - Driving the tablet (taps, swipes), screenshotting state, moving files on/off device.
- Do NOT use for Paper Pro steps without reading the deltas (different SSH enablement, display stack, arch).

## Quick connect

```sh
scripts/rm-ssh.sh true   # USB, user root; expect exit 0 with key auth (see 01)
# or raw ssh with the same fail-fast flags the wrapper uses:
# ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no \
#   -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa root@10.11.99.1 true
```

Your key lives in `/home/root/.ssh/authorized_keys` on the tablet (on `/home`, survives updates); private key on the host (`RM_KEY`, default `~/.ssh/id_rsa_remarkable`). Dropbear host keys live under `/etc` and regenerate on update, hence the `ssh-keygen -R` + re-accept flow. WiFi SSH needs `rm-ssh-over-wlan on` first (rM2 OS > 3.20 only). Full setup: [01](references/01-access-auth.md).

## Observe–act–verify loop

1. **Observe**: `rm2ctrl shot --out screen.png` ([02](references/02-display-screenshot.md) §2). On failure in strict mode: stop with the diagnostic (02 §3; assisted options only if the user allows a human step).
2. **Act**: one input (`rm2ctrl tap` / `rm2ctrl swipe`, [03](references/03-input-automation.md) §5; SVG line art via `rm2ctrl draw --run`) or file op ([04](references/04-files-content.md)); know the screen map ([05](references/05-ui-ux-map.md)). `rm2ctrl ssh -- <cmd>` runs a raw tablet command (ssh options before host, remote command after; use `--` to separate; dangerous ssh options need `--allow-unsafe-ssh-opts`, see [01](references/01-access-auth.md)).
3. **Verify**: re-screenshot; e-ink needs 0.5–1.0 s settle after input. Never verify by forcing a refresh.

 Timeouts: 2 s fail-fast probe, 5 s bulk-transfer default, `scripts/rm-ssh.sh`
 honors `RM_CONNECT_TIMEOUT` (integer 1..30, default 5), so the 2 s probe needs `RM_CONNECT_TIMEOUT=2` or raw ssh/config. Tool choice: [06](references/06-tooling-ecosystem.md); loop discipline: [07](references/07-autonomy-loop.md).

## Draw with the pen (working feature)

The helper draws real pen strokes, not just taps: a `pend` daemon
holds one pen device and takes strokes from `/tmp/pen.fifo`
(`S STEPS STEP_MS P0 P1 X1 Y1 ...`, screen coords, packed mode M1
is the default). `rm2ctrl draw drawing.svg --run` draws
SVG line art (paths/polylines, curves flattened, one pen-down per
subpath; `--speed 1-5` sets the pace, default 2 tracing pace, full
table in [CLI.md](CLI.md)). Every stroke opens with a short light glide that settles
the tablet's smoothing, without it lines kick sideways near the
start (that filter settling is the small jump you may still see a
trace of). Stroke starts under the toolbar (x<~135) are swallowed:
keep drawing inside the canvas. After any helper redeploy: start
helper first, then restart xochitl, verify it holds the node,
otherwise strokes fail silently (full detail: [03](references/03-input-automation.md) §5b–5d).

## References

| # | File | Contents |
|---|---|---|
| 01 | [access & auth](references/01-access-auth.md) | USB/WiFi SSH, keys, password paths, Web UI, pairing avoidance |
| 02 | [display & screenshot](references/02-display-screenshot.md) | 1404×1872 specs, capture method, fallback paths |
| 03 | [input automation](references/03-input-automation.md) | tap/swipe/pen via /tmp/rm-input helper + SVG drawing (keys unimplemented) |
| 04 | [files & content](references/04-files-content.md) | xochitl tree, USB endpoints, rmapi, cloud/rmfakecloud |
| 05 | [UI/UX map](references/05-ui-ux-map.md) | screens, gestures, toolbar, states |
| 06 | [tooling ecosystem](references/06-tooling-ecosystem.md) | capture/sync tool comparison |
| 07 | [autonomy loop](references/07-autonomy-loop.md) | zero-interruption operating discipline |

## Safety rules

- NEVER force an e-ink refresh to verify, screenshot instead.
- Stop xochitl before writing its file tree (`systemctl stop xochitl`), restart after.
- Capture paths are read-only; never send display-update ioctls from capture code.
- Verify every action by screenshot; fail fast (`BatchMode`, `ConnectTimeout`), never prompt.
