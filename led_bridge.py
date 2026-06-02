"""
led_bridge.py

Vollständig in den Launcher integrierte LED-Bridge.
Kein separater bridge.py-Prozess notwendig.

Architektur:
  Launcher (launcher.py)
    └── LEDBridge
          ├── Serial → USB → ESP32 → LEDs
          └── WebSocket-Server ws://localhost:8765
                ├── Pac-Man (Godot)
                ├── Asteroids (Browser/JS)
                └── Space Invaders (Python)

Kette A (Spieler-nah):
  marquee=0 | monitor_top=1 | monitor_right=2
  monitor_bottom=3 | monitor_left=4 | control_panel=5 | alle=99
"""

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union

try:
    import serial
    import serial.tools.list_ports
    _SERIAL_AVAILABLE = True
except ImportError:
    _SERIAL_AVAILABLE = False
    logging.warning("LED: pyserial nicht installiert — Hardware-LEDs deaktiviert.")

try:
    import websockets
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False
    logging.warning("LED: websockets nicht installiert — Spiel-LED-Integration deaktiviert.")

logger = logging.getLogger(__name__)

# --- Konfiguration -----------------------------------------------------------

_SERIAL_PORT          = os.environ.get("ARCADE_SERIAL_PORT", "/dev/ttyACM0")
_SERIAL_BAUD          = 115_200
_WS_HOST              = "localhost"
_WS_PORT              = 8765
_ATTRACT_IDLE_TIMEOUT = int(os.environ.get("ARCADE_ATTRACT_TIMEOUT", "30"))

# --- Segment-Mapping ---------------------------------------------------------

SEGMENTS: Dict[str, int] = {
    "marquee":        0,
    "monitor_top":    1,
    "monitor_right":  2,
    "monitor_bottom": 3,
    "monitor_left":   4,
    "control_panel":  5,
    "all_a":          99,
}

_MONITOR_SEGMENTS = ["monitor_top", "monitor_right", "monitor_bottom", "monitor_left"]
_PHYSICAL_INDICES = [segment_id for segment_id in SEGMENTS.values() if segment_id != 99]

# --- Spielfarben -------------------------------------------------------------

GAME_COLORS: Dict[str, Tuple[int, int, int]] = {
    "pac_man":        (255, 255,   0),
    "space_invaders": (255,   0, 255),
    "asteroids":      (  0, 255, 255),
}
_COLOR_CYCLE = ["pac_man", "space_invaders", "asteroids"]

# --- Prioritäten -------------------------------------------------------------

PRIORITY_LOW    = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH   = 3

# --- Effekt-Definitionen -----------------------------------------------------

@dataclass
class EffectDef:
    """Statische Konfiguration eines LED-Effekts ohne Farbinformation."""
    effect_type: str
    segments:    Union[str, List[str]]
    speed:       int = 50
    length:      int = 5
    repeat:      int = 0
    priority:    int = PRIORITY_LOW

# Menü-Selektion
FX_SELECT_GAME  = EffectDef("scanner", "all_a",                     speed=50,   repeat=-1,  priority=PRIORITY_MEDIUM)

# Attract-Mode
FX_ATTRACT      = EffectDef("sparkle", "all_a",                     speed=50,   repeat=-1,  priority=PRIORITY_MEDIUM)

# Spielstart
FX_START_FLASH  = EffectDef("fill",    "all_a",                                 repeat=2,   priority=PRIORITY_HIGH)

# Power-Down (Farbe ist immer Schwarz → _apply_direct)
FX_SHUTDOWN_WIPE = EffectDef("wipe", ["marquee", "control_panel"],  speed=55,               priority=PRIORITY_HIGH)
FX_SHUTDOWN_FILL = EffectDef("fill", _MONITOR_SEGMENTS,                                     priority=PRIORITY_HIGH)

# ESP32 Attract-Mode
FX_ESP32_ATTRACT = EffectDef("pulse", "all_a",                      speed=30,   repeat=-1,  priority=PRIORITY_LOW)

