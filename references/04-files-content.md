# Files & content — reMarkable 2

Target: reMarkable 2, OS 3.x. `PAPER-PRO` flags mark known divergences —
never apply rM2 paths/sizes there unverified.

Grounding: rmapi source (`api/auth.go`, `config/url.go`, `archive/doc.go`,
`encoding/rm/rm.go`), rmfakecloud docs, `remarkable.guide` USB/SSH pages,
`lines-are-beautiful` (v3/v5), `rmscene`/`rmc` (v6).

## 1. On-device xochitl store

Root: `/home/root/.local/share/remarkable/xochitl/` — one UUID per
document / notebook / folder. Sidecars per UUID:

| Path | Format | Key fields |
|---|---|---|
| `<uuid>.metadata` | JSON | `visibleName`, `type` (DocumentType/CollectionType), `parent`, `pinned`, `lastModified`, `synced`, `version` |
| `<uuid>.content` | JSON | page count, `pages` UUID list, `coverPageNumber`, `fileType` (pdf/epub/notebook), `cpalette`; PDFs/ePubs also reference the source file |
| `<uuid>.pagedata` | blank-line-separated text | per-page template name, e.g. `Blank` |
| `<uuid>/N.rm` | ink binary (§6) | per-page strokes, N = page index |
| `<uuid>.thumbnails/N.jpg` | JPEG | per-page thumbnail |
| `<uuid>/N-metadata.json` | JSON (newer fw) | layer/text metadata |
| `<uuid>.pdf` / `<uuid>.epub` | source file | only for PDF/ePub documents |

`PAPER-PRO`: color templates + larger canvas; Toltec does NOT support
Paper Pro.

## 2. Deterministic ssh+rsync recipe (preferred for autonomy)

Always stop xochitl before writing the tree; restart after. Transport:
`root@10.11.99.1` over USB (key auth — see `scripts/rm-ssh.sh`).

```sh
ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa root@10.11.99.1 "systemctl stop xochitl"
rsync -avz -e "ssh -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa" root@10.11.99.1:/home/root/.local/share/remarkable/xochitl/ ./backup/xochitl/
# ... modify local copy ...
rsync -avz -e "ssh -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa" ./backup/xochitl/ root@10.11.99.1:/home/root/.local/share/remarkable/xochitl/
ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa root@10.11.99.1 "systemctl start xochitl"
```

Template install (custom PNG + registry + restart):

```sh
# PNG MUST be 1404x1872 (rM2); PAPER-PRO: different canvas, re-check size
rsync -avz -e "ssh -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa" ./templates/ root@10.11.99.1:/usr/share/remarkable/templates/
ssh -n -o BatchMode=yes -o ConnectTimeout=5 -o PasswordAuthentication=no -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa root@10.11.99.1 "systemctl restart xochitl"
```

Templates live at `/usr/share/remarkable/templates/`: `*.png`
(1404×1872, cf. `Width=1404 Height=1872` in rmapi `encoding/rm/rm.go`)
+ `templates.json` registry. Custom template = scp PNG + append JSON
entry + `systemctl restart xochitl`. `.pagedata` maps pages → names.

Debug sync issues: `systemctl stop xochitl` first, then `QT_LOGGING_RULES=rm.network.*=true xochitl` in the foreground (never two instances at once); `systemctl start xochitl` after.

## 3. USB web UI — curl table (zero-prompt path)

Enable: Settings > Storage > USB web interface ON, browse
`http://10.11.99.1/`. No auth by default over USB. Community extensions:
`webinterface-onboot`, `webinterface-wifi` (adds auth/SSL over WiFi),
`webinterface-upload-button`.

| Action | Request |
|---|---|
| List root folder | `curl -s http://10.11.99.1/documents/` |
| List folder | `curl -s http://10.11.99.1/documents/{guid}` (GET or POST); JSON: `ID`, `VissibleName` [sic], `Type` |
| Download PDF render | `curl -O "http://10.11.99.1/download/{guid}/pdf"` |
| Download raw notebook | `curl -O "http://10.11.99.1/download/{guid}/rmdoc"` (fw ≥ 3.9) |
| Upload PDF/ePub | `curl http://10.11.99.1/upload -H 'Origin: http://10.11.99.1' -F "file=@book.pdf;type=application/pdf"` — lands in the LAST-LISTED folder, so GET the target folder first |
| Thumbnail | `curl -s "http://10.11.99.1/thumbnail/{guid}" -o thumb.jpg` |
| xochitl log | `curl -s http://10.11.99.1/log.txt` (= `/home/root/log.txt`) |
| Search (beta) | `curl -s -X POST http://10.11.99.1/search/{keyword}` |

Validate before interpolating: `{guid}` must match `^[0-9a-fA-F-]{36}$`;
URL-encode `{keyword}` (or use `curl --get --data-urlencode`); save with
`curl -o <local-chosen-name>` instead of `-O` (remote-controlled
filenames); never paste device output (GUIDs, visibleName) unquoted into
a shell command.

