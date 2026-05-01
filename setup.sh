#!/bin/bash
# BlinkySign Raspberry Pi Installer
set -e

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── 1. Must run with sudo ──────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "Run as root:  sudo ./setup.sh"
fi

# Determine the real user (the one who invoked sudo)
CURRENT_USER="${SUDO_USER:-}"
if [[ -z "$CURRENT_USER" ]]; then
    warn "Could not detect the invoking user. Enter the username to install for:"
    read -rp "Username [pi]: " CURRENT_USER
    CURRENT_USER="${CURRENT_USER:-pi}"
fi

echo ""
echo "========================================="
echo "   BlinkySign Raspberry Pi Installer"
echo "========================================="
echo ""

# ── 2. Raspberry Pi detection ──────────────────────────────────────────────────
if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    success "Detected: $PI_MODEL"
else
    warn "This doesn't appear to be a Raspberry Pi."
    read -rp "Continue anyway? [y/N]: " CONTINUE
    [[ "${CONTINUE,,}" == "y" ]] || exit 1
fi

# ── 3. System packages ─────────────────────────────────────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y python3-pip python3-venv python3-lgpio git curl > /dev/null
success "System packages installed."

# ── 4. Enable SPI ─────────────────────────────────────────────────────────────
info "Checking SPI interface..."
if ls /dev/spidev* &>/dev/null; then
    success "SPI is already enabled."
elif command -v raspi-config &>/dev/null; then
    info "Enabling SPI via raspi-config..."
    raspi-config nonint do_spi 0
    success "SPI enabled (takes effect after reboot)."
else
    warn "raspi-config not found. Manually add 'dtoverlay=spi0-1cs' to /boot/firmware/config.txt and reboot."
fi

# ── 5. Virtual environment & dependencies ─────────────────────────────────────
info "Creating Python virtual environment..."
sudo -u "$CURRENT_USER" python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
success "Python dependencies installed."

# ── 6. Certificates ────────────────────────────────────────────────────────────
mkdir -p "$INSTALL_DIR/certs"
if [[ ! -f "$INSTALL_DIR/certs/AmazonRootCA1.pem" ]]; then
    info "Downloading Amazon Root CA certificate..."
    curl -fsSL -o "$INSTALL_DIR/certs/AmazonRootCA1.pem" \
        https://www.amazontrust.com/repository/AmazonRootCA1.pem
    success "Amazon Root CA downloaded."
fi

# ── 7. Interactive .env wizard ─────────────────────────────────────────────────
if [[ -f "$INSTALL_DIR/.env" ]]; then
    warn ".env already exists — skipping configuration wizard."
    warn "Edit $INSTALL_DIR/.env to change settings."
else
    echo ""
    echo "--- LED Configuration ---"
    read -rp "Number of LEDs in your strip [30]: " LED_COUNT
    LED_COUNT="${LED_COUNT:-30}"

    read -rp "LED brightness (0.0 – 1.0) [0.5]: " LED_BRIGHTNESS
    LED_BRIGHTNESS="${LED_BRIGHTNESS:-0.5}"

    echo ""
    echo "--- Server Configuration ---"
    read -rp "Flask server port [5000]: " PORT
    PORT="${PORT:-5000}"

    LOCAL_IP=$(hostname -I | awk '{print $1}')
    read -rp "API endpoint URL [http://${LOCAL_IP}:${PORT}]: " API_ENDPOINT
    API_ENDPOINT="${API_ENDPOINT:-http://${LOCAL_IP}:${PORT}}"

    echo ""
    echo "--- Physical Button (optional) ---"
    read -rp "GPIO pin number for physical button [17]: " BUTTON_PIN
    BUTTON_PIN="${BUTTON_PIN:-17}"

    echo ""
    echo "--- AWS IoT Core (optional — press Enter to skip each field) ---"
    read -rp "AWS Region [us-east-1]: " AWS_REGION
    AWS_REGION="${AWS_REGION:-us-east-1}"
    read -rp "AWS Access Key ID: " AWS_ACCESS_KEY_ID
    read -rsp "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
    echo ""
    read -rp "IoT Endpoint: " IOT_ENDPOINT
    read -rp "IoT Thing Name [blinkysign]: " IOT_THING_NAME
    IOT_THING_NAME="${IOT_THING_NAME:-blinkysign}"

    cat > "$INSTALL_DIR/.env" <<EOF