# --- LED Bridge --------------------------------------------------------------

class LEDBridge:
    """
    Eigenständige LED-Bridge: steuert ESP32 via Serial und stellt
    WebSocket-Server für Spiele bereit. Läuft in Daemon-Threads.
    """

    _PRIORITY_LABELS = {PRIORITY_LOW: "LOW", PRIORITY_MEDIUM: "MED", PRIORITY_HIGH: "HIGH"}

    def __init__(
        self,
        serial_port:          Optional[str] = _SERIAL_PORT,
        serial_baud:          int           = _SERIAL_BAUD,
        ws_host:              str           = _WS_HOST,
        ws_port:              int           = _WS_PORT,
        attract_idle_timeout: int           = _ATTRACT_IDLE_TIMEOUT,
    ):
        # ── Serial ────────────────────────────────────────────────────────────
        self._serial_port = serial_port
        self._serial_baud = serial_baud
        self._serial: Optional[object] = None
        self._serial_lock = threading.Lock()

        # ── WebSocket-Server (für Spiele) ─────────────────────────────────────
        self._ws_host    = ws_host
        self._ws_port    = ws_port
        self._ws_clients: Set = set()

        # ── asyncio-Loop (WS-Server) ──────────────────────────────────────────
        self._loop        = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_ws_loop, daemon=True, name="LED-WSServer"
        )

        # ── Prioritäts-Tracking ───────────────────────────────────────────────
        self._current_priority: int = 0
        self._priority_lock = threading.Lock()

        # ── Attract-Mode State ────────────────────────────────────────────────
        self._is_attract_active    = True
        self._attract_color_index  = 0
        self._attract_event        = threading.Event()
        self._attract_idle_timeout = attract_idle_timeout

        # ── Keepalive ─────────────────────────────────────────────────────────
        self._is_keepalive_active    = False
        self._keepalive_effects: List[dict] = []
        self._keepalive_effects_lock = threading.Lock()
        self._is_recording_effects   = False

        self._current_game: Optional[str] = None
        self._running = False
        self._last_interaction_time: float = 0.0

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def start(self):
        """Bridge starten — einmalig beim Launcher-Init aufrufen."""
        self._running = True
        self._connect_serial()
        self._loop_thread.start()
        time.sleep(0.3)
        threading.Thread(target=self._attract_loop,          daemon=True, name="LED-Attract").start()
        threading.Thread(target=self._keepalive_loop,        daemon=True, name="LED-Keepalive").start()
        threading.Thread(target=self._serial_reconnect_loop, daemon=True, name="LED-SerialReconnect").start()
        logger.info(
            "LEDBridge: gestartet | Serial: %s | WS: ws://%s:%d",
            self._serial_port or "auto-detect", self._ws_host, self._ws_port,
        )

    def stop(self, send_all_off: bool = True):
        """Sauber beenden — Threads stoppen, optional alle LEDs aus."""
        self._running = False
        self._attract_event.set()
        if send_all_off:
            self._send_all_off()
        time.sleep(0.5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        with self._serial_lock:
            if self._serial and self._serial.is_open:
                self._serial.close()
        logger.info("LEDBridge: gestoppt.")

    # ── Öffentliche Launcher-API ──────────────────────────────────────────────

    def notify_selection_changed(self, game_name: str):
        """Beim Navigieren im Menü (W/S): Spielfarbe anzeigen."""
        self._is_attract_active     = False
        self._is_keepalive_active   = True
        self._last_interaction_time = time.time()
        self._attract_event.set()

        r, g, b = self._game_color(game_name)
        self._reset_priority()
        with self._keepalive_effects_lock:
            self._keepalive_effects.clear()

        self._is_recording_effects = True
        self._apply(FX_SELECT_GAME, r, g, b)
        self._is_recording_effects = False

    def notify_game_start(self, game_name: str):
        """Vor dem Spielstart: weißes Blitz-Fill (HIGH)."""
        self._current_game          = game_name
        self._is_attract_active     = False
        self._is_keepalive_active   = False
        with self._keepalive_effects_lock:
            self._keepalive_effects.clear()
        self._attract_event.set()
        self._reset_priority()

        self._apply(FX_START_FLASH, 255, 255, 255)

    def notify_game_stop(self):
        """Nach Spielende: sofortiger Takeover, dann Attract-Mode neu starten."""
        self._current_game          = None
        self._is_keepalive_active   = True
        self._reclaim_all_segments()
        self._is_attract_active     = True
        self._attract_color_index   = 0
        self._reset_priority()
        self._attract_event.set()
        logger.info("LEDBridge: Attract-Mode neugestartet.")

    def notify_launcher_exit(self):
        """Power-Down-Animation, dann ESP32-Attract-Mode aktivieren."""
        logger.info("LED: Launcher-Exit — Power-Down-Animation...")
        self._is_attract_active = False
        self._attract_event.set()
        self._reset_priority()
        self._apply_direct(FX_SHUTDOWN_WIPE)
        self._apply_direct(FX_SHUTDOWN_FILL)
        time.sleep(0.6)
        self._apply_direct(FX_ESP32_ATTRACT)
        self.stop(send_all_off=False)

    def is_connected(self) -> bool:
        """True wenn ESP32 via Serial verbunden."""
        return self._serial is not None and self._serial.is_open

    # ── Interne Effekt-Logik ──────────────────────────────────────────────────

    def _apply(self, fx: EffectDef, r: int, g: int, b: int) -> None:
        self._send_effect(fx.effect_type, fx.segments, r, g, b,
                         speed=fx.speed, length=fx.length, repeat=fx.repeat,
                         priority=fx.priority)

    def _apply_direct(self, fx: EffectDef) -> None:
        """Effekt ohne Prioritätsprüfung mit Schwarz senden (Power-Down)."""
        indices = self._resolve_segment_indices(fx.segments)
        if not indices:
            return
        self._write_serial({
            "cmd": "effect", "chain": "A", "type": fx.effect_type,
            "segment": indices[0] if len(indices) == 1 else indices,
            "color": {"r": 0, "g": 100, "b": 200},
            "speed": fx.speed, "length": fx.length, "repeat": 1, "priority": PRIORITY_HIGH,
        })

    def _send_effect(
        self,
        effect_type: str,
        segments:    Union[str, List[str]],
        r: int, g: int, b: int,
        speed:       int = 50,
        length:      int = 5,
        repeat:      int = 0,
        priority:    int = PRIORITY_LOW,
    ):
        """Prioritätsprüfung → Serial senden."""
        indices   = self._resolve_segment_indices(segments)
        seg_names = [segments] if isinstance(segments, str) else list(segments)
        if not indices:
            return

        with self._priority_lock:
            if priority < self._current_priority:
                logger.debug(
                    "LED: %s auf '%s' blockiert (Prio %s < %s)",
                    effect_type, ",".join(seg_names),
                    self._PRIORITY_LABELS.get(priority, priority),
                    self._PRIORITY_LABELS.get(self._current_priority, self._current_priority),
                )
                return
            self._current_priority = priority

        logger.info(
            "LED [A] | %-7s | %-40s | rgb(%3d,%3d,%3d) | speed=%-3d repeat=%d",
            effect_type, ",".join(seg_names), r, g, b, speed, repeat,
        )
        payload = {
            "cmd":        "effect",
            "chain":      "A",
            "type":       effect_type,
            "segment":    indices[0] if len(indices) == 1 else indices,
            "color":      {"r": r, "g": g, "b": b},
            "speed":      speed,
            "length":     length,
            "repeat":   repeat,
            "priority": priority,
        }
        with self._keepalive_effects_lock:
            if self._is_recording_effects:
                self._keepalive_effects.append(dict(payload))
        self._write_serial(payload)

    def _resolve_segment_indices(self, segments: Union[str, List[str]]) -> List[int]:
        seg_names = [segments] if isinstance(segments, str) else segments
        indices = [SEGMENTS[name] for name in seg_names if name in SEGMENTS]
        for name in seg_names:
            if name not in SEGMENTS:
                logger.debug("LED: Unbekanntes Segment: %s", name)
        return indices

    def _send_all_off(self):
        self._write_serial({
            "cmd": "effect", "chain": "A", "type": "off",
            "segment": 99, "priority": PRIORITY_HIGH,
        })

    def _reclaim_all_segments(self):
        """HIGH-Takeover: überschreibt alle Spiel-Effekte auf dem ESP32."""
        logger.info("LED: Launcher-Takeover — alle Spiel-Effekte überschrieben (HIGH)")
        self._send_all_off()

    def _keepalive_loop(self):
        """Re-sendet Launcher-Zustand alle 1.5 s mit HIGH-Prio."""
        while self._running:
            time.sleep(1.5)
            if not self._is_keepalive_active:
                continue
            with self._keepalive_effects_lock:
                cmds = list(self._keepalive_effects)
            if not cmds:
                continue
            logger.debug("LED: Keepalive — %d Effekte re-assertiert (HIGH)", len(cmds))
            for cmd in cmds:
                override = dict(cmd)
                override["priority"] = PRIORITY_HIGH
                self._write_serial(override)

    def _serial_reconnect_loop(self):
        """Prüft alle 5 s ob Serial getrennt ist und stellt Verbindung wieder her."""
        while self._running:
            time.sleep(5)
            with self._serial_lock:
                is_connected = self._serial is not None and self._serial.is_open
            if not is_connected and _SERIAL_AVAILABLE:
                logger.info("LED: Serial nicht verbunden — versuche Reconnect...")
                self._connect_serial()

    def _reset_priority(self):
        with self._priority_lock:
            self._current_priority = 0

    # ── Attract-Mode (Daemon-Thread) ──────────────────────────────────────────

    def _attract_loop(self):
        while self._running:
            self._attract_event.clear()

            if not self._is_attract_active:
                idle = time.time() - self._last_interaction_time
                can_activate = (
                    self._last_interaction_time > 0
                    and idle >= self._attract_idle_timeout
                    and self._current_game is None
                )
                if can_activate:
                    self._is_attract_active   = True
                    self._attract_color_index = 0
                    self._reset_priority()
                    logger.info("LEDBridge: Attract-Mode nach %.0fs Inaktivität aktiviert", idle)
                else:
                    self._attract_event.wait(timeout=1.0)
                    continue

            r, g, b = GAME_COLORS[_COLOR_CYCLE[self._attract_color_index % len(_COLOR_CYCLE)]]
            self._reset_priority()

            with self._keepalive_effects_lock:
                self._keepalive_effects.clear()
            self._is_recording_effects = True
            self._apply(FX_ATTRACT, r, g, b)
            self._is_recording_effects = False

            self._attract_event.wait(timeout=4.0)
            if self._is_attract_active:
                self._attract_color_index += 1

    # ── Serial-Kommunikation ──────────────────────────────────────────────────

    def _connect_serial(self):
        if not _SERIAL_AVAILABLE:
            return
        port = self._serial_port or self._auto_detect_port()
        if not port:
            logger.warning("LED: Kein ESP32 gefunden — Serial deaktiviert. "
                           "Tipp: ARCADE_SERIAL_PORT=COM3 setzen.")
            return
        try:
            self._serial = serial.Serial(port, self._serial_baud, timeout=1)
            self._serial_port = port
            logger.info("LED: Serial verbunden → %s @ %d Baud", port, self._serial_baud)
            threading.Thread(
                target=self._serial_reader, daemon=True, name="LED-SerialRX"
            ).start()
        except Exception as exc:
            logger.warning("LED: Serial-Verbindung fehlgeschlagen (%s): %s", port, exc)
            self._serial = None

    def _auto_detect_port(self) -> Optional[str]:
        if not _SERIAL_AVAILABLE:
            return None
        keywords = ("cp210", "ch340", "esp32", "uart", "usb serial",
                    "usb-serial", "silicon labs")
        for port_info in serial.tools.list_ports.comports():
            description  = (port_info.description  or "").lower()
            manufacturer = (port_info.manufacturer or "").lower()
            if any(k in description or k in manufacturer for k in keywords):
                logger.info("LED: ESP32 gefunden auf %s (%s)", port_info.device, port_info.description)
                return port_info.device
        return None

    def _write_serial(self, payload: dict):
        """Thread-sicher JSON an ESP32 senden."""
        try:
            data = json.dumps(payload, separators=(",", ":")) + "\n"
            with self._serial_lock:
                if not self._serial or not self._serial.is_open:
                    return
                self._serial.write(data.encode("utf-8"))
        except Exception as exc:
            logger.warning("LED: Serial-Schreibfehler: %s", exc)
            with self._serial_lock:
                self._serial = None

    def _serial_reader(self):
        """ESP32-Antworten empfangen: Heartbeat + NACK."""
        while self._running:
            with self._serial_lock:
                serial_ref = self._serial
            if not serial_ref or not serial_ref.is_open:
                break
            try:
                raw_line = serial_ref.readline().decode("utf-8", errors="ignore").strip()
                if not raw_line:
                    continue
                data = json.loads(raw_line)
                if data.get("status") == "ready":
                    logger.info(
                        "ESP32 bereit — v%s | Kette A: %d LEDs",
                        data.get("version", "?"),
                        data.get("leds_a", 0),
                    )
                elif data.get("status") == "error":
                    logger.error(
                        "ESP32-Fehler [%s]: %s",
                        data.get("code", "?"),
                        data.get("msg", ""),
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as exc:
                logger.error("LED: Serial-Reader unerwartet beendet: %s", exc)
                break

    # ── WebSocket-Server (für Spiele) ─────────────────────────────────────────

    def _run_ws_loop(self):
        self._loop.run_until_complete(self._ws_serve())

    async def _ws_serve(self):
        if not _WS_AVAILABLE:
            return
        while self._running:
            try:
                async with websockets.serve(
                    self._handle_game_client, self._ws_host, self._ws_port
                ):
                    logger.info(
                        "LED-WS: Server bereit auf ws://%s:%d", self._ws_host, self._ws_port
                    )
                    while self._running:
                        await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("LED-WS: Server-Fehler: %s — Retry in 5s", exc)
                await asyncio.sleep(5)

    async def _handle_game_client(self, websocket):
        client_address = getattr(websocket, "remote_address", "?")
        self._ws_clients.add(websocket)
        logger.info("LED-WS: Spiel verbunden: %s", client_address)
        try:
            async for message in websocket:
                await self._handle_game_message(message)
        except Exception as exc:
            logger.debug("LED-WS: Client-Verbindungsfehler (%s): %s", client_address, exc)
        finally:
            self._ws_clients.discard(websocket)
            logger.info("LED-WS: Spiel getrennt: %s", client_address)

    async def _handle_game_message(self, message: str):
        """Spiel-Effektbefehle validieren und an ESP32 senden."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        if data.get("cmd") != "effect":
            return

        color = data.get("color", {})
        if isinstance(color, dict):
            data["color"] = {
                "r": self._clamp_color_channel(color.get("r", 0)),
                "g": self._clamp_color_channel(color.get("g", 0)),
                "b": self._clamp_color_channel(color.get("b", 0)),
            }

        self._write_serial(data)
        logger.debug("LED-WS: Spiel-Effekt → ESP32: %s", str(data)[:60])

    # ── Hilfsfunktionen ───────────────────────────────────────────────────────

    @staticmethod
    def _clamp_color_channel(value) -> int:
        return max(0, min(255, int(value)))

    @staticmethod
    def _game_color(game_name: str) -> Tuple[int, int, int]:
        return GAME_COLORS[game_name.lower()]


# ── Singleton-Accessor ────────────────────────────────────────────────────────

_bridge_instance: Optional[LEDBridge] = None

def get_bridge() -> LEDBridge:
    """Globale LEDBridge-Instanz (lazy init)."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = LEDBridge()
    return _bridge_instance
