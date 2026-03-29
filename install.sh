#!/usr/bin/env bash
# install.sh — Install Quran Radio system tray app on PopOS / Ubuntu 22.04+
set -euo pipefail

APP_DIR="/opt/quran-radio"
AUTOSTART_DIR="$HOME/.config/autostart"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing system dependencies…"
sudo apt install -y \
    python3-gi \
    python3-gi-cairo \
    python3-pil \
    gir1.2-gtk-3.0 \
    gir1.2-appindicator3-0.1 \
    gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav

echo "==> Copying app files to $APP_DIR…"
sudo mkdir -p "$APP_DIR"
sudo cp "$SCRIPT_DIR/quran_radio.py"   "$APP_DIR/"
sudo cp "$SCRIPT_DIR/create_icon.py"   "$APP_DIR/"

echo "==> Generating icon…"
python3 "$SCRIPT_DIR/create_icon.py"
sudo cp "$SCRIPT_DIR/icon.png" "$APP_DIR/"

echo "==> Setting up autostart…"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/quran-radio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Quran Radio
Comment=Quran Karim Radio Station tray app
Exec=python3 $APP_DIR/quran_radio.py
Icon=$APP_DIR/icon.png
Terminal=false
Categories=Audio;Player;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

echo "==> Creating launcher shortcut at /usr/local/bin/quran-radio…"
sudo tee /usr/local/bin/quran-radio > /dev/null <<EOF
#!/bin/bash
exec python3 $APP_DIR/quran_radio.py "\$@"
EOF
sudo chmod +x /usr/local/bin/quran-radio

echo ""
echo "✓ Installation complete."
echo "  • Run now:        quran-radio"
echo "  • Starts on login automatically via ~/.config/autostart/"
echo "  • To uninstall:   sudo rm -rf $APP_DIR /usr/local/bin/quran-radio"
echo "                    rm ~/.config/autostart/quran-radio.desktop"
