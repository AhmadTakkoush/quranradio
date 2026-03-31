#!/usr/bin/env python3
"""Quran Karim Radio Station — Linux system tray app for PopOS/GNOME."""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gst, GLib, Gdk, GdkPixbuf, Gio

import json
import os
import threading
import urllib.request

# ── Paths ──────────────────────────────────────────────────────────────────────
APP_DIR     = os.path.dirname(os.path.abspath(__file__))
ICON_PATH   = os.path.join(APP_DIR, "icon.png")
CONFIG_DIR  = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "quran-radio",
)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ── Stations ───────────────────────────────────────────────────────────────────
STATIONS = [
    {
        "name": "Quran Kareem — Beirut",
        "url":  "https://audio.osina.cloud:7987/stream",
        "fallbacks": [],
    },
    {
        "name": "Quran Kareem — Cairo (ERTU 98.2 FM)",
        "url":  "https://n06.radiojar.com/8s5u5tpdtwzuv?rj-ttl=5&rj-tok=AAABnTqNgzMAhlc1s6-kMlbiTw",
        "fallbacks": [],
    },
]

# ── D-Bus interface XML ────────────────────────────────────────────────────────
_SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category"     type="s"       access="read"/>
    <property name="Id"           type="s"       access="read"/>
    <property name="Title"        type="s"       access="read"/>
    <property name="Status"       type="s"       access="read"/>
    <property name="IconName"     type="s"       access="read"/>
    <property name="IconPixmap"   type="a(iiay)" access="read"/>
    <property name="Menu"         type="o"       access="read"/>
    <property name="ItemIsMenu"   type="b"       access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta"       type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""

_MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version"       type="u"  access="read"/>
    <property name="TextDirection" type="s"  access="read"/>
    <property name="Status"        type="s"  access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId"      type="i"          direction="in"/>
      <arg name="recursionDepth" type="i"         direction="in"/>
      <arg name="propertyNames" type="as"         direction="in"/>
      <arg name="revision"      type="u"          direction="out"/>
      <arg name="layout"        type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids"           type="ai"        direction="in"/>
      <arg name="propertyNames" type="as"        direction="in"/>
      <arg name="properties"    type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id"    type="i" direction="in"/>
      <arg name="name"  type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id"        type="i"  direction="in"/>
      <arg name="eventId"   type="s"  direction="in"/>
      <arg name="data"      type="v"  direction="in"/>
      <arg name="timestamp" type="u"  direction="in"/>
    </method>
    <method name="EventGroup">
      <arg name="events"   type="a(isvu)" direction="in"/>
      <arg name="idErrors" type="ai"      direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg name="id"          type="i" direction="in"/>
      <arg name="needUpdate"  type="b" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg name="ids"          type="ai" direction="in"/>
      <arg name="updatesNeeded" type="ai" direction="out"/>
      <arg name="idErrors"      type="ai" direction="out"/>
    </method>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent"   type="i"/>
    </signal>
    <signal name="ItemsPropertiesUpdated">
      <arg name="updatedProps" type="a(ia{sv})"/>
      <arg name="removedProps" type="a(ias)"/>
    </signal>
  </interface>
