#!/usr/bin/env bash
# rm-screenshot.sh — single-shot framebuffer capture from reMarkable 2.
# Probes /dev/shm/swtfb.01 first (fast shared-mem path), falls back to /dev/fb0,
# then converts raw rgb565le 1404x1872 to PNG with ffmpeg.
# Usage: rm-screenshot.sh [--help] [--dry-run] [--force] [--out FILE] [--host HOST] [--key PATH]
set -euo pipefail

# Display hygiene: bash [[:cntrl:]] is ASCII-only under LC_ALL=C, leaving C1
# bytes 80-9F (e.g. CSI c2 9b) printable. Layer an explicit byte strip after
# every display-path class strip below. Builtins only: --help must survive
# PATH= empty, so no tr/sed/command substitution here.
_C1_CTRL=$'\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'

DEFAULT_HOST="${RM_HOST:-root@10.11.99.1}"
if [ -n "${RM_KEY:-}" ]; then
  DEFAULT_KEY="$RM_KEY"
elif [ -n "${HOME:-}" ]; then
  DEFAULT_KEY="${HOME:-}/.ssh/id_rsa_remarkable"
else
  DEFAULT_KEY=""
fi

OUT="screenshot.png"
HOST="$DEFAULT_HOST"
KEY="$DEFAULT_KEY"
DRY_RUN=0
FORCE=0
TMP_PUB=""
OUT_PUB_DIR=""

usage() {
  # Pure builtins (no cat): --help must work with an empty PATH.
  _show_host=${DEFAULT_HOST//[[:cntrl:]]/}; _show_host=${_show_host//[$_C1_CTRL]/}
  _show_key=${DEFAULT_KEY//[[:cntrl:]]/}; _show_key=${_show_key//[$_C1_CTRL]/}
  while IFS= read -r _line; do printf '%s\n' "$_line"; done <<EOF
Usage: rm-screenshot.sh [OPTIONS]

Single-shot screenshot from reMarkable 2 over SSH. Read-only (no e-ink writes).

Options:
  --help        Show this help and exit (no device needed).
  --dry-run     Print the probe/convert steps without touching device or ffmpeg.
  --out FILE    Output PNG path (default: screenshot.png; must not start with -,
                must not contain control characters, must be absent or a
                regular file, and must not be the --key file).
  --host HOST   SSH target (default: ${_show_host}, from \$RM_HOST).
  --key PATH    Identity file (default: ${_show_key}, from \$RM_KEY;
                must be a readable regular file).
  --force       Overwrite --out if it exists. Default refuses to clobber
                (ffmpeg -n); with --force ffmpeg runs with -y.
  --            End of options (nothing may follow: anything after --
                is rejected with exit 2).

Environment:
  RM_CONNECT_TIMEOUT
                ssh ConnectTimeout seconds (default: 5; integer 1..30).

Expects full 16-bit frame: 1404*1872*2 = 5256576 bytes. Size mismatch
means the firmware serves another layout (see references/02-display-
screenshot.md pix_fmt matrix: :mem: gray8/gray16be/bgra, skips
8/2629636/4705256) — use the matrix or reStream/ScreenShare instead.
NOTE: output is rotated by transpose=1, so the PNG is 1872x1404
landscape bytes for the 1404x1872 portrait panel.

One SSH connection per capture. Concurrent runs are safe (mktemp frame).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --help) usage; exit 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --out|--host|--key)
      if [ $# -lt 2 ]; then echo "error: $1 needs a value (see --help)" >&2; exit 2; fi
      case "$1" in
        --out) OUT="$2" ;;
        --host) HOST="$2" ;;
        --key) KEY="$2" ;;
      esac
      shift 2 ;;
    --)
      shift
      if [ $# -gt 0 ]; then
        _emsg=${*//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
        echo "error: unexpected argument(s) after --: ${_emsg}" >&2
        exit 2
      fi
      break ;;
    -*)
      _emsg=${1//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
      echo "error: unknown flag: ${_emsg} (see --help)" >&2; exit 2 ;;
    *)
      _emsg=${1//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
      echo "error: unknown argument: ${_emsg} (see --help)" >&2; exit 2 ;;
  esac
done
# tr is load-bearing in validation below (control-character gates); fail
# with a clear cause instead of false rejections.
if ! command -v tr >/dev/null 2>&1; then
  echo "error: required command not found in PATH: tr" >&2
  exit 2
fi
# C1-aware control test: [:cntrl:] under LC_ALL=C covers C0 only; the
# explicit 80-9F strip catches C1 bytes (e.g. CSI c2 9b) while leaving
# other high bytes (e.g. c3 a9 for e-acute) intact.
_has_ctrl() { [ "$(printf '%s' "$1" | LC_ALL=C tr -d '[:cntrl:]' | LC_ALL=C tr -d '\200-\237')" != "$1" ]; }

# Terminal-escape hygiene: OUT/HOST/KEY are echoed in errors below, so
# reject control characters first (all messages after this stay printable).
if _has_ctrl "$OUT"; then
  echo "error: --out must not contain control characters (see --help)" >&2
  exit 2
fi
# Reject option-injection / hostile paths before touching ssh or ffmpeg.
case "$OUT" in
  -*)
    echo "error: --out must not start with '-' (option injection): $OUT" >&2
    exit 2
    ;;
  "")
    echo "error: --out must not be empty" >&2
    exit 2
    ;;
