# Quran Karim Radio Station

A lightweight Linux system tray app for PopOS (GNOME) that streams two
Quran radio stations directly from the top panel bar.

![Tray menu](screenshots/tray-menu.png)

## Features

- Sits in the GNOME top panel via AppIndicator3
- Two stations: Beirut and Cairo (ERTU 98.2 FM)
- Play / Stop toggle
- Volume slider (0–100 %)
- Live status: Stopped / Buffering… / Playing / Error
- Remembers last selected station and volume across sessions
- Auto-verifies the Cairo stream URL at startup and falls back if unreachable
- Graceful 8-second connection timeout with error message

## Install

### Flatpak (recommended)

Once approved on Flathub:

```bash
flatpak install flathub io.github.AhmadTakkoush.QuranRadio
```

### Quick Install (native)

```bash
chmod +x install.sh
./install.sh
```

`install.sh` will:
1. Install all apt dependencies
2. Copy the app to `/opt/quran-radio/`
3. Register `~/.config/autostart/quran-radio.desktop` so the app starts on login
4. Create a `/usr/local/bin/quran-radio` launcher

### Manual Install

#### 1. Install dependencies

```bash
sudo apt install python3-gi python3-gi-cairo \
     gir1.2-gtk-3.0 gir1.2-appindicator3-0.1 \
     gir1.2-gst-plugins-base-1.0 \
     gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
     gstreamer1.0-libav
```

#### 2. Run

```bash
python3 quran_radio.py
```

#### 3. Autostart on login (optional)

```bash
mkdir -p ~/.config/autostart
cp quran_radio.desktop ~/.config/autostart/
# Edit the Exec= path inside to point to wherever quran_radio.py lives
```

## Radio Stations

| Station | URL |
|---------|-----|
| Quran Kareem — Beirut | `https://audio.osina.cloud:7987/stream` |
| Quran Kareem — Cairo (ERTU 98.2 FM) | `https://n06.radiojar.com/8s5u5tpdtwzuv` |

## Uninstall

```bash
sudo rm -rf /opt/quran-radio /usr/local/bin/quran-radio
rm ~/.config/autostart/quran-radio.desktop
```