</node>
"""

# Menu item IDs
#  0 = root container
#  1 = Beirut station   (radio toggle)
#  2 = Cairo station    (radio toggle)
#  3 = separator
#  4 = Play / Stop
#  5 = separator
#  6 = Volume Controls…
#  7 = separator
#  8 = Quit
_MENU_CHILD_IDS = [1, 2, 3, 4, 5, 6, 7, 8]


# ── Native SNI tray icon ───────────────────────────────────────────────────────
class _TrayIcon:
    """StatusNotifierItem + com.canonical.dbusmenu via Gio D-Bus."""

    def __init__(self, app: "QuranRadioApp"):
        self.app       = app
        self._conn     = None
        self._revision = 1
        self._pixmap   = self._load_pixmap()
        self._bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"

        Gio.bus_own_name(
            Gio.BusType.SESSION,
            self._bus_name,
            Gio.BusNameOwnerFlags.NONE,
            self._on_bus_acquired,
            self._on_name_acquired,
            self._on_name_lost,
        )

    # ── Icon loading ──────────────────────────────────────────────────────────
    def _load_pixmap(self) -> list:
        """Load icon.png → list of (width, height, argb32_bytes) tuples."""
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(ICON_PATH)
            pb = pb.scale_simple(64, 64, GdkPixbuf.InterpType.BILINEAR)
            w, h        = pb.get_width(), pb.get_height()
            pixels      = pb.get_pixels()
            n_ch        = pb.get_n_channels()
            rowstride   = pb.get_rowstride()
            argb = bytearray()
            for row in range(h):
                for col in range(w):
                    off = row * rowstride + col * n_ch
                    r = pixels[off];  g = pixels[off + 1]
                    b = pixels[off + 2]
                    a = pixels[off + 3] if n_ch == 4 else 255
                    argb += bytes([a, r, g, b])   # ARGB big-endian
            return [(w, h, bytes(argb))]
        except Exception as e:
            print(f"[tray] icon load error: {e}")
            return []

    # ── Bus callbacks ─────────────────────────────────────────────────────────
    def _on_bus_acquired(self, conn, _name):
        self._conn = conn

        sni_node  = Gio.DBusNodeInfo.new_for_xml(_SNI_XML)
        menu_node = Gio.DBusNodeInfo.new_for_xml(_MENU_XML)

        conn.register_object(
            "/StatusNotifierItem",
            sni_node.interfaces[0],
            self._sni_call, self._sni_prop, None,
        )
        conn.register_object(
            "/MenuBar",
            menu_node.interfaces[0],
            self._menu_call, self._menu_prop, None,
        )

    def _on_name_acquired(self, _conn, name):
        self._conn.call(
            "org.kde.StatusNotifierWatcher",
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (name,)),
            None,
            Gio.DBusCallFlags.NONE,
            -1, None,
            lambda conn, res: self._reg_done(conn, res),
        )

    def _reg_done(self, conn, res):
        try:
            conn.call_finish(res)
        except Exception as e:
            print(f"[tray] SNI registration failed: {e}")

    def _on_name_lost(self, _conn, _name):
        print("[tray] StatusNotifierWatcher not available — tray icon inactive")

    # ── SNI interface ─────────────────────────────────────────────────────────
    def _sni_prop(self, _conn, _sender, _path, _iface, prop):
        table = {
            "Category":   GLib.Variant("s",       "ApplicationStatus"),
            "Id":         GLib.Variant("s",       "quran-radio"),
            "Title":      GLib.Variant("s",       "Quran Radio"),
            "Status":     GLib.Variant("s",       "Active"),
            "IconName":   GLib.Variant("s",       ""),
            "IconPixmap": GLib.Variant("a(iiay)", self._pixmap),
            "Menu":       GLib.Variant("o",       "/MenuBar"),
            "ItemIsMenu": GLib.Variant("b",       False),
        }
        return table.get(prop)

    def _sni_call(self, _conn, _sender, _path, _iface, method, _params, inv):
        if method in ("Activate", "ContextMenu", "SecondaryActivate"):
            GLib.idle_add(self.app._toggle_window)
        inv.return_value(None)

    # ── dbusmenu interface ────────────────────────────────────────────────────
    def _menu_prop(self, _conn, _sender, _path, _iface, prop):
        table = {
            "Version":       GLib.Variant("u",  3),
            "TextDirection": GLib.Variant("s",  "ltr"),
            "Status":        GLib.Variant("s",  "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return table.get(prop)

    def _item_props(self, item_id: int) -> dict:
        app = self.app
        if item_id == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        if item_id in (3, 5, 7):
            return {"type": GLib.Variant("s", "separator")}
        if item_id in (1, 2):
            idx = item_id - 1
            return {
                "label":        GLib.Variant("s", STATIONS[idx]["name"]),
                "toggle-type":  GLib.Variant("s", "radio"),
                "toggle-state": GLib.Variant("i", 1 if app.selected_idx == idx else 0),
                "enabled":      GLib.Variant("b", True),
                "visible":      GLib.Variant("b", True),
            }
        if item_id == 4:
            return {
                "label":   GLib.Variant("s", "⏹  Stop" if app.is_playing else "▶  Play"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        if item_id == 6:
            return {
                "label":   GLib.Variant("s", "Volume Controls…"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        if item_id == 8:
            return {
                "label":   GLib.Variant("s", "Quit"),
                "enabled": GLib.Variant("b", True),
                "visible": GLib.Variant("b", True),
            }
        return {}

    def _build_item(self, item_id: int, depth: int) -> tuple:
        """Recursively build a (id, props, children) tuple for dbusmenu."""
        props    = self._item_props(item_id)
        children = []
        if item_id == 0 and depth != 0:
            next_depth = -1 if depth == -1 else depth - 1
            for cid in _MENU_CHILD_IDS:
                child = self._build_item(cid, next_depth)
                children.append(GLib.Variant("(ia{sv}av)", child))
        return (item_id, props, children)

    def _menu_call(self, _conn, _sender, _path, _iface, method, params, inv):
        if method == "GetLayout":
            parent_id, depth, _props = params.unpack()
            layout = self._build_item(parent_id, depth)
            inv.return_value(GLib.Variant("(u(ia{sv}av))", (self._revision, layout)))

        elif method == "GetGroupProperties":
            ids, _prop_names = params.unpack()
            result = [(i, self._item_props(i)) for i in ids]
            inv.return_value(GLib.Variant("(a(ia{sv}))", (result,)))

        elif method == "GetProperty":
            item_id, prop_name = params.unpack()
            val = self._item_props(item_id).get(prop_name, GLib.Variant("s", ""))
            inv.return_value(GLib.Variant("(v)", (val,)))

        elif method == "Event":
            item_id, event_id, _data, _ts = params.unpack()
            if event_id == "clicked":
                GLib.idle_add(self._handle_click, item_id)
            inv.return_value(None)

        elif method == "EventGroup":
            events, = params.unpack()
            for item_id, event_id, _data, _ts in events:
                if event_id == "clicked":
                    GLib.idle_add(self._handle_click, item_id)
            inv.return_value(GLib.Variant("(ai)", ([],)))

        elif method == "AboutToShow":
            inv.return_value(GLib.Variant("(b)", (False,)))

        elif method == "AboutToShowGroup":
            inv.return_value(GLib.Variant("(aiai)", ([], [])))

        else:
            inv.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod", method
            )

    def _handle_click(self, item_id: int):
        app = self.app
        if item_id in (1, 2):
            idx = item_id - 1
            app._radio_btns[idx].set_active(True)   # syncs popup window too
            app._switch_station(idx)
        elif item_id == 4:
            app._on_play_stop()
        elif item_id == 6:
            app._toggle_window()
        elif item_id == 8:
            app._quit()

    # ── Public ────────────────────────────────────────────────────────────────
    def update_menu(self):
        """Notify the tray host that the menu has changed."""
        if not self._conn:
            return
        self._revision += 1
        self._conn.emit_signal(
            None, "/MenuBar",
            "com.canonical.dbusmenu", "LayoutUpdated",
            GLib.Variant("(ui)", (self._revision, 0)),
        )


# ── Helpers ────────────────────────────────────────────────────────────────────
def url_alive(url: str, timeout: int = 5) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"station": 0, "volume": 80}


def save_config(data: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── CSS ────────────────────────────────────────────────────────────────────────
APP_CSS = b"""
window {
    background-color: #1e1e1e;
}
label#title {
    color: #2da05a;
    font-weight: bold;
    font-size: 15px;
}
button#play-btn {
    background: #1B6B3A;
    color: white;
    border-radius: 5px;
    font-weight: bold;
    padding: 4px 0;
    border: none;
    box-shadow: none;
}
button#play-btn:hover {
    background: #24924f;
}
radiobutton label,
label {
    color: #d8d8d8;
}
label#status {
    color: #888888;
    font-style: italic;
    font-size: 11px;
}
scale trough {
    background-color: #3a3a3a;
}
scale highlight {
    background-color: #1B6B3A;
}
"""


# ── Main App ───────────────────────────────────────────────────────────────────
class QuranRadioApp:
    def __init__(self):
        Gst.init(None)

        self.config          = load_config()
        self.selected_idx    = self.config.get("station", 0)
        self.volume          = self.config.get("volume", 80)
        self.is_playing      = False
        self._timeout_id     = None
        self._window_visible = False

        # ── GStreamer ──
        self.player = Gst.ElementFactory.make("playbin", "player")
        self.player.set_property("volume", self.volume / 100.0)

        # Force mono→stereo upmix: downmix to true mono first, then expand
        # to stereo so both channels carry audio regardless of source layout.
        try:
            to_mono    = Gst.ElementFactory.make("audioconvert", "to_mono")
            mono_caps  = Gst.ElementFactory.make("capsfilter",   "mono_caps")
            to_stereo  = Gst.ElementFactory.make("audioconvert", "to_stereo")
            ster_caps  = Gst.ElementFactory.make("capsfilter",   "ster_caps")
            sink       = Gst.ElementFactory.make("autoaudiosink","audio_out")

            mono_caps.set_property(
                "caps", Gst.Caps.from_string("audio/x-raw,channels=1")
            )
            ster_caps.set_property(
                "caps",
                Gst.Caps.from_string("audio/x-raw,channels=2,channel-mask=(bitmask)0x3"),
            )

            stereo_bin = Gst.Bin.new("stereo_sink")
            for el in (to_mono, mono_caps, to_stereo, ster_caps, sink):
                stereo_bin.add(el)
            to_mono.link(mono_caps)
            mono_caps.link(to_stereo)
            to_stereo.link(ster_caps)
            ster_caps.link(sink)
            stereo_bin.add_pad(
                Gst.GhostPad.new("sink", to_mono.get_static_pad("sink"))
            )
            self.player.set_property("audio-sink", stereo_bin)
            print("[audio] stereo sink active (mono→stereo upmix)")
        except Exception as e:
            print(f"[audio] mono→stereo sink unavailable: {e}")

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_gst_message)

        # ── Native SNI tray (replaces AppIndicator3) ──
        self._tray = _TrayIcon(self)

        # ── Popup window ──
        self._apply_css()
        self.window = self._build_window()

        # Verify Cairo URL in background thread
        threading.Thread(target=self._verify_cairo_url, daemon=True).start()

    # ── CSS ──────────────────────────────────────────────────────────────────
    def _apply_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(APP_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ── Window ───────────────────────────────────────────────────────────────
    def _build_window(self) -> Gtk.Window:
        win = Gtk.Window()
        win.set_title("Quran Radio")
        win.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_keep_above(True)
        win.set_resizable(False)
        win.set_border_width(14)
        win.set_default_size(280, -1)
        win.connect("focus-out-event", self._on_focus_out)
        win.connect("delete-event", lambda w, e: w.hide() or True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        win.add(vbox)

        title = Gtk.Label(label="Quran Radio 📻")
        title.set_name("title")
        title.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(title, False, False, 4)

        vbox.pack_start(Gtk.Separator(), False, False, 2)

        self._radio_btns: list[Gtk.RadioButton] = []
        group_btn = None
        for i, station in enumerate(STATIONS):
            btn = Gtk.RadioButton.new_with_label_from_widget(group_btn, station["name"])
            if group_btn is None:
                group_btn = btn
            btn.set_active(i == self.selected_idx)
            btn.connect("toggled", self._on_station_toggled, i)
            self._radio_btns.append(btn)
            vbox.pack_start(btn, False, False, 0)

        vbox.pack_start(Gtk.Separator(), False, False, 2)

        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vol_row.pack_start(Gtk.Label(label="Vol:"), False, False, 0)

        self._vol_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self._vol_slider.set_value(self.volume)
        self._vol_slider.set_hexpand(True)
        self._vol_slider.set_draw_value(False)
        self._vol_slider.connect("value-changed", self._on_volume_changed)
        vol_row.pack_start(self._vol_slider, True, True, 0)

        self._vol_label = Gtk.Label(label=f"{self.volume}%")
        self._vol_label.set_width_chars(4)
        vol_row.pack_start(self._vol_label, False, False, 0)
        vbox.pack_start(vol_row, False, False, 0)

        self._play_btn = Gtk.Button(label="▶  Play")
        self._play_btn.set_name("play-btn")
        self._play_btn.connect("clicked", self._on_play_stop)
        vbox.pack_start(self._play_btn, False, False, 4)

        self._status_lbl = Gtk.Label(label="Stopped")
        self._status_lbl.set_name("status")
        self._status_lbl.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(self._status_lbl, False, False, 0)

        win.show_all()
        win.hide()
        return win

    # ── Window visibility ────────────────────────────────────────────────────
    def _toggle_window(self, *_):
        if self._window_visible:
            self.window.hide()
            self._window_visible = False
        else:
            self._show_window()

    def _show_window(self):
        self.window.show_all()
        self.window.present()

        display  = Gdk.Display.get_default()
        monitor  = display.get_primary_monitor() or display.get_monitor(0)
        geo      = monitor.get_geometry()
        win_w, _ = self.window.get_size()
        x = geo.x + geo.width - win_w - 20
        y = geo.y + 44
        self.window.move(x, y)
        self._window_visible = True

    def _on_focus_out(self, _widget, _event):
        self.window.hide()
        self._window_visible = False
        return False

    # ── Station selection ────────────────────────────────────────────────────
    def _on_station_toggled(self, btn: Gtk.RadioButton, idx: int):
        if not btn.get_active() or idx == self.selected_idx:
            return
        self._switch_station(idx)

    def _switch_station(self, idx: int):
        self.selected_idx = idx
        self.config["station"] = idx
        save_config(self.config)
        self._tray.update_menu()
        if self.is_playing:
            self._stop_playback()
            self._start_playback()

    # ── Volume ───────────────────────────────────────────────────────────────
    def _on_volume_changed(self, slider: Gtk.Scale):
        vol = int(slider.get_value())
        self.volume = vol
        self._vol_label.set_text(f"{vol}%")
        self.player.set_property("volume", vol / 100.0)
        self.config["volume"] = vol
        save_config(self.config)

    # ── Play / Stop ──────────────────────────────────────────────────────────
    def _on_play_stop(self, *_):
        if self.is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        url = STATIONS[self.selected_idx]["url"]
        self.player.set_state(Gst.State.NULL)
        self.player.set_property("uri", url)
        self.player.set_state(Gst.State.PLAYING)
        self.is_playing = True
        self._play_btn.set_label("⏹  Stop")
        self._tray.update_menu()
        self._set_status("Buffering…")

        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
        self._timeout_id = GLib.timeout_add(8000, self._on_connect_timeout)

    def _stop_playback(self):
        self.player.set_state(Gst.State.NULL)
        self.is_playing = False
        self._play_btn.set_label("▶  Play")
        self._tray.update_menu()
        self._set_status("Stopped")
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _on_connect_timeout(self):
        if self.is_playing and self._status_lbl.get_text().startswith("Buffering"):
            self._stop_playback()
            self._set_status("Error: Connection timed out")
        self._timeout_id = None
        return False

    # ── GStreamer bus ────────────────────────────────────────────────────────
    def _on_gst_message(self, _bus, msg):
        t = msg.type

        if t == Gst.MessageType.ERROR:
            err, _ = msg.parse_error()
            GLib.idle_add(self._stop_playback)
            self._set_status(f"Error: {err.message}")

        elif t == Gst.MessageType.BUFFERING:
            pct = msg.parse_buffering()
            if pct < 100:
                self.player.set_state(Gst.State.PAUSED)
                self._set_status(f"Buffering… {pct}%")
            else:
                self.player.set_state(Gst.State.PLAYING)
                self._clear_timeout()
                self._set_status("Playing")

        elif t == Gst.MessageType.STATE_CHANGED:
            if msg.src == self.player:
                _, new, _ = msg.parse_state_changed()
                if new == Gst.State.PLAYING:
                    self._clear_timeout()
                    self._set_status("Playing")

    def _clear_timeout(self):
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    # ── Utilities ────────────────────────────────────────────────────────────
    def _set_status(self, text: str):
        GLib.idle_add(self._status_lbl.set_text, text)

    def _verify_cairo_url(self):
        station = STATIONS[1]
        if not url_alive(station["url"]):
            for fb in station["fallbacks"]:
                if url_alive(fb):
                    station["url"] = fb
                    break

    def _quit(self, *_):
        self._stop_playback()
        Gtk.main_quit()

    def run(self):
        Gtk.main()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QuranRadioApp()
    app.run()
