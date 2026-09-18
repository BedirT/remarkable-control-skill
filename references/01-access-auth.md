# 01 — Access & Auth (reMarkable 2)

Zero-interruption rule: USB SSH + key auth is the autonomous path. Cloud pairing and passwords are manual fallbacks, never the default.

Sources: [SSH guide](https://remarkable.guide/guide/access/ssh.html), [USB web interface](https://remarkable.guide/tech/usb-web-interface.html), [Developer mode](https://remarkable.guide/tech/developer-mode.html), [Recovery](https://remarkable.guide/tech/recovery.html), [FAQ](https://remarkable.guide/faqs.html), [rmapi auth](https://github.com/juruen/rmapi/blob/master/api/auth.go).

## 1. USB: the deterministic path

Tablet is always `10.11.99.1` over the USB cable (Ethernet-over-USB gadget; host gets a `10.11.99.x` address). SSH is port 22, user `root`, server Dropbear. No enablement needed on rM2.

```sh
ssh -n root@10.11.99.1 true          # smoke test; expect exit 0, no prompt (with key)
curl -s http://10.11.99.1/ | head # Web UI (after enabling, see §5)
```

[INFERENCE] macOS may need extra RNDIS/ECM driver handling — verify once with `ifconfig` / `system_profiler SPUSBDataType` if the interface does not appear.

## 2. SSH password location (firmware-dependent)

The string shown is the per-device random `root` password. Write it down before anything risky.

| Firmware | Path |
|---|---|
| OS < 3.9 or > 3.18 | Menu > Settings > Help > Copyright and licenses > under "GPLv3 Compliance" |
| OS 3.9 – 3.18 | Menu > Settings > About (inside Help) > Copyright and licenses > same GPLv3 block |

Caveats: factory reset regenerates/wipes the password and clears `/home` keys; a full root partition (`df -h /` = 100%, fix with `journalctl --vacuum-size=1M`) can blank the password screen.

## 3. Key auth (preferred) + ssh config

```sh
ssh-keygen -t rsa -f ~/.ssh/id_rsa_remarkable -N ''   # no passphrase (convenient; safer: use a passphrase + ssh-agent, chmod 600, and `rm-ssh-over-wlan off` when WiFi SSH is unneeded)
ssh -n root@10.11.99.1 mkdir -p -m 700 /home/root/.ssh
cat ~/.ssh/id_rsa_remarkable.pub | ssh root@10.11.99.1 'tee -a /home/root/.ssh/authorized_keys'
ssh -n root@10.11.99.1 chmod 600 /home/root/.ssh/authorized_keys
# idempotent re-run (no duplicates, quote-safe: the key travels over stdin, never through shell quoting):
# ssh root@10.11.99.1 'k="$(cat)"; grep -qxF "$k" /home/root/.ssh/authorized_keys || printf "%s\n" "$k" >> /home/root/.ssh/authorized_keys' < ~/.ssh/id_rsa_remarkable.pub
```

(`ssh-copy-id` before OpenSSH 9.4 installs to the wrong path on-device; the `tee` recipe works everywhere.)

`~/.ssh/config`:

```
host remarkable
  Hostname 10.11.99.1
  User root
  Port 22
  IdentityFile ~/.ssh/id_rsa_remarkable
  BatchMode yes
  ConnectTimeout 2
  PasswordAuthentication no
```

`scripts/rm2ctrl-capture.py` (`--timeout`, integer 1..30, default 5) and `scripts/rm2ctrl-ssh.sh` (`RM_CONNECT_TIMEOUT`) fail fast; the 2 s fail-fast probe needs `--timeout 2` / `RM_CONNECT_TIMEOUT=2` or raw ssh/config.

If you see `no matching host key type … Their offer: ssh-rsa` (OpenSSH ≥ 8.8 vs Dropbear), append:

 ```
   PubkeyAcceptedKeyTypes +ssh-rsa
   HostKeyAlgorithms +ssh-rsa
 ```

Then `ssh remarkable`. Keys live on `/home`, so they survive OS updates (only the root partition is replaced). The host key regenerates on update — delete the stale `known_hosts` entry for the bare IP (`ssh-keygen -R 10.11.99.1`, never `StrictHostKeyChecking=no`), verify the new fingerprint over USB before trusting it over WiFi, and re-accept.

Wrapper gate (`scripts/rm2ctrl-ssh.sh`): dangerous ssh options are rejected (exit 2) unless `--allow-unsafe-ssh-opts` is passed, in which case they pass through with a stderr warning. Denied: `-F -J -L -R -D -W -S -E -A -X -Y -w -I -B` (bundled flags are scanned — e.g. `-AX` is denied) and `-o` values setting `ProxyCommand`, `LocalCommand`, `PermitLocalCommand`, `ForwardAgent`, `LocalForward`, `RemoteForward`, `DynamicForward`, `ProxyJump`, `IdentityAgent`, `PKCS11Provider`, `SecurityKeyProvider`, `ForwardX11`, `ForwardX11Trusted`, `Tunnel`, destination: `Hostname`, `Port` (`-p` stays the sanctioned port flag), verification: `StrictHostKeyChecking`, `UserKnownHostsFile`, `GlobalKnownHostsFile`, `KnownHostsCommand`, multiplex: `ControlMaster`, `ControlPath`, `ControlPersist`, `StreamLocalBindUnlink`, in both `-o Key=Val` and `-oKey=Val` forms; `-o` key matching is case-insensitive. Probe it without a device: `rm2ctrl-ssh.sh --dry-run -o ProxyCommand=evil -- true` (expect exit 2).

Config files still apply: the wrappers pass no `-F`, so `~/.ssh/config` (and `/etc/ssh/ssh_config`) merge into every connection — including directives the CLI gate rejects (`ProxyCommand`, `LocalForward`, …). Pinned CLI flags (`BatchMode`, `ConnectTimeout`, `PasswordAuthentication`, `HostKeyAlgorithms`, `PubkeyAcceptedKeyTypes`) win over config, but `--dry-run` cannot reveal config-smuggled directives — when behavior surprises, audit with `ssh -G <host>` and check `Host *` stanzas first.

## 4. WiFi SSH (secondary)

Same `root` / port 22, but the host is the DHCP address (shown on the GPLv3 page, §2). `remarkable`, `remarkable.local`, `remarkable.lan` may work but are network-dependent — prefer the numeric IP.

On OS > 3.20 WiFi SSH is OFF until enabled over USB SSH (persists across updates):

```sh
ssh -n remarkable 'rm-ssh-over-wlan on'
ssh -n root@<wifi-ip> true
```

## 5. Web UI: enable + endpoints summary

Enable: Menu > Settings > Storage > toggle "USB web interface" ON, then browse `http://10.11.99.1/`. No password over USB by default — treat it as unauthenticated file access: keep USB-only unless you need WiFi, and when bridging (webinterface-wifi) enable its auth/SSL option on trusted networks only. (Full endpoint table: §5 below + [guide](https://remarkable.guide/tech/usb-web-interface.html).)

| Method | Endpoint | Notes |
|---|---|---|
| GET/POST | `/documents/` | root listing |
| GET | `/documents/{guid}` | folder listing |
| GET | `/download/{guid}/pdf` | rendered PDF |
| GET | `/download/{guid}/rmdoc` | raw notebook archive (v3.9+) |
| POST | `/upload` | multipart `file=@…`; needs `Origin: http://10.11.99.1`; lands in last-listed folder — GET target folder first |
| GET | `/thumbnail/{guid}`, `/log.txt` | preview; xochitl log |
| POST | `/search/{keyword}` | experimental |

Community extensions (WiFi exposure, on-boot serve, upload button): [webinterface-wifi](https://github.com/rM-self-serve/webinterface-wifi) and siblings `webinterface-onboot`, `webinterface-upload-button`.

## 6. Pairing avoidance

Do NOT use cloud pairing in the autonomous path: it needs an interactive 8-char one-time code (`my.remarkable.com` → `…/device/desktop/connect`, typed at Menu > General > Account > Setup Account) that exchanges device-then-user tokens (see [api/auth.go](https://github.com/juruen/rmapi/blob/master/api/auth.go)). Also distinct: the on-device lock PIN is unrelated to SSH. Rule: USB SSH + keys; treat Web UI upload as unauthenticated-but-order-dependent (list-then-upload).

## 7. Paper Pro deltas (never mix with rM2 steps)

- Developer Mode is MANDATORY for SSH (Settings > General > Paper Tablet > Software > Advanced > Developer Mode). Enabling forces a factory reset and shows a boot warning. Creds then at Settings > General > Help > About > Copyrights and Licenses. ([guide](https://remarkable.guide/tech/developer-mode.html), [official docs](https://developer.remarkable.com/documentation/developer-mode))
- `rm-ssh-over-wlan on` still required for WiFi SSH.
- rootfs is read-only + OverlayFS on parts of `/etc`: `mount -o remount,rw /` + `umount -R /etc` dance; overlays return after reboot.
- Different CPU arch — rM1/rM2 binaries need recompilation; Toltec unsupported; recovery is official (support Software-recovery article), unlike rM2's pogo-jig recovery ([recovery](https://remarkable.guide/tech/recovery.html)).
