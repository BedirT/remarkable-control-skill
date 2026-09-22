#!/usr/bin/env bash
# rm2ctrl-ssh.sh — key-based SSH wrapper for reMarkable 2 (USB default).
# Usage: rm2ctrl-ssh.sh [--help] [--dry-run] [--allow-unsafe-ssh-opts] [ssh-options] [--] [remote-command...]
# Env: RM_HOST (default root@10.11.99.1), RM_KEY (default ~/.ssh/id_rsa_remarkable)
# Notes:
#   - No eval. SSH options go before HOST, remote command goes after HOST.
#   - Leading "-p/-o/..." args are treated as ssh options; the rest is the
#     remote command. Use "--" to separate explicitly, e.g.:
#       rm2ctrl-ssh.sh -p 2222 -- true
#       rm2ctrl-ssh.sh -- -h   # remote command starting with a dash
#   - Non-interactive: ssh runs with -n, so the remote command never
#     reads the caller's stdin (a slow pipe cannot hang the wrapper).
set -euo pipefail

# Display hygiene: bash [[:cntrl:]] is ASCII-only under LC_ALL=C, leaving C1
# bytes 80-9F (e.g. CSI c2 9b) printable. Layer an explicit byte strip after
# every display-path class strip below. Builtins only: --help must survive
# PATH= empty, so no tr/sed/command substitution here.
_C1_CTRL=$'\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f'

HOST="${RM_HOST:-root@10.11.99.1}"