Upload accepts PDF and ePub only — no native PNG-ingest as a document
(PNGs are templates or annotation renders).

## 4. rmapi — UNMAINTAINED, archiving soon

Repo: https://github.com/juruen/rmapi — README banner says effectively
unmaintained, to be archived (see discussion #313). Experimental
new-sync-protocol support: `get` works, `put` flaky for migrated
accounts. Back up first; prefer §2/§3 for autonomy.

Install: `go install` from source, release binaries, or docker
(`-v $HOME/.config/rmapi:/home/app/.config/rmapi`).

Auth (one-time, interactive — avoid in autonomous flows): 8-char code
from https://my.remarkable.com/device/desktop/connect →
`POST {authHost}/token/json/2/device/new` (device token) →
`POST {authHost}/token/json/2/user/new` (user token); tokens cached in
`~/.config/rmapi`. Env overrides: `RMAPI_HOST`, `RMAPI_AUTH`,
`RMAPI_DOC` (point at rmfakecloud for local testing).

```sh
rmapi ls                  # list current dir
rmapi get DocName         # download
rmapi mget .              # download everything
rmapi put book.pdf /books # upload (flaky on new sync — verify)
rmapi mput /Papers        # upload dir
rmapi geta DocName        # PDF + annotations
rmapi mkdir /books; rmapi mv Old New; rmapi rm /Stale
rmapi account; rmapi refresh; rmapi version
```

## 5. rclone verdict + WebDAV bridge

There is NO rclone reMarkable backend (verified: `rclone.org/remarkable/`
→ 404; no entry in the ~70-backend table at `rclone.org/overview/`).
Do NOT promise `rclone lsd remarkable:`.

Bridge pattern: rmfakecloud exposes WebDAV (`/usage/integrations/`) and
FTP — both ARE rclone backends:

```sh
rclone sync ./docs webdav-remarkable:/
```

Or pair `rmapi mget/mput` with `rclone sync` to S3/Drive.

## 6. rmfakecloud setup note (self-hosted sync)

Repo: https://github.com/ddvk/rmfakecloud (AGPL-3.0), MAINTAINED
(sync tested to SW 3.27.1; supports RM1 + RM2 + Paper Pro/Move/Pure).
Parity: file sync v1.0/1.5/2/3/4 ✅, email-send ✅, HWR ✅,
screen share ✅, WebDAV/FTP ✅, calendar ICS ✅, webhook ✅,
PIN reset (RM1/2) ✅; handwriting search ❌, doc preview ❌ (WIP #255),
Dropbox/GDrive 🟡 WIP, OneDrive ❌.

Device hookup: Toltec `opkg install rmfakecloud-proxy` (Toltec: OS <= 3.3.2);
`rmfakecloudctl set-upstream <URL>; rmfakecloudctl enable`, or scp
`installer-rm12.sh` / `installer-rmpro.sh` and run on device
(`PAPER-PRO`: `mount -o remount,rw /; umount -R /etc` first), or manual
CA (`*.appspot.com`) + `/etc/hosts` entries + reverse proxy.
OS updates wipe the proxy/hosts — re-enable after every update.
Tablet flow: Menu > General > Account > Setup Account, local Web UI >
Code > Generate Code, enter on tablet, Menu > Storage > Check Sync.

## 7. Ink `.rm` versions + parsers

| Version | Model | Parser |
|---|---|---|
| v3 / v5 | flat stroke/line lists | `lines-are-beautiful` (C++, STALE — v3/v5 era; good format reference + `lines2png`/`lines2svg`; pressure/tilt texture unimplemented) |
| v6 | scene tree + text (CRDT) | `rmscene` (Py, MAINTAINED v0.8.0) — parse v6 scene trees + text; `rmc` (Py, MAINTAINED) — v6 rm→svg/pdf/md + md→rm |

Export paths: USB `/download/{guid}/pdf` (§3), `rmapi geta` (basic, one
pen type), `rmscene`/`rmc` SVG/PDF (text-box multibyte positioning
caveats). PDF annotation path: original PDF untouched, strokes overlaid;
ePub converts to PDF internally — reformat regenerates the PDF and
orphans strokes (stock warning).

## 8. Sources

- https://github.com/juruen/rmapi
- https://github.com/ddvk/rmfakecloud (+ https://ddvk.github.io/rmfakecloud/)
- https://github.com/ddvk/rmfakecloud-proxy
- https://remarkable.guide/tech/usb-web-interface.html
- https://remarkable.guide/guide/access/ssh.html
- https://github.com/ax3l/lines-are-beautiful
- https://github.com/ricklupton/rmscene + https://github.com/ricklupton/rmc
- https://toltec-dev.org/
- https://github.com/splitbrain/ReMarkableAPI
- https://github.com/reHackable/awesome-reMarkable
