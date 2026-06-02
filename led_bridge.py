"""
led_bridge.py

LED-Bridge für den Arcade-Launcher.
Steuert ESP32 via Serial und stellt einen WebSocket-Server für Spiele bereit.

Architektur:
  LEDBridge (Fassade)
    ├── SerialTransport      — Serial I/O + Reconnect
    ├── EffectDispatcher     — Prioritäten, Segmente, Keepalive
    ├── AttractMode          — Idle-Farbrotation
    └── GameWebSocketServer  — WS-Server für Spiele

Kette A:
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

# --- Konfiguration ---

_SERIAL_PORT          = os.environ.get("ARCADE_SERIAL_PORT", "/dev/ttyACM0")
_SERIAL_BAUD          = 115_200
_WS_HOST              = "localhost"
_WS_PORT              = 8765
_ATTRACT_IDLE_TIMEOUT = int(os.environ.get("ARCADE_ATTRACT_TIMEOUT", "30"))

# --- Segment-Mapping ---

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

# --- Spielfarben ---

GAME_COLORS: Dict[str, Tuple[int, int, int]] = {
    "pac_man":        (255, 255,   0),
    "space_invaders": (255,   0, 255),
    "asteroids":      (  0, 255, 255),
}
_COLOR_CYCLE = ["pac_man", "space_invaders", "asteroids"]

# --- Prioritäten ---

PRIORITY_LOW    = 1
PRIORITY_MEDIUM = 2
PRIORITY_HIGH   = 3

# --- Effekt-Definitionen ---

@dataclass
class EffectDef:
    """Statische Konfiguration eines LED-Effekts ohne Farbinformation."""
    effect_type: str
    segments:    Union[str, List[str]]
    speed:       int = 50
    length:      int = 5
    repeat:      int = 0
    priority:    int = PRIORITY_LOW

FX_SELECT_GAME   = EffectDef("scanner", "all_a",                    speed=50, repeat=-1, priority=PRIORITY_MEDIUM)
FX_ATTRACT       = EffectDef("sparkle", "all_a",                    speed=50, repeat=-1, priority=PRIORITY_MEDIUM)
FX_START_FLASH   = EffectDef("fill",    "all_a",                              repeat=2,  priority=PRIORITY_HIGH)
FX_SHUTDOWN_WIPE = EffectDef("wipe",  ["marquee", "control_panel"], speed=55,            priority=PRIORITY_HIGH)
FX_SHUTDOWN_FILL = EffectDef("fill",  _MONITOR_SEGMENTS,                                 priority=PRIORITY_HIGH)


# ─────────────────────────────────────────────────────────────────────────────
# SerialTransport
# ─────────────────────────────────────────────────────────────────────────────

class SerialTransport:
    """
    Kapselt die serielle Verbindung zum ESP32.
    Verwaltet Verbindungsaufbau, automatisches Reconnect und Empfangs-Thread.
    """

    _ESP32_KEYWORDS = (
        "cp210", "ch340", "esp32", "uart", "usb serial", "usb-serial", "usb jtag", "silicon labs"
    )

    def __init__(self, port: Optional[str] = _SERIAL_PORT, baud: int = _SERIAL_BAUD) -> None:
        self._port    = port
        self._baud    = baud
        self._conn:   Optional[serial.Serial] = None
        self._lock    = threading.Lock()
        self._running = False

    @property
    def port(self) -> Optional[str]:
        return self._port

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and self._conn.is_open

    def start(self) -> None:
        self._running = True
        self._connect()
        threading.Thread(target=self._reconnect_loop, daemon=True, name="LED-SerialReconnect").start()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            if self._conn and self._conn.is_open:
                self._conn.close()

    def write(self, payload: dict) -> None:
        """Sendet ein JSON-Payload an den ESP32. Thread-sicher."""
        try:
            data = json.dumps(payload, separators=(",", ":")) + "\n"
            with self._lock:
                if not self._conn or not self._conn.is_open:
                    return
                self._conn.write(data.encode("utf-8"))
        except Exception as exc:
            logger.warning("LED: Serial-Schreibfehler: %s", exc)
            with self._lock:
                self._conn = None

    def _connect(self) -> None:
        if not _SERIAL_AVAILABLE:
            return
        port = self._port or self._auto_detect()
        if not port:
            logger.warning(
                "LED: Kein ESP32 gefunden — Serial deaktiviert. "
                "Tipp: ARCADE_SERIAL_PORT=/dev/ttyACM0 setzen."
            )
            return
        try:
            conn = serial.Serial(port, self._baud, timeout=1)
            with self._lock:
                self._conn = conn
                self._port = port
            logger.info("LED: Serial verbunden → %s @ %d Baud", port, self._baud)
            threading.Thread(target=self._reader, daemon=True, name="LED-SerialRX").start()
        except Exception as exc:
            logger.warning("LED: Serial-Verbindung fehlgeschlagen (%s): %s", port, exc)

    def _reconnect_loop(self) -> None:
        while self._running:
            time.sleep(5)
            if not self.is_connected and _SERIAL_AVAILABLE:
                logger.info("LED: Serial getrennt — Reconnect...")
                self._connect()

    def _reader(self) -> None:
        """Empfängt und loggt ESP32-Antworten (Heartbeat, Fehler)."""
        while self._running:
            with self._lock:
                conn_ref = self._conn
            if not conn_ref or not conn_ref.is_open:
                break
            try:
                raw = conn_ref.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("status") == "ready":
                    logger.info(
                        "ESP32 bereit — v%s | Kette A: %d LEDs",
                        data.get("version", "?"), data.get("leds_a", 0),
                    )
                elif data.get("status") == "error":
                    logger.error(
                        "ESP32-Fehler [%s]: %s",
                        data.get("code", "?"), data.get("msg", ""),
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as exc:
                logger.error("LED: Serial-Reader unerwartet beendet: %s", exc)
                break

    def _auto_detect(self) -> Optional[str]:
        for info in serial.tools.list_ports.comports():
            desc = (info.description  or "").lower()
            mfr  = (info.manufacturer or "").lower()
            if any(k in desc or k in mfr for k in self._ESP32_KEYWORDS):
                logger.info("LED: ESP32 gefunden auf %s (%s)", info.device, info.description)
                return info.device
        return None


# ─────────────────────────────────────────────────────────────────────────────
# EffectDispatcher
# ─────────────────────────────────────────────────────────────────────────────

class EffectDispatcher:
    """
    Verteilt LED-Effekte an den SerialTransport.
    Verwaltet Prioritäten, Segment-Auflösung und den Keepalive-Mechanismus.
    """

    _PRIORITY_LABELS = {PRIORITY_LOW: "LOW", PRIORITY_MEDIUM: "MED", PRIORITY_HIGH: "HIGH"}

    def __init__(self, transport: SerialTransport) -> None:
        self._transport        = transport
        self._priority         = 0
        self._priority_lock    = threading.Lock()
        self._keepalive_effects: List[dict] = []
        self._keepalive_lock   = threading.Lock()
        self._keepalive_active = False
        self._is_recording     = False
        self._running          = False

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._keepalive_loop, daemon=True, name="LED-Keepalive").start()

    def stop(self) -> None:
        self._running = False

    def reset_priority(self) -> None:
        with self._priority_lock:
            self._priority = 0

    def enable_keepalive(self, active: bool) -> None:
        self._keepalive_active = active

    def begin_record(self) -> None:
        """Startet Aufzeichnung der nächsten Effekte für den Keepalive."""
        with self._keepalive_lock:
            self._keepalive_effects.clear()
        self._is_recording = True

    def end_record(self) -> None:
        self._is_recording = False

    def clear_keepalive(self) -> None:
        with self._keepalive_lock:
            self._keepalive_effects.clear()

    def send(self, fx: EffectDef, r: int, g: int, b: int) -> None:
        """Sendet Effekt nach Prioritätsprüfung. Zeichnet ggf. für Keepalive auf."""
        indices   = self._resolve_segments(fx.segments)
        seg_names = [fx.segments] if isinstance(fx.segments, str) else list(fx.segments)
        if not indices:
            return

        with self._priority_lock:
            if fx.priority < self._priority:
                logger.debug(
                    "LED: %s auf '%s' blockiert (Prio %s < %s)",
                    fx.effect_type, ",".join(seg_names),
                    self._PRIORITY_LABELS.get(fx.priority, fx.priority),
                    self._PRIORITY_LABELS.get(self._priority, self._priority),
                )
                return
            self._priority = fx.priority

        logger.info(
            "LED [A] | %-7s | %-40s | rgb(%3d,%3d,%3d) | speed=%-3d repeat=%d",
            fx.effect_type, ",".join(seg_names), r, g, b, fx.speed, fx.repeat,
        )
        payload = {
            "cmd":      "effect",
            "chain":    "A",
            "type":     fx.effect_type,
            "segment":  indices[0] if len(indices) == 1 else indices,
            "color":    {"r": r, "g": g, "b": b},
            "speed":    fx.speed,
            "length":   fx.length,
            "repeat":   fx.repeat,
            "priority": fx.priority,
        }
        if self._is_recording:
            with self._keepalive_lock:
                self._keepalive_effects.append(dict(payload))
        self._transport.write(payload)

    def send_direct(self, fx: EffectDef, r: int = 0, g: int = 0, b: int = 0) -> None:
        """Sendet Effekt ohne Prioritätsprüfung (Power-Down, Takeover)."""
        indices = self._resolve_segments(fx.segments)
        if not indices:
            return
        self._transport.write({
            "cmd":      "effect",
            "chain":    "A",
            "type":     fx.effect_type,
            "segment":  indices[0] if len(indices) == 1 else indices,
            "color":    {"r": r, "g": g, "b": b},
            "speed":    fx.speed,
            "length":   fx.length,
            "repeat":   1,
            "priority": PRIORITY_HIGH,
        })

    def send_all_off(self) -> None:
        self._transport.write({
            "cmd": "effect", "chain": "A", "type": "off",
            "segment": 99, "priority": PRIORITY_HIGH,
        })

    def _keepalive_loop(self) -> None:
        """Re-sendet Launcher-Zustand alle 1.5 s mit HIGH-Prio."""
        while self._running:
            time.sleep(1.5)
            if not self._keepalive_active:
                continue
            with self._keepalive_lock:
                cmds = list(self._keepalive_effects)
            if not cmds:
                continue
            logger.debug("LED: Keepalive — %d Effekte re-assertiert (HIGH)", len(cmds))
            for cmd in cmds:
                override = dict(cmd)
                override["priority"] = PRIORITY_HIGH
                self._transport.write(override)

    @staticmethod
    def _resolve_segments(segments: Union[str, List[str]]) -> List[int]:
        names = [segments] if isinstance(segments, str) else segments
        result = []
        for name in names:
            if name in SEGMENTS:
                result.append(SEGMENTS[name])
            else:
                logger.debug("LED: Unbekanntes Segment: %s", name)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# AttractMode
# ─────────────────────────────────────────────────────────────────────────────

class AttractMode:
    """
    Steuert den Attract-Mode: Farbrotation durch Spielfarben bei Inaktivität.
    Wechselt alle 4 Sekunden die Farbe, aktiviert sich nach idle_timeout Sekunden.
    """

    def __init__(self, dispatcher: EffectDispatcher, idle_timeout: int = _ATTRACT_IDLE_TIMEOUT) -> None:
        self._dispatcher       = dispatcher
        self._idle_timeout     = idle_timeout
        self._active           = True
        self._suspended        = False
        self._color_index      = 0
        self._last_interaction = 0.0
        self._event            = threading.Event()
        self._running          = False

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="LED-Attract").start()

    def stop(self) -> None:
        self._running = False
        self._event.set()

    def activate(self) -> None:
        """Aktiviert den Attract-Mode sofort und hebt eine Suspension auf."""
        self._suspended   = False
        self._active      = True
        self._color_index = 0
        self._event.set()

    def deactivate(self) -> None:
        """Deaktiviert den Attract-Mode temporär — Idle-Reaktivierung bleibt möglich."""
        self._active = False
        self._event.set()

    def suspend(self) -> None:
        """Sperrt den Attract-Mode hart — keine automatische Reaktivierung bis activate()."""
        self._suspended = True
        self._active    = False
        self._event.set()

    def notify_interaction(self) -> None:
        """Setzt den Inaktivitäts-Timer zurück und deaktiviert den Attract-Mode."""
        self._last_interaction = time.time()
        self.deactivate()

    def _loop(self) -> None:
        while self._running:
            self._event.clear()

            if not self._active:
                if self._suspended:
                    self._event.wait(timeout=1.0)
                    continue
                idle = time.time() - self._last_interaction
                if self._last_interaction > 0 and idle >= self._idle_timeout:
                    self._active = True
                    self._color_index = 0
                    self._dispatcher.reset_priority()
                    logger.info("LED: Attract-Mode nach %.0fs Inaktivität aktiviert", idle)
                else:
                    self._event.wait(timeout=1.0)
                    continue

            r, g, b = GAME_COLORS[_COLOR_CYCLE[self._color_index % len(_COLOR_CYCLE)]]
            self._dispatcher.reset_priority()
            self._dispatcher.begin_record()
            self._dispatcher.send(FX_ATTRACT, r, g, b)
            self._dispatcher.end_record()

            self._event.wait(timeout=4.0)
            if self._active:
                self._color_index += 1


# ─────────────────────────────────────────────────────────────────────────────
# GameWebSocketServer
# ─────────────────────────────────────────────────────────────────────────────

class GameWebSocketServer:
    """
    WebSocket-Server für Spiele (Godot, JS, Python).
    Empfängt Effekt-Kommandos und leitet sie direkt an den ESP32 weiter.
    """

    def __init__(
        self,
        transport: SerialTransport,
        host: str = _WS_HOST,
        port: int = _WS_PORT,
    ) -> None:
        self._transport = transport
        self._host      = host
        self._port      = port
        self._clients:  Set = set()
        self._loop      = asyncio.new_event_loop()
        self._running   = False

    @property
    def address(self) -> str:
        return f"ws://{self._host}:{self._port}"

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._run_loop, daemon=True, name="LED-WSServer").start()
        time.sleep(0.3)

    def stop(self) -> None:
        self._running = False
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self) -> None:
        try:
            self._loop.run_until_complete(self._serve())
        except RuntimeError:
            pass  # loop.stop() während run_until_complete() — erwartet beim Shutdown

    async def _serve(self) -> None:
        if not _WS_AVAILABLE:
            return
        while self._running:
            try:
                async with websockets.serve(self._handle_client, self._host, self._port):
                    logger.info("LED-WS: Server bereit auf %s", self.address)
                    while self._running:
                        await asyncio.sleep(0.5)
            except Exception as exc:
                logger.warning("LED-WS: Server-Fehler: %s — Retry in 5s", exc)
                await asyncio.sleep(5)

    async def _handle_client(self, websocket) -> None:
        addr = getattr(websocket, "remote_address", "?")
        self._clients.add(websocket)
        logger.info("LED-WS: Spiel verbunden: %s", addr)
        try:
            async for message in websocket:
                self._forward(message)
        except Exception as exc:
            logger.debug("LED-WS: Client-Verbindungsfehler (%s): %s", addr, exc)
        finally:
            self._clients.discard(websocket)
            logger.info("LED-WS: Spiel getrennt: %s", addr)

    def _forward(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        if data.get("cmd") != "effect":
            return
        color = data.get("color", {})
        if isinstance(color, dict):
            data["color"] = {
                "r": self._clamp(color.get("r", 0)),
                "g": self._clamp(color.get("g", 0)),
                "b": self._clamp(color.get("b", 0)),
            }
        self._transport.write(data)
        logger.debug("LED-WS: Spiel-Effekt → ESP32: %s", str(data)[:60])

    @staticmethod
    def _clamp(value) -> int:
        return max(0, min(255, int(value)))


# ─────────────────────────────────────────────────────────────────────────────
# LEDBridge — öffentliche Fassade
# ─────────────────────────────────────────────────────────────────────────────

class LEDBridge:
    """
    Öffentliche Fassade für die gesamte LED-Infrastruktur.
    Koordiniert SerialTransport, EffectDispatcher, AttractMode und GameWebSocketServer.
    """

    def __init__(
        self,
        serial_port:     Optional[str] = _SERIAL_PORT,
        serial_baud:     int           = _SERIAL_BAUD,
        ws_host:         str           = _WS_HOST,
        ws_port:         int           = _WS_PORT,
        attract_timeout: int           = _ATTRACT_IDLE_TIMEOUT,
    ) -> None:
        self._transport  = SerialTransport(serial_port, serial_baud)
        self._dispatcher = EffectDispatcher(self._transport)
        self._attract    = AttractMode(self._dispatcher, attract_timeout)
        self._ws_server  = GameWebSocketServer(self._transport, ws_host, ws_port)

    def start(self) -> None:
        """Bridge starten — einmalig beim Launcher-Init aufrufen."""
        self._transport.start()
        self._dispatcher.start()
        self._ws_server.start()
        self._attract.start()
        logger.info(
            "LEDBridge: gestartet | Serial: %s | WS: %s",
            self._transport.port or "auto-detect",
            self._ws_server.address,
        )

    def stop(self, send_all_off: bool = True) -> None:
        """Bridge sauber beenden."""
        self._attract.stop()
        self._dispatcher.stop()
        if send_all_off:
            self._dispatcher.send_all_off()
        time.sleep(0.5)
        self._ws_server.stop()
        self._transport.stop()
        logger.info("LEDBridge: gestoppt.")

    # ── Launcher-API ──────────────────────────────────────────────────────────

    def notify_selection_changed(self, game_name: str) -> None:
        """W/S im Menü: Spielfarbe auf allen Segmenten anzeigen."""
        self._attract.notify_interaction()
        self._dispatcher.reset_priority()
        self._dispatcher.enable_keepalive(True)
        r, g, b = self._game_color(game_name)
        self._dispatcher.begin_record()
        self._dispatcher.send(FX_SELECT_GAME, r, g, b)
        self._dispatcher.end_record()

    def notify_game_start(self, game_name: str) -> None:
        """Vor Spielstart: weißer Blitz-Fill."""
        logger.info("LED: Spielstart — %s", game_name)
        self._attract.suspend()
        self._dispatcher.enable_keepalive(False)
        self._dispatcher.clear_keepalive()
        self._dispatcher.reset_priority()
        self._dispatcher.send(FX_START_FLASH, 255, 255, 255)

    def notify_game_stop(self) -> None:
        """Nach Spielende: Takeover → Attract-Mode neu starten."""
        self._dispatcher.reset_priority()
        self._dispatcher.send_all_off()
        self._dispatcher.enable_keepalive(True)
        self._attract.activate()
        logger.info("LEDBridge: Attract-Mode neugestartet.")

    def notify_launcher_exit(self) -> None:
        """Power-Down-Animation, dann alles aus."""
        logger.info("LED: Launcher-Exit — Power-Down-Animation...")
        self._attract.deactivate()
        self._dispatcher.enable_keepalive(False)
        self._dispatcher.clear_keepalive()
        self._dispatcher.reset_priority()
        self._dispatcher.send_all_off()
        time.sleep(0.1)
        self._dispatcher.send_direct(FX_SHUTDOWN_WIPE)
        self._dispatcher.send_direct(FX_SHUTDOWN_FILL)
        time.sleep(0.1)
        self.stop()

    @property
    def is_connected(self) -> bool:
        return self._transport.is_connected

    # ── Hilfsfunktionen ───────────────────────────────────────────────────────

    @staticmethod
    def _game_color(game_name: str) -> Tuple[int, int, int]:
        key = game_name.lower().replace(" ", "_").replace("-", "_")
        return GAME_COLORS.get(key, (255, 255, 255))


# ── Singleton-Accessor ────────────────────────────────────────────────────────

_bridge_instance: Optional[LEDBridge] = None

def get_bridge() -> LEDBridge:
    """Globale LEDBridge-Instanz (lazy init)."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = LEDBridge()
    return _bridge_instance