usage() {
  HOST_ONLY="${HOST#*@}"
  HOST_ONLY=${HOST_ONLY//[[:cntrl:]]/}
  HOST_ONLY=${HOST_ONLY//[$_C1_CTRL]/}
  # Pure builtins (no cat): --help must work with an empty PATH.
  while IFS= read -r _line; do printf '%s\n' "$_line"; done <<EOF
Usage: rm2ctrl-ssh.sh [OPTIONS] [--] [ssh-options] [remote-command...]

Key-based SSH wrapper for reMarkable 2. Fails fast, never prompts.

Options:
  --help       Show this help and exit (no device needed).
  --dry-run    Print the ssh command that would run, then exit (no device needed).
  --allow-unsafe-ssh-opts
               Allow dangerous ssh options, rejected by default (exit 2):
               -F -J -L -R -D -W -S -E -A -X -Y -w -I -B, and -o values
               setting ProxyCommand, LocalCommand, PermitLocalCommand,
               ForwardAgent, LocalForward, RemoteForward, DynamicForward,
               ProxyJump, IdentityAgent, PKCS11Provider, SecurityKeyProvider,
               ForwardX11, ForwardX11Trusted, Tunnel, Hostname, Port (-p stays
               the sanctioned port flag), StrictHostKeyChecking,
               UserKnownHostsFile, GlobalKnownHostsFile, KnownHostsCommand,
               ControlMaster, ControlPath, ControlPersist,
               StreamLocalBindUnlink (matched
               case-insensitively; both "-o Key=Val" and "-oKey=Val"
               attached forms). With this flag they pass through with a
               stderr warning instead.

Environment:
  RM_HOST      SSH target (default: root@10.11.99.1; WiFi IP also works
               after \`rm-ssh-over-wlan on\` on the tablet, OS > 3.20 only).
  RM_KEY       Identity file (default: ~/.ssh/id_rsa_remarkable; a missing
               default falls back to ssh key discovery, a missing explicit
               RM_KEY is an error).
  RM_CONNECT_TIMEOUT
               ConnectTimeout seconds (default: 5; must be an integer 1..30).
  RM_SSH_MUX   Connection reuse: auto (default) shares one TCP link
               across capture's many small calls; RM_SSH_MUX=0 disables.
  RM_SSH_MUX_DIR
               Control-socket dir (default ~/.ssh/rm2ctrl-mux, mode 0700).
  RM_SSH_PERSIST
               Idle seconds to keep the shared link (default 120).

Notes:
- Newer Dropbear (e.g. 2025.88) offers an ed25519 host key, older ones
  legacy ssh-rsa: passes HostKeyAlgorithms +ssh-rsa /
  PubkeyAcceptedKeyTypes +ssh-rsa as harmless compatibility appends.
  ssh-rsa uses SHA-1 and is legacy; prefer ecdsa where firmware allows.
  - ConnectTimeout (\$RM_CONNECT_TIMEOUT, default 5) + BatchMode=yes:
    no password prompts, fast failure.
  - Non-interactive: stdin is detached (ssh -n), so the remote command
    never reads your terminal input.
  - Single-dash options pass through to ssh: -h shows ssh's help (not
    this help), -v traces, etc. Options end at --: \`rm2ctrl-ssh.sh -- -h\`
    runs -h on the tablet instead.
  - OS updates regenerate the tablet host key: if verification fails,
    remove the stale entry for the bare host (no user@, no suffix),
    e.g. \`ssh-keygen -R "${HOST_ONLY}"\` for the current target, verify the
    new fingerprint over USB before trusting it over WiFi, and retry.
    Never use StrictHostKeyChecking=no to work around this.

Examples:
  rm2ctrl-ssh.sh true
  rm2ctrl-ssh.sh -- systemctl stop xochitl
  rm2ctrl-ssh.sh -p 2222 -- true
  rm2ctrl-ssh.sh -vp 2222 -- true (bundles expand ssh-style: -v -p 2222)
  rm2ctrl-ssh.sh --dry-run -- cat /sys/devices/soc0/machine
EOF
}

DRY_RUN=0
ALLOW_UNSAFE=0
SSH_OPTS=()
CMD=()
SEEN_DASHDASH=0

# Options taking a separate argument (ssh -o option -p port style).
TAKES_ARG=" p o i F l L R D W J b c m O S E e Q w I B "

while [ $# -gt 0 ]; do
  case "$1" in
    --help) usage; exit 0 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --allow-unsafe-ssh-opts) ALLOW_UNSAFE=1; shift ;;
    --)
      SEEN_DASHDASH=1; shift
      while [ $# -gt 0 ]; do CMD+=("$1"); shift; done
      break ;;
    -*)
      if [ "$SEEN_DASHDASH" -eq 1 ]; then
        CMD+=("$1"); shift
      elif [ "${#CMD[@]}" -gt 0 ]; then
        # Already collecting the remote command; keep appending.
        CMD+=("$1"); shift
      else
        # A lone "-" is never a valid ssh option (ssh dies downstream with
        # "hostname contains invalid characters"); reject it here. A "-"
        # after -- or inside the remote command is still passed through.
        if [ "$1" = "-" ]; then
          echo "error: unexpected argument: - (see --help)" >&2
          exit 2
        fi
        opt="$1"; shift
        _stripped="${opt#-}"
        if [[ "$opt" != --* && "$opt" != -o* ]] && [ "${#_stripped}" -gt 1 ]; then
          # Dash bundle (e.g. -vp 2222 means -v -p 2222): expand ssh-style
          # so the gate below sees exact short options. An arg-taking flag
          # consumes the rest of the bundle, else the next argument;
          # otherwise that value would leak into the remote command.
          # Attached -o forms (-oKey=Val) pass through whole; any other
          # =-form also expands (ssh strips a leading '=' from a bundled
          # -o value, so -vo=Key=Val must face the exact -o gate check).
          _rest="$_stripped"
          while [ -n "$_rest" ]; do
            _c="${_rest:0:1}"; _rest="${_rest:1}"
            SSH_OPTS+=("-$_c")
            case "$_c" in
              [a-zA-Z])
                # shellcheck disable=SC2076
                if [[ " $TAKES_ARG " =~ " $_c " ]]; then
                  if [ -n "$_rest" ]; then
                    SSH_OPTS+=("$_rest"); _rest=""
                  else
                    if [ $# -eq 0 ]; then
                    _emsg=${opt//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
                    echo "error: ssh option ${_emsg} needs a value (see --help)" >&2
                      exit 2
                    fi
                    SSH_OPTS+=("$1"); shift
                  fi
                  break
                fi
                ;;
            esac
          done
        else
          # Normalize "--opt=val" and "-oVal" forms are passed through as-is.
          SSH_OPTS+=("$opt")
          # shellcheck disable=SC2076
          if [ -n "$_stripped" ] && { [[ " $TAKES_ARG " =~ " ${_stripped} " ]] || [[ " $TAKES_ARG " =~ " $opt " ]]; }; then
            if [ $# -eq 0 ]; then
            _emsg=${opt//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
            echo "error: ssh option ${_emsg} needs a value (see --help)" >&2
              exit 2
            fi
            SSH_OPTS+=("$1"); shift
          fi
        fi
      fi
      ;;
    *)
      CMD+=("$1"); shift
      # Once the remote command starts (no explicit --), everything
      # remaining is part of it.
      while [ $# -gt 0 ]; do
        if [ "$1" = "--" ]; then
          echo "warning: stray '--' inside remote command; passing through" >&2
        fi
        CMD+=("$1"); shift
      done
      break ;;
  esac
done
if [ -n "${RM_KEY:-}" ]; then
  KEY="$RM_KEY"
  KEY_EXPLICIT=1
elif [ -z "${HOME:-}" ]; then
  echo "error: RM_KEY is not set and HOME is not set; set RM_KEY to your private key path" >&2
  exit 1
else
  KEY="$HOME/.ssh/id_rsa_remarkable"
  KEY_EXPLICIT=0
fi
# tr is load-bearing in validation below (control-character gates, -o
# gate); fail with a clear cause instead of false rejections.
if ! command -v tr >/dev/null 2>&1; then
  echo "error: required command not found in PATH: tr" >&2
  exit 2
fi
# C1-aware control test: [:cntrl:] under LC_ALL=C covers C0 only; the
# explicit 80-9F strip catches C1 bytes (e.g. CSI c2 9b) while leaving
# other high bytes (e.g. c3 a9 for e-acute) intact.
_has_ctrl() { [ "$(printf '%s' "$1" | LC_ALL=C tr -d '[:cntrl:]' | LC_ALL=C tr -d '\200-\237')" != "$1" ]; }

# Basic HOST sanity: reject whitespace / shell metachars that indicate
# injection via RM_HOST env.
# Terminal-escape hygiene: values below are echoed in errors, so reject
# control characters first (all messages after this stay printable).
if _has_ctrl "$HOST"; then
  echo "error: refusing suspicious RM_HOST value (control characters)" >&2
  exit 2
fi
if [[ -z "$HOST" || "$HOST" == *@*@* ]]; then
  echo "error: refusing suspicious RM_HOST value: $HOST" >&2
  exit 2
fi
if [[ "$HOST" =~ [[:space:]] || "$HOST" =~ [\;\&\|\$\`\(\)\<\>] ]]; then
  echo "error: refusing suspicious RM_HOST value: $HOST" >&2
  exit 2
fi
sq="'"; dq='"'
if [[ "$HOST" == *"$sq"* || "$HOST" == *"$dq"* ]]; then
  echo "error: refusing suspicious RM_HOST value: $HOST" >&2
  exit 2
fi
case "$HOST" in
  -*)
    echo "error: RM_HOST must not start with '-' (option injection): $HOST" >&2
    exit 2
    ;;
esac
if _has_ctrl "$KEY"; then
  echo "error: refusing suspicious RM_KEY value (control characters)" >&2
  exit 2
fi
if [[ "$KEY" == *$'\n'* || "$KEY" == *"$sq"* || "$KEY" == *"$dq"* ]]; then
  echo "error: refusing suspicious RM_KEY value (newline/quote)" >&2
  exit 2
fi

# Unsafe ssh options (forwarding, proxy/local command execution, alternate
# config, agent/X11 forwarding) are rejected unless --allow-unsafe-ssh-opts
# was given, in which case they pass through with a stderr warning.
_UNSAFE_LETTERS="FJLRDWSEAXYwIB"
_i=0
while [ "$_i" -lt "${#SSH_OPTS[@]}" ]; do
  _opt="${SSH_OPTS[$_i]}"
  _unsafe=""
  case "$_opt" in
    -o)
      _oval="${SSH_OPTS[$((_i+1))]:-}"
      if _has_ctrl "$_oval"; then
        echo "error: refusing -o value with control characters (see --help)" >&2
        exit 2
      fi
      _olower="$(printf '%s' "$_oval" | tr '[:upper:]' '[:lower:]')"
      _okey="${_olower%%=*}"; _okey="${_okey%% *}"
      if [ -z "$_okey" ]; then
        _unsafe="-o ${_oval}"
      else
      case "$_okey" in
        *proxycommand*|*localcommand*|*permitlocalcommand*|*forwardagent*|*localforward*|*remoteforward*|*dynamicforward*|*proxyjump*|*identityagent*|*pkcs11provider*|*securitykeyprovider*|*forwardx11*|*forwardx11trusted*|*tunnel*|*hostname*|*port*|*stricthostkeychecking*|*userknownhostsfile*|*globalknownhostsfile*|*knownhostscommand*|*controlmaster*|*controlpath*|*controlpersist*|*streamlocalbindunlink*)
          _unsafe="-o ${_oval}"
          ;;
      esac
      fi
      ;;
    -o*)
      _ovalue="${_opt#-o}"
      if _has_ctrl "$_ovalue"; then
        echo "error: refusing -o value with control characters (see --help)" >&2
        exit 2
      fi
      _olower="$(printf '%s' "$_opt" | tr '[:upper:]' '[:lower:]')"
      _okey="${_olower#-o}"; _okey="${_okey%%=*}"
      if [ -z "$_okey" ]; then
        _unsafe="$_opt"
      else
      case "$_okey" in
        *proxycommand*|*localcommand*|*permitlocalcommand*|*forwardagent*|*localforward*|*remoteforward*|*dynamicforward*|*proxyjump*|*identityagent*|*pkcs11provider*|*securitykeyprovider*|*forwardx11*|*forwardx11trusted*|*tunnel*|*hostname*|*port*|*stricthostkeychecking*|*userknownhostsfile*|*globalknownhostsfile*|*knownhostscommand*|*controlmaster*|*controlpath*|*controlpersist*|*streamlocalbindunlink*)
          _unsafe="$_opt"
          ;;
      esac
      fi
      ;;
    --*)
      ;;
    -?*)
      _cluster="${_opt#-}"
      _cluster="${_cluster%%=*}"
      _k=0
      while [ "$_k" -lt "${#_cluster}" ]; do
        _ch="${_cluster:$_k:1}"
        case "$_UNSAFE_LETTERS" in
          *"$_ch"*)
            _unsafe="$_opt"
            break
            ;;
        esac
        _k=$((_k+1))
      done
      if [ -z "$_unsafe" ]; then
        case "$_cluster" in
          *o*)
            _osub="${_cluster#*o}"
            if [ -n "$_osub" ]; then
              if _has_ctrl "$_osub"; then
                echo "error: refusing -o value with control characters (see --help)" >&2
                exit 2
              fi
              _osublower="$(printf '%s' "$_osub" | tr '[:upper:]' '[:lower:]')"
              _osubkey="${_osublower%%=*}"
              if [ -z "$_osubkey" ]; then
                _unsafe="$_opt"
              else
              case "$_osubkey" in
                *proxycommand*|*localcommand*|*permitlocalcommand*|*forwardagent*|*localforward*|*remoteforward*|*dynamicforward*|*proxyjump*|*identityagent*|*pkcs11provider*|*securitykeyprovider*|*forwardx11*|*forwardx11trusted*|*tunnel*|*hostname*|*port*|*stricthostkeychecking*|*userknownhostsfile*|*globalknownhostsfile*|*knownhostscommand*|*controlmaster*|*controlpath*|*controlpersist*|*streamlocalbindunlink*)
                  _unsafe="$_opt"
                  ;;
              esac
              fi
            fi
            ;;
        esac
      fi
      ;;
  esac
  if [ -n "$_unsafe" ]; then
    if [ "$ALLOW_UNSAFE" -eq 1 ]; then
      _emsg=${_unsafe//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
      echo "warning: passing through unsafe ssh option: ${_emsg} (allowed by --allow-unsafe-ssh-opts)" >&2
    else
      _emsg=${_unsafe//[[:cntrl:]]/}; _emsg=${_emsg//[$_C1_CTRL]/}
      echo "error: unsafe ssh option rejected without --allow-unsafe-ssh-opts: ${_emsg} (see --help)" >&2
      exit 2
    fi
  fi
  # Skip the separate value of an option that takes an argument.
  case "$_opt" in
    -?)
      # shellcheck disable=SC2076
      if [[ " $TAKES_ARG " =~ " ${_opt#-} " ]]; then
        _i=$((_i+1))
      fi
      ;;
  esac
  _i=$((_i+1))
done

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

# Identity selection: an explicit RM_KEY that is missing stays a hard
# error (typo protection); a missing *default* file falls back to ssh's
# own key discovery (default identities, agent) with a stderr note.
KEY_ARGS=()
if [ -f "$KEY" ] && [ -r "$KEY" ]; then
  KEY_ARGS=(-i "$KEY")
elif [ "${KEY_EXPLICIT:-0}" -eq 1 ]; then
  echo "error: identity file not readable: $KEY (set RM_KEY)" >&2
  exit 1
else
  echo "note: no key file at $KEY; letting ssh use default identities/agent (set RM_KEY to pin one)" >&2
fi
# Built-in connection reuse. RM_SSH_MUX=0 disables; anything else enables.
# Socket lives in a private dir so concurrent hosts never share it.
MUX_ARGS=()
if [ "${RM_SSH_MUX:-auto}" != "0" ]; then
  _mux_base="${RM_SSH_MUX_DIR:-}"
  if [ -z "$_mux_base" ]; then
    if [ -n "${HOME:-}" ]; then
      _mux_base="$HOME/.ssh/rm2ctrl-mux"
    else
      _mux_base="/tmp/rm2ctrl-mux-$(id -u 2>/dev/null || echo 0)"
    fi
  fi
  if mkdir -p "$_mux_base" 2>/dev/null && chmod 700 "$_mux_base" 2>/dev/null; then
    _persist="${RM_SSH_PERSIST:-120}"
    case "$_persist" in
      ""|*[!0-9]*) _persist=120 ;;
    esac
    MUX_ARGS=(-o ControlMaster=auto -o "ControlPath=$_mux_base/%r@%h:%p" -o "ControlPersist=$_persist")
  fi
fi
SSH_BASE=(ssh -n ${KEY_ARGS[@]+"${KEY_ARGS[@]}"} ${MUX_ARGS[@]+"${MUX_ARGS[@]}"} -o BatchMode=yes -o ConnectTimeout="$CONNECT_TIMEOUT"
  -o ConnectionAttempts=1
  -o PasswordAuthentication=no
  -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedKeyTypes=+ssh-rsa)

if [ "$DRY_RUN" -eq 1 ]; then
  {
    printf '+'
    printf ' %q' "${SSH_BASE[@]}" ${SSH_OPTS[@]+"${SSH_OPTS[@]}"} -- "$HOST" ${CMD[@]+"${CMD[@]}"}
    printf '\n'
  }
  exit 0
fi
if ! command -v ssh >/dev/null 2>&1; then
  echo "error: ssh not found in PATH (install an OpenSSH client)" >&2
  exit 1
fi


exec "${SSH_BASE[@]}" ${SSH_OPTS[@]+"${SSH_OPTS[@]}"} -- "$HOST" ${CMD[@]+"${CMD[@]}"}