esac
if [[ "$OUT" == *$'\n'* ]]; then
  echo "error: --out must not contain a newline (see --help)" >&2
  exit 2
fi
if [ -L "$OUT" ]; then
  echo "error: --out must not be a symlink (refusing to write through link): $OUT" >&2
  exit 2
fi
if [ -e "$OUT" ] && [ ! -f "$OUT" ]; then
  echo "error: --out exists and is not a regular file (see --help): $OUT" >&2
  exit 1
fi

if _has_ctrl "$HOST"; then
  echo "error: refusing suspicious --host value (control characters)" >&2
  exit 2
fi
if [[ -z "$HOST" || "$HOST" == *@*@* ]]; then
  echo "error: refusing suspicious --host value: $HOST" >&2
  exit 2
fi
if [[ "$HOST" =~ [[:space:]] || "$HOST" =~ [\;\&\|\$\`\(\)\<\>] ]]; then
  echo "error: refusing suspicious --host value: $HOST" >&2
  exit 2
fi
sq="'"; dq='"'
if [[ "$HOST" == *"$sq"* || "$HOST" == *"$dq"* ]]; then
  echo "error: refusing suspicious --host value: $HOST" >&2
  exit 2
fi
case "$HOST" in
  -*)
    echo "error: --host/HOST must not start with '-' (option injection): $HOST" >&2
    exit 2
    ;;
esac

if [ -z "$KEY" ]; then
  echo "error: --key must not be empty (see --help)" >&2
  exit 2
fi
if _has_ctrl "$KEY"; then
  echo "error: refusing suspicious --key value (control characters)" >&2
  exit 2
fi
if [[ "$KEY" == *$'\n'* || "$KEY" == *"$sq"* || "$KEY" == *"$dq"* ]]; then
  echo "error: refusing suspicious --key value (newline/quote)" >&2
  exit 2
fi

CONNECT_TIMEOUT="${RM_CONNECT_TIMEOUT:-5}"
if _has_ctrl "$CONNECT_TIMEOUT"; then
  echo "error: RM_CONNECT_TIMEOUT must be an integer 1..30 (control characters rejected)" >&2
  exit 2
fi
if [[ ! "$CONNECT_TIMEOUT" =~ ^[0-9]+$ ]]; then
  echo "error: RM_CONNECT_TIMEOUT must be an integer 1..30 (got: $CONNECT_TIMEOUT)" >&2
  exit 2
fi
_t="$CONNECT_TIMEOUT"
while true; do case "$_t" in 0?*) _t="${_t#0}" ;; *) break ;; esac; done
case "$_t" in
  [1-9]|[12][0-9]|30) ;;
  *) echo "error: RM_CONNECT_TIMEOUT must be an integer 1..30 (got: $CONNECT_TIMEOUT)" >&2; exit 2 ;;
esac

SSH_BASE=(ssh -n -i "$KEY" -o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT"
  -o PasswordAuthentication=no -o ServerAliveInterval=10 -o ServerAliveCountMax=3
  -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa)
FFMPEG_CLOBBER=(-n)
if [ "$FORCE" -eq 1 ]; then FFMPEG_CLOBBER=(-y); fi
REMOTE_SCRIPT='if [ -f /dev/shm/swtfb.01 ]; then echo "source: /dev/shm/swtfb.01" >&2; cat /dev/shm/swtfb.01; elif [ -e /dev/fb0 ]; then echo "source: /dev/fb0" >&2; dd if=/dev/fb0 bs=5256576 count=1 2>/dev/null; else echo "no framebuffer node (no /dev/shm/swtfb.01, no /dev/fb0)" >&2; exit 3; fi'

if [ "$FORCE" -eq 0 ] && [ "$DRY_RUN" -eq 0 ] && [ -e "$OUT" ]; then
  echo "error: refusing to overwrite existing output without --force: $OUT" >&2
  exit 1
fi

# Never plan a capture that would overwrite the identity file: mirror the
# live OUT==KEY refusal before the dry-run plan (an OUT==KEY plan can never succeed).
if [ "$OUT" -ef "$KEY" ]; then
  echo "error: --out and --key are the same file (refusing to overwrite key): $OUT" >&2
  exit 2
fi

if [ "$DRY_RUN" -eq 1 ]; then
  {
    printf '+'
    printf ' %q' "${SSH_BASE[@]}" -- "$HOST" "$REMOTE_SCRIPT"
    printf ' > %q\n' "<tmp>.raw"
  }
  echo '+ test "$(wc -c < "<tmp>.raw")" -eq 5256576  # full 1404x1872 rgb565le frame'
  {
    printf '+ ffmpeg -hide_banner -loglevel error'
    printf ' %q' "${FFMPEG_CLOBBER[@]}"
    printf ' -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 -i %q' "<tmp>.raw"
    printf ' -vf %q -- %q\n' "transpose=1" "<tmp>.png"
    if [ "$FORCE" -eq 1 ]; then printf '+ mv -f -- %q %q\n' "<tmp>.png" "$OUT"; else printf '+ ln -- %q %q\n' "<tmp>.png" "$OUT"; fi
  }
  exit 0
fi

if [ ! -f "$KEY" ] || [ ! -r "$KEY" ]; then
  echo "error: identity file not readable: $KEY (set RM_KEY or pass --key)" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "error: ffmpeg not found in PATH (install ffmpeg to convert frames)" >&2
  exit 1
fi
if ! command -v ssh >/dev/null 2>&1; then
  echo "error: ssh not found in PATH (install an OpenSSH client)" >&2
  exit 1
fi
OUT_DIR="$(dirname "$OUT")"
if [ ! -d "$OUT_DIR" ] || [ ! -w "$OUT_DIR" ]; then
  echo "error: output directory not writable: $OUT_DIR" >&2
  exit 1
fi

# Never let the capture overwrite the identity file, even with --force:
# OUT==KEY (any spelling: hardlink, ./d/../k) would replace the only key
# copy with a PNG. -ef compares inodes, so dodges fail closed too.
if [ "$OUT" -ef "$KEY" ]; then
  echo "error: --out and --key are the same file (refusing to overwrite key): $OUT" >&2
  exit 2
fi

if ! TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/rm-shot-XXXXXX" 2>/dev/null)"; then
  echo "error: cannot create temporary directory (check TMPDIR)" >&2
  exit 1
fi
# Publish staging inside OUT's directory (same filesystem, so the final
# link(2) claim below is atomic). Template X's must TRAIL: BSD mktemp
# silently keeps a non-trailing template literally, which would share one
# path between concurrent runs. Fresh dir per run => unique names, and
# ffmpeg -n still writes a never-before-existing file.
if ! OUT_PUB_DIR="$(mktemp -d "$OUT_DIR/.rm-shot-XXXXXX" 2>/dev/null)"; then
  echo "error: cannot create publish staging in $OUT_DIR (check permissions)" >&2
  exit 1
fi
TMP_PUB="$OUT_PUB_DIR/out.png"
TMP_RAW="$TMP_DIR/fb.raw"
cleanup() { rm -rf "$TMP_DIR" "$OUT_PUB_DIR"; rm -f "$TMP_PUB"; }
trap cleanup EXIT

CHILD=""
_sig_int() { if [ -n "${CHILD:-}" ]; then kill -TERM "$CHILD" 2>/dev/null || true; wait "$CHILD" 2>/dev/null || true; fi; exit 130; }
_sig_term() { if [ -n "${CHILD:-}" ]; then kill -TERM "$CHILD" 2>/dev/null || true; wait "$CHILD" 2>/dev/null || true; fi; exit 143; }
trap _sig_int INT
trap _sig_term TERM

SSH_RC=0
"${SSH_BASE[@]}" -- "$HOST" "$REMOTE_SCRIPT" > "$TMP_RAW" & CHILD=$!; wait "$CHILD" || SSH_RC=$?
CHILD=""
if [ "$SSH_RC" -eq 3 ]; then
  echo "error: no framebuffer node on $HOST (no /dev/shm/swtfb.01, no /dev/fb0); firmware may serve another layout" >&2
  echo "see references/02-display-screenshot.md pix_fmt matrix (:mem: gray8/gray16be/bgra), or use reStream/ScreenShare" >&2
  exit 1
elif [ "$SSH_RC" -ne 0 ]; then
  echo "error: ssh failed (rc=$SSH_RC) for $HOST; check network, key auth, and host key" >&2
  exit 1
fi

SIZE="$(wc -c < "$TMP_RAW" | tr -d ' ')"
if [ "$SIZE" -ne 5256576 ]; then
  echo "error: unexpected frame size $SIZE (want 5256576); firmware may serve :mem: gray8/gray16be/bgra layouts" >&2
  echo "see references/02-display-screenshot.md pix_fmt matrix, or use reStream/ScreenShare" >&2
  exit 1
fi

FFMPEG_RC=0
ffmpeg -hide_banner -loglevel error "${FFMPEG_CLOBBER[@]}" \
  -vcodec rawvideo -f rawvideo -pix_fmt rgb565le -s 1404x1872 -i "$TMP_RAW" \
  -vf "transpose=1" -- "$TMP_PUB" & CHILD=$!; wait "$CHILD" || FFMPEG_RC=$?
CHILD=""
if [ "$FFMPEG_RC" -ne 0 ]; then
  echo "error: ffmpeg failed (rc=$FFMPEG_RC) converting 1404x1872 rgb565le frame; check ffmpeg install and disk space" >&2
  exit 1
fi
# Publish: OUT appears only when complete (no partials on kill).
# Without --force the claim is one atomic link(2): it fails EEXIST if OUT
# appeared concurrently, so same-path racers cannot both succeed — exactly
# one wins, losers exit 1 below. rename(2) replaces rather than follows a
# swapped-in link. --force keeps last-writer-wins.
if [ -L "$OUT" ]; then
  echo "error: --out became a symlink during capture (refusing to write through link): $OUT" >&2
  exit 1
fi
if [ "$OUT" -ef "$KEY" ]; then
  echo "error: --out became the same file as --key during capture (refusing to overwrite key): $OUT" >&2
  exit 1
fi
if [ "$FORCE" -eq 0 ] && [ -e "$OUT" ]; then
  echo "error: refusing to overwrite existing output without --force: $OUT" >&2
  exit 1
fi
if [ -e "$OUT" ] && [ ! -f "$OUT" ]; then
  echo "error: --out exists and is not a regular file (see --help): $OUT" >&2
  exit 1
fi
if [ "$FORCE" -eq 1 ]; then
  if ! MV_ERR="$(mv -f -- "$TMP_PUB" "$OUT" 2>&1)"; then
    echo "error: cannot publish capture to $OUT${MV_ERR:+ ($MV_ERR)}" >&2
    exit 1
  fi
else
  if ! LN_ERR="$(ln -- "$TMP_PUB" "$OUT" 2>&1)"; then
    if [ -e "$OUT" ]; then
      echo "error: refusing to overwrite $OUT (appeared during capture; use --force to clobber)" >&2
    else
      echo "error: cannot publish capture to $OUT${LN_ERR:+ ($LN_ERR)}" >&2
    fi
    exit 1
  fi
  rm -f -- "$TMP_PUB"
fi
echo "wrote $OUT" >&2