PORT=${PORT}
LED_COUNT=${LED_COUNT}
LED_BRIGHTNESS=${LED_BRIGHTNESS}
BUTTON_PIN=${BUTTON_PIN}
AWS_REGION=${AWS_REGION}
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
IOT_ENDPOINT=${IOT_ENDPOINT}
IOT_THING_NAME=${IOT_THING_NAME}
API_ENDPOINT=${API_ENDPOINT}
EOF
    chown "$CURRENT_USER:$CURRENT_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    success ".env written."
fi

# ── 8. Install systemd services ────────────────────────────────────────────────
echo ""
info "Installing systemd services..."

install_service() {
    local name="$1"
    local template="$INSTALL_DIR/systemd/${name}"
    local dest="/etc/systemd/system/${name}"
    sed -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
        -e "s|__USER__|${CURRENT_USER}|g" \
        "$template" > "$dest"
    success "Installed ${dest}"
}

install_service blinkysign.service
install_service blinkysign-panel.service

echo ""
read -rp "Install physical button service? [y/N]: " INSTALL_BUTTON
ENABLE_BUTTON=false
if [[ "${INSTALL_BUTTON,,}" == "y" ]]; then
    install_service blinkysign-button.service
    ENABLE_BUTTON=true
fi

ENABLE_IOT=false
IOT_ENDPOINT_VALUE=$(grep "^IOT_ENDPOINT=" "$INSTALL_DIR/.env" | cut -d= -f2-)
if [[ -n "$IOT_ENDPOINT_VALUE" ]]; then
    read -rp "Install AWS IoT client service? [y/N]: " INSTALL_IOT
    if [[ "${INSTALL_IOT,,}" == "y" ]]; then
        install_service blinkysign-iot.service
        ENABLE_IOT=true
    fi
fi

systemctl daemon-reload

systemctl enable blinkysign.service
systemctl enable blinkysign-panel.service
$ENABLE_BUTTON && systemctl enable blinkysign-button.service
$ENABLE_IOT    && systemctl enable blinkysign-iot.service

# ── 9. Fix ownership ───────────────────────────────────────────────────────────
chown -R "$CURRENT_USER:$CURRENT_USER" "$INSTALL_DIR"

# ── 10. Start services now? ────────────────────────────────────────────────────
echo ""
read -rp "Start services now? [Y/n]: " START_NOW
if [[ "${START_NOW,,}" != "n" ]]; then
    systemctl start blinkysign.service
    systemctl start blinkysign-panel.service
    $ENABLE_BUTTON && systemctl start blinkysign-button.service
    $ENABLE_IOT    && systemctl start blinkysign-iot.service
    success "Services started."
fi

# ── 11. Summary ────────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')
FINAL_PORT=$(grep "^PORT=" "$INSTALL_DIR/.env" | cut -d= -f2)
FINAL_PORT="${FINAL_PORT:-5000}"

echo ""
echo "========================================="
echo "   Installation Complete!"
echo "========================================="
echo ""
echo "  API:           http://${LOCAL_IP}:${FINAL_PORT}"
echo "  Control Panel: http://${LOCAL_IP}:8000/control_panel.html"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status blinkysign"
echo "    sudo systemctl restart blinkysign"
echo "    sudo journalctl -u blinkysign -f"
echo ""
if ls /dev/spidev* &>/dev/null; then
    success "SPI is active — LEDs should work immediately."
else
    warn "SPI was just enabled. Reboot to activate it:"
    echo "    sudo reboot"
fi
echo ""
