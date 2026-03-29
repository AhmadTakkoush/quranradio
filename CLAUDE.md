# Quran Radio — PopOS System Tray App

## Project Overview
A Linux system tray application for PopOS (GNOME-based) written in Python.
It sits in the top panel bar. Clicking the icon opens a small dropdown window
with two radio station options and play/stop controls.

## Tech Stack
- **Language:** Python 3
- **UI Framework:** GTK3 via PyGObject (`gi.repository`)
- **System Tray:** `AppIndicator3` (libappindicator3) for GNOME/PopOS top bar
- **Audio Playback:** GStreamer via `gi.repository.Gst` (no extra media player dependency)
- **Build/Run:** Single Python script, launched at login via `.desktop` autostart

## Radio Stations

| Station | URL |
|---|---|
| Quran Kareem — Beirut | `https://audio.osina.cloud:7987/stream` |
| Quran Kareem — Cairo (ERTU 98.2 FM) | `http://stream.radiojar.com/quraneg` |

> **Note:** If the Cairo stream URL is unreachable, try these fallbacks in order:
> 1. `https://zeno.fm/radio/egypt-quran-radio/` (Zeno.FM — may require HLS handling)
> 2. `http://maspero.eg` live page source extraction
> Always verify the Cairo URL is alive before hardcoding it. Use `urllib` or `requests` to HEAD-check at startup.

## App Behavior

1. **Tray icon** appears in the PopOS top bar (GNOME Shell panel)
2. **Left-click** opens a small GTK Popover/Window anchored below the icon
3. **Dropdown window** contains:
   - App title: "Quran Radio 📻"
   - Two radio buttons (GtkRadioButton): one per station
   - A Play / Stop toggle button
   - A volume slider (GtkScale, 0–100)
   - Status label: "Stopped", "Buffering…", "Playing"
4. **Only one stream plays at a time.** Switching stations while playing stops the
   current stream and starts the new one automatically.
5. **Remember last selected station** using a simple JSON config file at
   `~/.config/quran-radio/config.json`
6. **Graceful fallback:** If a stream fails to connect within 8 seconds, show an
   error label and reset to Stopped state.

## File Structure
```
quran-radio/
├── quran_radio.py        # Main application entry point
├── quran_radio.desktop   # Autostart .desktop file
├── icon.png              # Tray icon (crescent moon or Quran symbol, 64x64 PNG)
├── requirements.txt      # Python deps (if any pip packages used)
├── install.sh            # Install script (copies .desktop, icon, sets up autostart)
└── README.md
```

## Installation Requirements (document in README and install.sh)
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
     gir1.2-appindicator3-0.1 gir1.2-gst-plugins-base-1.0 \
     gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
     gstreamer1.0-libav
```

## Key Implementation Notes

- Use `AppIndicator3.Indicator` for the tray icon — **not** `Gtk.StatusIcon`
  (deprecated in GNOME). Category: `AppIndicator3.IndicatorCategory.APPLICATION_STATUS`.
- Use `GStreamer` (`Gst.ElementFactory.make("playbin", "player")`) for audio.
  Set the URI property of playbin to the stream URL. Call `player.set_state(Gst.State.PLAYING)`
  to play and `Gst.State.NULL` to stop.
- The dropdown window should be a `Gtk.Window` with `type_hint = Gdk.WindowTypeHint.POPUP_MENU`
  and `skip_taskbar_hint = True` so it doesn't appear in the taskbar.
- Position the window near the top of the screen (use `Gtk.Window.move()` or attach
  it to the indicator via a menu if popover approach is complex).
- Volume control: use GStreamer's `playbin.set_property("volume", value)` where value
  is 0.0–1.0.
- Monitor GStreamer bus messages for `GST_MESSAGE_ERROR` and `GST_MESSAGE_BUFFERING`
  to update the status label.
- The `.desktop` autostart file goes in `~/.config/autostart/quran-radio.desktop`.

## Tone & Style
- Keep the UI minimal and clean — Islamic green accent color (#1B6B3A) or neutral gray
- Icon: use a simple crescent-and-star SVG converted to PNG, or a generic radio wave icon
- No external web calls except the radio streams themselves

## Testing
- Test play/stop toggle
- Test station switching while playing
- Test stream failure (point to a bad URL temporarily)
- Test autostart on login
- Verify tray icon appears on PopOS 22.04 (GNOME 42+)
```

---

## Claude Code Prompt

Copy and paste this into your Claude Code session:
```
Build a Linux system tray radio app for PopOS (GNOME) following the CLAUDE.md spec in this directory.

The app should:
1. Appear as an icon in the top bar using AppIndicator3
2. Open a small dropdown window on click with two Quran radio stations (Beirut and Cairo), a Play/Stop button, a volume slider, and a status label
3. Stream audio using GStreamer's playbin element
4. Save the last selected station to ~/.config/quran-radio/config.json
5. Gracefully handle stream errors with a status message

Start by reading CLAUDE.md carefully, then:
- Create quran_radio.py with the full working implementation
- Create icon.png (a simple 64x64 crescent icon using PIL/Pillow if needed, or download a free one)
- Create quran_radio.desktop for autostart
- Create install.sh that installs apt dependencies and copies the autostart file
- Create README.md with usage instructions

Make sure the app works on PopOS 22.04 with Python 3.10+. Use only GTK3 and GStreamer — no Electron, no Qt.
