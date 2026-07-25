#!/usr/bin/env bash
#
# BlinkySign installer.
#
#   curl -fsSL https://raw.githubusercontent.com/ttrentler/blinkysign/master/install.sh | bash
#
# Replaces the README's multi-step routine: clone, venv, hand-edit .env, run
# three processes and hand-write two systemd units. Re-running this script is
# also the upgrade path -- every step is idempotent.
#
#   install.sh --uninstall   remove the service, keep the code and .env
#   install.sh --force       run on a non-Raspberry-Pi host anyway
#
set -euo pipefail

REPO_URL="${BLINKYSIGN_REPO:-https://github.com/ttrentler/blinkysign.git}"
BRANCH="${BLINKYSIGN_BRANCH:-master}"
INSTALL_DIR="${BLINKYSIGN_DIR:-$HOME/blinkysign}"
SERVICE_NAME="blinkysign"
# Overridable so the install flow can be exercised without writing to /etc.
UNIT_PATH="${BLINKYSIGN_UNIT_PATH:-/etc/systemd/system/${SERVICE_NAME}.service}"
FORCE=0
REBOOT_REQUIRED=0

log()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m==>\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m==>\033[0m %s\n' "$*" >&2; exit 1; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null 2>&1 || die "sudo is required (or run as root)."
    SUDO="sudo"
fi

# ---------------------------------------------------------------- uninstall

uninstall() {
    log "Stopping and removing the ${SERVICE_NAME} service"
    $SUDO systemctl disable --now "${SERVICE_NAME}.service" 2>/dev/null || true
    $SUDO rm -f "$UNIT_PATH"
    $SUDO systemctl daemon-reload
    log "Service removed. ${INSTALL_DIR} and its .env were left alone."
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --uninstall) uninstall ;;
        --force)     FORCE=1 ;;
        -h|--help)   sed -n '2,14p' "$0"; exit 0 ;;
        *)           die "Unknown option: $arg" ;;
    esac
done

# ------------------------------------------------------------------- checks

[ "$(uname -s)" = "Linux" ] || die "This installer targets Raspberry Pi OS. Use --force to override."

MODEL="unknown"
[ -r /proc/device-tree/model ] && MODEL="$(tr -d '\0' < /proc/device-tree/model)"
case "$MODEL" in
    *"Raspberry Pi"*) log "Detected: $MODEL" ;;
    *)
        if [ "$FORCE" -eq 0 ]; then
            die "This does not look like a Raspberry Pi (model: $MODEL). Use --force to continue."
        fi
        warn "Not a Raspberry Pi (model: $MODEL); continuing because --force was given."
        ;;
esac

command -v systemctl >/dev/null 2>&1 || die "systemd is required."

# --------------------------------------------------------------- system deps

log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get update -qq
# swig, python3-dev and build-essential are needed because lgpio builds from
# source on the Pi -- PyPI does not ship a wheel for every Pi/Python
# combination, and without these the [pi] extra fails on "swig: not found".
$SUDO apt-get install -y -qq \
    git python3-venv python3-pip python3-dev \
    build-essential swig avahi-daemon

# ------------------------------------------------------------------- enable SPI

enable_spi() {
    local config
    for candidate in /boot/firmware/config.txt /boot/config.txt; do
        [ -f "$candidate" ] && { config="$candidate"; break; }
    done
    if [ -z "${config:-}" ]; then
        warn "Could not find config.txt; enable SPI yourself with raspi-config."
        return
    fi

    if grep -qE '^\s*dtparam=spi=on' "$config"; then
        log "SPI already enabled in $config"
        return
    fi

    log "Enabling SPI in $config"
    printf '\n# Added by the BlinkySign installer\ndtparam=spi=on\n' | $SUDO tee -a "$config" >/dev/null
    REBOOT_REQUIRED=1
}

if [ "$FORCE" -eq 0 ] || [ -f /boot/config.txt ] || [ -f /boot/firmware/config.txt ]; then
    enable_spi
fi
[ -e /dev/spidev0.0 ] || REBOOT_REQUIRED=1

# ------------------------------------------------------------------ get code

if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating the existing checkout in $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout --quiet "$BRANCH"
    git -C "$INSTALL_DIR" pull --quiet --ff-only origin "$BRANCH"
elif [ -f "$INSTALL_DIR/pyproject.toml" ]; then
    log "Using the existing source tree in $INSTALL_DIR"
else
    log "Cloning into $INSTALL_DIR"
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# --------------------------------------------------------------- virtualenv

log "Creating the virtual environment and installing BlinkySign"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
# The [pi] extra carries the hardware libraries. If they fail to build, install
# the sign anyway rather than aborting: it comes up on the mock backend, serves
# the panel, and reports "degraded" from /health -- which is a far better
# failure than a half-installed system and a wall of pip output.
HARDWARE_OK=1
if ! ./.venv/bin/pip install --quiet -e '.[pi]' > /tmp/blinkysign-pip.log 2>&1; then
    HARDWARE_OK=0
    warn "The hardware libraries failed to build (see /tmp/blinkysign-pip.log);"
    warn "installing without LED support so the rest of the sign still works."
    ./.venv/bin/pip install --quiet -e .
fi

# --------------------------------------------------------------------- .env

if [ ! -f .env ]; then
    log "Creating .env from .env.example"
    cp .env.example .env
fi
chmod 600 .env

# ------------------------------------------------------------------- groups

for group in spi gpio; do
    if getent group "$group" >/dev/null 2>&1; then
        $SUDO usermod -aG "$group" "$USER" 2>/dev/null || true
    fi
done

# ------------------------------------------------------------------- service

log "Installing the systemd unit"
sed -e "s|@USER@|$USER|g" \
    -e "s|@DIR@|$INSTALL_DIR|g" \
    -e "s|@VENV@|$INSTALL_DIR/.venv|g" \
    systemd/blinkysign.service.in | $SUDO tee "$UNIT_PATH" >/dev/null

$SUDO systemctl daemon-reload
$SUDO systemctl enable --quiet "${SERVICE_NAME}.service"
$SUDO systemctl restart "${SERVICE_NAME}.service"

# -------------------------------------------------------------------- report

PORT="$(grep -E '^\s*(BLINKYSIGN_)?PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
PORT="${PORT:-5000}"
NAME="$(grep -E '^\s*BLINKYSIGN_MDNS_NAME=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
NAME="${NAME:-blinkysign}"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo
log "BlinkySign is installed and running."
echo
echo "    Control panel:  http://${NAME}.local:${PORT}"
[ -n "$IP" ] && \
echo "    Or by address:  http://${IP}:${PORT}"
echo
echo "    Status:   systemctl status ${SERVICE_NAME}"
echo "    Logs:     journalctl -u ${SERVICE_NAME} -f"
echo "    Settings: ${INSTALL_DIR}/.env  (then: systemctl restart ${SERVICE_NAME})"
echo

if [ "$HARDWARE_OK" -eq 0 ]; then
    warn "LED support is NOT installed -- the hardware libraries failed to build."
    warn "The sign is running on its mock backend and /health reports 'degraded'."
    warn "Re-run this script once the build tools are available to fix it."
    echo
fi

if [ "$REBOOT_REQUIRED" -eq 1 ]; then
    warn "A REBOOT IS REQUIRED before the LEDs will light up."
    warn "SPI is not active yet, so the sign is running on its mock backend and"
    warn "/health will report 'degraded'. Run: sudo reboot"
    echo
fi

warn "Your user was added to the 'spi' and 'gpio' groups. The service already"
warn "has them, but your current shell does not until you log out and back in."
