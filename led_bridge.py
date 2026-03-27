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
  marquee=0 | monitor_right=1 | monitor_bottom=2
  monitor_left=3 | monitor_top=4 | control_panel=5 | alle=99

Kette B (Ambient/Gehäuse):
  side_left=0 | bottom=1 | side_right=2 | alle=99
"""

import asyncio
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

try:
    import serial
    import serial.tools.list_ports
    _SERIAL_OK = True
except ImportError:
    _SERIAL_OK = False
    logging.warning("LED: pyserial nicht installiert — Hardware-LEDs deaktiviert.")

try:
    import websockets
    _WS_OK = True
except ImportError:
    _WS_OK = False
    logging.warning("LED: websockets nicht installiert — Spiel-LED-Integration deaktiviert.")

logger = logging.getLogger(__name__)

# --- Konfiguration -----------------------------------------------------------

# Serial-Port: Umgebungsvariable ARCADE_SERIAL_PORT oder Auto-Detect
# Manuell setzen: ARCADE_SERIAL_PORT=COM3 (Windows) oder /dev/ttyUSB0 (Linux)
_SERIAL_PORT = os.environ.get("ARCADE_SERIAL_PORT", None)   # None = auto-detect
_SERIAL_BAUD = 115_200
_WS_HOST     = "localhost"
_WS_PORT     = 8765

# --- Segment-Mapping ---------------------------------------------------------

SEGMENT_MAP: Dict[str, Tuple[str, int]] = {
    "marquee":        ("A", 0),
    "monitor_right":  ("A", 1),
    "monitor_bottom": ("A", 2),
    "monitor_left":   ("A", 3),
    "monitor_top":    ("A", 4),
    "control_panel":  ("A", 5),
    "all_a":          ("A", 99),
    "side_left":      ("B", 0),
    "bottom":         ("B", 1),
    "side_right":     ("B", 2),
    "all_b":          ("B", 99),
}

SEGMENT_ALIASES: Dict[str, List[str]] = {
    "monitor": ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"],
    "sides":   ["side_left", "side_right"],
}

# --- Spielfarben -------------------------------------------------------------

GAME_COLORS: Dict[str, Tuple[int, int, int]] = {
    "pac-man":        (255, 255, 0),
    "space_invaders": (57,  255, 20),
    "asteroids":      (0,   255, 255),
}
_COLOR_CYCLE = ["pac-man", "space_invaders", "asteroids"]

# --- Prioritäten -------------------------------------------------------------

PRIORITY_LOW    = 1   # Attract-Mode, Idle
PRIORITY_MEDIUM = 2   # Selektion, Treffer, Bonus
PRIORITY_HIGH   = 3   # Spielstart, Game Over, Tod


# --- LED Bridge --------------------------------------------------------------

class LEDBridge:
    """
    Eigenständige LED-Bridge: steuert ESP32 via Serial und stellt
    WebSocket-Server für Spiele bereit. Läuft in Daemon-Threads.
    """

    def __init__(
        self,
        serial_port: Optional[str] = _SERIAL_PORT,
        serial_baud: int           = _SERIAL_BAUD,
        ws_host: str               = _WS_HOST,
        ws_port: int               = _WS_PORT,
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

        # ── Prioritäts-Tracking pro Kette ─────────────────────────────────────
        self._cur_prio: Dict[str, int] = {"A": 0, "B": 0}
        self._prio_lock = threading.Lock()

        # ── Attract-Mode State ────────────────────────────────────────────────
        self._attract_active  = True
        self._attract_start   = time.time()
        self._attract_phase   = "soft_idle"   # "soft_idle" | "active_attract"
        self._attract_color_i = 0
        self._attract_event   = threading.Event()

        # ── Launcher-Lock + Keepalive ─────────────────────────────────────────
        self._launcher_locked     = True
        self._locked_effects: List[dict] = []
        self._locked_effects_lock = threading.Lock()
        self._locked_recording    = False

        self._current_game: Optional[str] = None
        self._running = False

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def start(self):
        """Bridge starten — einmalig beim Launcher-Init aufrufen."""
        self._running = True
        self._connect_serial()
        self._loop_thread.start()
        time.sleep(0.3)
        threading.Thread(target=self._attract_loop,   daemon=True, name="LED-Attract").start()
        threading.Thread(target=self._keepalive_loop, daemon=True, name="LED-Keepalive").start()
        logger.info(
            "LEDBridge: gestartet | Serial: %s | WS: ws://%s:%d",
            self._serial_port or "auto-detect", self._ws_host, self._ws_port,
        )

    def stop(self):
        """Sauber beenden — alle LEDs aus, Threads stoppen."""
        self._running = False
        self._attract_event.set()
        self._send_all_off()
        time.sleep(0.5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._serial and self._serial.is_open:
            self._serial.close()
        logger.info("LEDBridge: gestoppt.")

    # ── Öffentliche Launcher-API ──────────────────────────────────────────────

    def notify_selection_changed(self, game_name: str):
        """Beim Navigieren im Menü (W/S): Spielfarbe anzeigen."""
        self._attract_active  = False
        self._launcher_locked = True
        self._attract_event.set()

        r, g, b = self._game_color(game_name)
        self._reset_prio()
        with self._locked_effects_lock:
            self._locked_effects.clear()

        self._locked_recording = True
        self._effect("pulse",   "marquee",       r, g, b, speed=50, priority=PRIORITY_MEDIUM)
        self._effect("wipe",    "control_panel", r, g, b, speed=35, priority=PRIORITY_MEDIUM)
        for seg in ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"]:
            self._effect("fill", seg, r, g, b, priority=PRIORITY_MEDIUM)
        self._effect("chase",   "side_left",  r, g, b, speed=25, priority=PRIORITY_MEDIUM)
        self._effect("chase",   "side_right", r, g, b, speed=25, priority=PRIORITY_MEDIUM)
        self._effect("rainbow", "bottom",     0, 0, 0, speed=15, priority=PRIORITY_MEDIUM)
        self._locked_recording = False

    def notify_game_start(self, game_name: str):
        """Vor dem Spielstart: weißes Blitz-Fill (HIGH), dann Spiel-Ambient."""
        self._current_game    = game_name
        self._attract_active  = False
        self._launcher_locked = False        # Spiel übernimmt Kontrolle
        with self._locked_effects_lock:
            self._locked_effects.clear()
        self._attract_event.set()
        self._reset_prio()

        white = (255, 255, 255)
        for seg in ["marquee", "monitor_right", "monitor_bottom",
                    "monitor_left", "monitor_top", "control_panel"]:
            self._effect("fill", seg, *white, repeat=1, priority=PRIORITY_HIGH)
        for seg in ["side_left", "bottom", "side_right"]:
            self._effect("fill", seg, *white, repeat=1, priority=PRIORITY_HIGH)

        def _delayed_ambient():
            time.sleep(1.0)
            if self._current_game != game_name:
                return
            r, g, b = self._game_color(game_name)
            self._reset_prio()
            self._effect("pulse",   "marquee",       r, g, b, speed=30, priority=PRIORITY_MEDIUM)
            self._effect("fill",    "control_panel", r, g, b,            priority=PRIORITY_MEDIUM)
            for seg in ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"]:
                self._effect("blink", seg, r, g, b, speed=80, priority=PRIORITY_MEDIUM)
            self._effect("rainbow", "side_left",  0, 0, 0, speed=20, priority=PRIORITY_LOW)
            self._effect("rainbow", "side_right", 0, 0, 0, speed=20, priority=PRIORITY_LOW)
            self._effect("pulse",   "bottom",     r, g, b, speed=15, priority=PRIORITY_LOW)

        threading.Thread(target=_delayed_ambient, daemon=True).start()

    def notify_game_stop(self):
        """Nach Spielende: sofortiger Takeover, dann Attract-Mode neu starten."""
        self._current_game    = None
        self._launcher_locked = True
        self._force_takeover()
        self._attract_active  = True
        self._attract_start   = time.time()
        self._attract_phase   = "soft_idle"
        self._attract_color_i = 0
        self._reset_prio()
        self._attract_event.set()
        logger.info("LEDBridge: Attract-Mode neugestartet.")

    def notify_launcher_exit(self):
        """Sauberer Exit: Power-Down-Animation, dann alle LEDs aus."""
        logger.info("LED: Launcher-Exit — Power-Down-Animation...")
        self._attract_active = False
        self._attract_event.set()
        self._reset_prio()
        for seg in ["marquee", "control_panel"]:
            self._write_serial_direct("wipe", seg, speed=55)
        for seg in ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"]:
            self._write_serial_direct("fill", seg)
        for seg in ["side_left", "bottom", "side_right"]:
            self._write_serial_direct("wipe", seg, speed=40)
        time.sleep(0.6)
        self.stop()

    def is_connected(self) -> bool:
        """True wenn ESP32 via Serial verbunden."""
        return self._serial is not None and self._serial.is_open

    # ── Interne Effekt-Logik ──────────────────────────────────────────────────

    _PRIO_NAMES = {PRIORITY_LOW: "LOW", PRIORITY_MEDIUM: "MED", PRIORITY_HIGH: "HIGH"}

    def _effect(
        self,
        effect_type: str,
        segment: str,
        r: int, g: int, b: int,
        speed: int = 50,
        length: int = 5,
        repeat: int = 0,
        brightness: int = 255,
        priority: int = PRIORITY_LOW,
    ):
        """Prioritätsprüfung → Alias expandieren → Serial senden."""
        if segment in SEGMENT_ALIASES:
            for real_seg in SEGMENT_ALIASES[segment]:
                self._effect(effect_type, real_seg, r, g, b,
                             speed, length, repeat, brightness, priority)
            return

        if segment not in SEGMENT_MAP:
            logger.debug("LED: Unbekanntes Segment: %s", segment)
            return

        chain, seg_idx = SEGMENT_MAP[segment]

        with self._prio_lock:
            if priority < self._cur_prio.get(chain, 0):
                logger.debug(
                    "LED: [%s] %s auf '%s' blockiert (Prio %s < %s)",
                    chain, effect_type, segment,
                    self._PRIO_NAMES.get(priority, priority),
                    self._PRIO_NAMES.get(self._cur_prio[chain], self._cur_prio[chain]),
                )
                return
            self._cur_prio[chain] = priority

        logger.info(
            "LED %-4s | %-7s | %-16s | rgb(%3d,%3d,%3d) | speed=%-3d repeat=%d",
            f"[{chain}]", effect_type, segment, r, g, b, speed, repeat,
        )
        payload = {
            "cmd":        "effect",
            "chain":      chain,
            "type":       effect_type,
            "segment":    seg_idx,
            "color":      {"r": r, "g": g, "b": b},
            "speed":      speed,
            "length":     length,
            "repeat":     repeat,
            "brightness": brightness,
            "priority":   priority,
        }
        if self._locked_recording:
            with self._locked_effects_lock:
                self._locked_effects.append(dict(payload))
        self._write_serial(payload)

    def _send_all_off(self):
        for seg, (chain, idx) in SEGMENT_MAP.items():
            if idx == 99:
                continue
            self._write_serial({
                "cmd": "effect", "chain": chain, "type": "off",
                "segment": idx, "priority": PRIORITY_HIGH,
            })

    def _write_serial_direct(self, effect: str, segment: str, speed: int = 50):
        """Hilfsmethode: Segment schwarz/aus setzen (bypasses priority check)."""
        if segment not in SEGMENT_MAP:
            return
        chain, idx = SEGMENT_MAP[segment]
        self._write_serial({
            "cmd": "effect", "chain": chain, "type": effect,
            "segment": idx, "color": {"r": 0, "g": 0, "b": 0},
            "speed": speed, "repeat": 1, "priority": PRIORITY_HIGH,
        })

    def _force_takeover(self):
        """Sofortiger HIGH-Takeover: überschreibt alle Spiel-Effekte auf dem ESP32."""
        logger.info("LED: Launcher-Takeover — alle Spiel-Effekte überschrieben (HIGH)")
        for seg, (chain, idx) in SEGMENT_MAP.items():
            if idx == 99:
                continue
            self._write_serial({
                "cmd": "effect", "chain": chain, "type": "off",
                "segment": idx, "priority": PRIORITY_HIGH,
            })

    def _keepalive_loop(self):
        """Re-sendet Launcher-Zustand alle 1.5 s mit HIGH-Prio (überschreibt Spiel-Effekte)."""
        while self._running:
            time.sleep(1.5)
            if not self._launcher_locked:
                continue
            with self._locked_effects_lock:
                cmds = list(self._locked_effects)
            if not cmds:
                continue
            logger.debug("LED: Keepalive — %d Effekte re-assertiert (HIGH)", len(cmds))
            for cmd in cmds:
                override = dict(cmd)
                override["priority"] = PRIORITY_HIGH
                self._write_serial(override)

    def _reset_prio(self):
        with self._prio_lock:
            self._cur_prio = {"A": 0, "B": 0}

    # ── Attract-Mode (Daemon-Thread) ──────────────────────────────────────────

    def _attract_loop(self):
        while self._running:
            self._attract_event.clear()
            if not self._attract_active:
                self._attract_event.wait(timeout=1.0)
                continue

            elapsed   = time.time() - self._attract_start
            new_phase = "active_attract" if elapsed >= 300 else "soft_idle"
            if new_phase != self._attract_phase:
                self._attract_phase = new_phase
                self._reset_prio()
                logger.info("LEDBridge Attract: → %s", new_phase)

            r, g, b = GAME_COLORS[_COLOR_CYCLE[self._attract_color_i % 3]]
            self._reset_prio()

            with self._locked_effects_lock:
                self._locked_effects.clear()
            self._locked_recording = True

            if self._attract_phase == "soft_idle":
                self._attract_soft_idle(r, g, b)
                self._locked_recording = False
                self._attract_event.wait(timeout=2.0)
            else:
                self._attract_active_attract()
                self._locked_recording = False
                self._attract_event.wait(timeout=2.0)
                if self._attract_active:
                    self._attract_color_i += 1

    def _attract_soft_idle(self, r: int, g: int, b: int):
        """0–5 Min: sanftes Pulsieren in Spielfarbe + langsamer Rainbow Ambient."""
        for seg in ["marquee", "monitor_right", "monitor_bottom",
                    "monitor_left", "monitor_top", "control_panel"]:
            self._effect("pulse", seg, r, g, b, speed=15, priority=PRIORITY_LOW)
        for seg in ["side_left", "bottom", "side_right"]:
            self._effect("rainbow", seg, 0, 0, 0, speed=8, priority=PRIORITY_LOW)

    def _attract_active_attract(self):
        """5+ Min: Spielfarben rotieren auf A, Chase auf Ambient-Seiten."""
        i          = self._attract_color_i
        r1, g1, b1 = GAME_COLORS[_COLOR_CYCLE[i % 3]]
        r2, g2, b2 = GAME_COLORS[_COLOR_CYCLE[(i + 1) % 3]]
        self._effect("rainbow", "marquee",       0,  0,  0,  speed=40, priority=PRIORITY_LOW)
        self._effect("chase",   "control_panel", r1, g1, b1, speed=45, priority=PRIORITY_LOW)
        for seg in ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"]:
            self._effect("chase", seg, r1, g1, b1, speed=55, priority=PRIORITY_LOW)
        self._effect("chase",   "side_left",  r2, g2, b2, speed=30, priority=PRIORITY_LOW)
        self._effect("chase",   "side_right", r2, g2, b2, speed=30, priority=PRIORITY_LOW)
        self._effect("sparkle", "bottom",     r1, g1, b1, speed=60, priority=PRIORITY_LOW)

    # ── Serial-Kommunikation ──────────────────────────────────────────────────

    def _connect_serial(self):
        if not _SERIAL_OK:
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
        if not _SERIAL_OK:
            return None
        keywords = ("cp210", "ch340", "esp32", "uart", "usb serial",
                    "usb-serial", "silicon labs")
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            mfg  = (p.manufacturer or "").lower()
            if any(k in desc or k in mfg for k in keywords):
                logger.info("LED: ESP32 gefunden auf %s (%s)", p.device, p.description)
                return p.device
        return None

    def _write_serial(self, payload: dict):
        """Thread-sicher JSON an ESP32 senden."""
        if not self._serial or not self._serial.is_open:
            return
        try:
            data = json.dumps(payload, separators=(",", ":")) + "\n"
            with self._serial_lock:
                self._serial.write(data.encode("utf-8"))
        except Exception as exc:
            logger.warning("LED: Serial-Schreibfehler: %s", exc)

    def _serial_reader(self):
        """ESP32-Antworten empfangen: Heartbeat + NACK."""
        while self._running and self._serial and self._serial.is_open:
            try:
                raw = self._serial.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("status") == "ready":
                    logger.info(
                        "ESP32 bereit — v%s | Kette A: %d LEDs | Kette B: %d LEDs",
                        data.get("version", "?"),
                        data.get("leds_a", 0),
                        data.get("leds_b", 0),
                    )
                elif data.get("status") == "error":
                    logger.error(
                        "ESP32-Fehler [%s]: %s",
                        data.get("code", "?"),
                        data.get("msg", ""),
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception:
                break

    # ── WebSocket-Server (für Spiele) ─────────────────────────────────────────

    def _run_ws_loop(self):
        self._loop.run_until_complete(self._ws_serve())

    async def _ws_serve(self):
        if not _WS_OK:
            return
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
            logger.warning("LED-WS: Server-Fehler: %s", exc)

    async def _handle_game_client(self, websocket):
        addr = getattr(websocket, "remote_address", "?")
        self._ws_clients.add(websocket)
        logger.info("LED-WS: Spiel verbunden: %s", addr)
        try:
            async for message in websocket:
                await self._handle_game_message(message, websocket)
        except Exception:
            pass
        finally:
            self._ws_clients.discard(websocket)
            logger.info("LED-WS: Spiel getrennt: %s", addr)

    async def _handle_game_message(self, message: str, websocket):
        """Spiel-Effektbefehle validieren und (wenn nicht gesperrt) an ESP32 senden."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        command = data.get("cmd")

        # attract/lock sind bridge-intern — nie an ESP32 weiterleiten
        if command in ("attract", "lock"):
            return

        if command != "effect":
            return

        # Wenn Launcher gesperrt: Spiel-Effekte blockieren
        if self._launcher_locked:
            logger.debug(
                "LED-WS: Spiel-Effekt von %s blockiert (Launcher gesperrt)", addr
            )
            return

        # Spiel-Effekt direkt an ESP32 weiterleiten
        self._write_serial(data)
        logger.debug("LED-WS: Spiel-Effekt → ESP32: %s", str(data)[:60])

    # ── Hilfsfunktionen ───────────────────────────────────────────────────────

    @staticmethod
    def _game_color(game_name: str) -> Tuple[int, int, int]:
        n = game_name.lower()
        if "pac" in n:
            return GAME_COLORS["pac-man"]
        if "space" in n or "invader" in n:
            return GAME_COLORS["space_invaders"]
        if "asteroid" in n:
            return GAME_COLORS["asteroids"]
        return (255, 255, 255)


# ── Singleton-Accessor ────────────────────────────────────────────────────────

_bridge_instance: Optional[LEDBridge] = None

def get_bridge() -> LEDBridge:
    """Globale LEDBridge-Instanz (lazy init)."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = LEDBridge()
    return _bridge_instance
