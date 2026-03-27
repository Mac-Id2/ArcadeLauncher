"""
led_bridge.py

WebSocket-Client zwischen dem Arcade-Launcher und der LED Bridge (bridge.py).

bridge.py läuft als eigenständiger Prozess und verwaltet die Serial-Verbindung
zum ESP32. Dieser Client verbindet sich via WebSocket und sendet Effekt-Befehle:

  {"cmd":"effect","chain":"A","type":"chase","segment":0,
   "color":{"r":255,"g":200,"b":0},"speed":50,"repeat":1,"priority":2}

Attract-Mode-Steuerung:
  {"cmd":"attract","state":"pause"}
  {"cmd":"attract","state":"resume"}

Launcher-Lock (ws_server.py muss dies implementieren):
  {"cmd":"lock","active":true}   → bridge blockiert alle Spiel-Effekte
  {"cmd":"lock","active":false}  → bridge gibt Spiel-Effekte wieder frei

Segment-Mapping:
  Kette A  marquee=0 | monitor_right=1 | monitor_bottom=2
           monitor_left=3 | monitor_top=4 | control_panel=5 | alle=99
  Kette B  side_left=0 | bottom=1 | side_right=2 | alle=99
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

try:
    import websockets
    _WS_OK = True
except ImportError:
    _WS_OK = False
    logging.warning("LED: websockets nicht installiert — LED-Effekte deaktiviert.")

logger = logging.getLogger(__name__)

# --- Segment-Mapping ---------------------------------------------------------

# Segment-Name → (chain, integer index)
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

# Gruppen-Aliase → Liste echter Segment-Namen
SEGMENT_ALIASES: Dict[str, List[str]] = {
    "monitor": ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"],
    "sides":   ["side_left", "side_right"],
}

# --- Spielfarben (RGB-Tupel) --------------------------------------------------

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


# --- LED Bridge (WebSocket-Client) -------------------------------------------

class LEDBridge:
    """
    Verbindet sich als WebSocket-Client mit bridge.py (ws://localhost:8765).
    Sendet Effekt-Befehle und steuert den Attract-Mode lokal.
    Läuft vollständig in Daemon-Threads — der Launcher wird nicht blockiert.
    """

    def __init__(self, url: str = "ws://localhost:8765"):
        self._url  = url
        self._ws: Optional[object] = None

        # Eigener asyncio-Loop im Daemon-Thread
        self._loop        = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop, daemon=True, name="LED-AsyncLoop"
        )

        # Prioritäts-Tracking pro Kette (A / B), unabhängig
        self._cur_prio: Dict[str, int] = {"A": 0, "B": 0}
        self._prio_lock = threading.Lock()

        # Attract-Mode State
        self._attract_active  = True
        self._attract_start   = time.time()
        self._attract_phase   = "soft_idle"   # "soft_idle" | "active_attract"
        self._attract_color_i = 0
        self._attract_event   = threading.Event()

        # Launcher-Lock: True solange Menü sichtbar, False während Spiel läuft.
        # Keepalive re-sendet gespeicherte Effekte alle 1.5 s mit HIGH-Prio,
        # damit Spiel-Effekte den Launcher nie überschreiben können.
        self._launcher_locked     = True
        self._locked_effects: List[dict] = []
        self._locked_effects_lock = threading.Lock()
        self._locked_recording    = False   # True während Effekte aufgezeichnet werden

        self._current_game: Optional[str] = None
        self._running = False

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def start(self):
        """Bridge starten — einmalig beim Launcher-Init aufrufen."""
        self._running = True
        self._loop_thread.start()
        time.sleep(0.4)  # kurz auf Verbindungsaufbau warten
        threading.Thread(
            target=self._attract_loop, daemon=True, name="LED-Attract"
        ).start()
        threading.Thread(
            target=self._keepalive_loop, daemon=True, name="LED-Keepalive"
        ).start()
        logger.info("LEDBridge: Client gestartet → %s", self._url)

    def stop(self):
        """Sauber beenden — alle LEDs aus, Verbindung schließen."""
        self._running = False
        self._attract_event.set()
        self._send_all_off()
        time.sleep(0.5)  # sicherstellen dass OFF-Befehle gesendet wurden
        self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("LEDBridge: gestoppt.")

    # ── Öffentliche Launcher-API ──────────────────────────────────────────────

    def notify_selection_changed(self, game_name: str):
        """
        Beim Navigieren im Menü (W/S).
        Zeigt Spielfarbe an, pausiert den Attract-Mode.
        """
        self._attract_active  = False
        self._launcher_locked = True
        self._attract_event.set()
        self._send_attract_cmd("pause")
        self._send_lock_cmd(True)

        r, g, b = self._game_color(game_name)
        self._reset_prio()

        # Effekte aufzeichnen → Keepalive replay
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
        """
        Unmittelbar vor dem Prozess-Start des Spiels aufrufen.
        Kurzes weißes Blitz-Fill (HIGH), dann nach 1 s Spiel-Ambient (MEDIUM).
        """
        self._current_game    = game_name
        self._attract_active  = False
        self._launcher_locked = False          # Spiel übernimmt Kontrolle
        with self._locked_effects_lock:
            self._locked_effects.clear()       # Keepalive pausiert
        self._attract_event.set()
        self._send_attract_cmd("pause")
        self._send_lock_cmd(False)             # Bridge: Spiel-Effekte freigeben
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
        """
        Nach Beenden des Spielprozesses aufrufen.
        Überschreibt sofort alle Spiel-Effekte, startet dann Attract-Mode neu.
        """
        self._current_game    = None
        self._launcher_locked = True
        self._send_lock_cmd(True)          # Bridge: Spiel-Effekte wieder blockieren
        self._force_takeover()             # sofortiger HIGH-Takeover auf dem ESP32
        self._attract_active  = True
        self._attract_start   = time.time()
        self._attract_phase   = "soft_idle"
        self._attract_color_i = 0
        self._reset_prio()
        self._attract_event.set()
        logger.info("LEDBridge: Attract-Mode neugestartet.")

    def notify_launcher_exit(self):
        """
        Sauberer Exit: kurze Power-Down-Animation, dann alle LEDs aus.
        Ersetzt den direkten stop()-Aufruf im Launcher.
        """
        logger.info("LED: Launcher-Exit — Power-Down-Animation...")
        self._attract_active = False
        self._attract_event.set()
        self._reset_prio()

        # Wipe zu Schwarz auf allen Segmenten
        for seg in ["marquee", "control_panel"]:
            self._send_segment_off(seg, effect="wipe", speed=55)
        for seg in ["monitor_right", "monitor_bottom", "monitor_left", "monitor_top"]:
            self._send_segment_off(seg, effect="fill")
        for seg in ["side_left", "bottom", "side_right"]:
            self._send_segment_off(seg, effect="wipe", speed=40)

        time.sleep(0.6)  # Animation ablaufen lassen
        self.stop()

    def _send_segment_off(self, segment: str, effect: str = "fill", speed: int = 50):
        """Hilfsmethode: Einzelnes Segment auf Schwarz setzen (für Exit-Animation)."""
        if segment not in SEGMENT_MAP:
            return
        chain, seg_idx = SEGMENT_MAP[segment]
        self._send_json({
            "cmd": "effect", "chain": chain, "type": effect,
            "segment": seg_idx, "color": {"r": 0, "g": 0, "b": 0},
            "speed": speed, "repeat": 1, "priority": PRIORITY_HIGH,
        })

    def is_connected(self) -> bool:
        return self._ws is not None

    # ── Effekt-Logik (intern) ─────────────────────────────────────────────────

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
        """Prioritätsprüfung → Alias expandieren → JSON an Bridge senden."""
        # Gruppen-Alias expandieren
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
                    "LED: [%s] %s auf '%s' blockiert (Prio %s < laufende %s)",
                    chain, effect_type, segment,
                    self._PRIO_NAMES.get(priority, priority),
                    self._PRIO_NAMES.get(self._cur_prio[chain], self._cur_prio[chain]),
                )
                return  # Niedrigere Priorität wird ignoriert
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
        # Effekt für Keepalive-Replay aufzeichnen
        if self._locked_recording:
            with self._locked_effects_lock:
                self._locked_effects.append(dict(payload))
        self._send_json(payload)

    def _send_all_off(self):
        for seg, (chain, idx) in SEGMENT_MAP.items():
            if idx == 99:
                continue  # all_a / all_b überspringen (einzelne reichen)
            self._send_json({
                "cmd": "effect", "chain": chain, "type": "off",
                "segment": idx, "priority": PRIORITY_HIGH,
            })

    def _send_attract_cmd(self, state: str):
        self._send_json({"cmd": "attract", "state": state})

    def _send_lock_cmd(self, active: bool):
        """
        Teilt bridge.py mit, ob der Launcher die alleinige LED-Kontrolle hat.
        ws_server.py muss {"cmd":"lock","active":bool} implementieren:
          active=True  → alle Effekte von anderen Clients blockieren
          active=False → Effekte von allen Clients durchlassen
        """
        self._send_json({"cmd": "lock", "active": active})

    def _force_takeover(self):
        """
        Sofortiger HIGH-Priorität Takeover: überschreibt alle laufenden
        Spiel-Effekte auf dem ESP32, bypasses den Python-seitigen Prio-Check.
        """
        logger.info("LED: Launcher-Takeover — überschreibe alle Spiel-Effekte (HIGH)")
        for seg, (chain, idx) in SEGMENT_MAP.items():
            if idx == 99:
                continue
            self._send_json({
                "cmd": "effect", "chain": chain, "type": "off",
                "segment": idx, "priority": PRIORITY_HIGH,
            })

    def _keepalive_loop(self):
        """
        Sendet den zuletzt gespeicherten Launcher-Zustand alle 1.5 s mit
        HIGH-Priorität erneut, solange der Launcher die Kontrolle hat.

        Warum nötig: Spiele senden ihre Effekte direkt an bridge.py.
        bridge.py leitet alles weiter zum ESP32 — am Python-Prio-Check vorbei.
        Der Keepalive stellt sicher, dass Launcher-Effekte auf dem ESP32 immer
        die letzte (höchste) Priorität haben — auch ohne bridge.py-Lock-Support.
        """
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
                self._send_json(override)

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
            new_phase = "active_attract" if elapsed >= 300 else "soft_idle"  # 5 Min

            if new_phase != self._attract_phase:
                self._attract_phase = new_phase
                self._reset_prio()
                logger.info("LEDBridge Attract: → %s", new_phase)

            color_name    = _COLOR_CYCLE[self._attract_color_i % 3]
            r, g, b       = GAME_COLORS[color_name]
            self._reset_prio()  # Attract darf immer schreiben

            # Effekte aufzeichnen damit Keepalive sie mit HIGH re-senden kann
            with self._locked_effects_lock:
                self._locked_effects.clear()
            self._locked_recording = True

            if self._attract_phase == "soft_idle":
                self._attract_soft_idle(r, g, b)
                self._locked_recording = False
                self._attract_event.wait(timeout=8.0)
            else:
                self._attract_active_attract()
                self._locked_recording = False
                self._attract_event.wait(timeout=5.0)
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
        """5+ Min: Spielfarben rotieren auf Kette A, Chase auf Ambient-Seiten."""
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

    # ── WebSocket-Client (asyncio) ────────────────────────────────────────────

    def _run_loop(self):
        self._loop.run_until_complete(self._ws_connect_loop())

    async def _ws_connect_loop(self):
        """Verbindet sich mit bridge.py; reconnect bei Verbindungsabbruch."""
        if not _WS_OK:
            return
        while self._running:
            try:
                async with websockets.connect(self._url) as ws:
                    self._ws = ws
                    logger.info("LEDBridge: Verbunden mit %s", self._url)
                    await asyncio.Future()  # Verbindung offen halten
            except Exception as exc:
                self._ws = None
                if self._running:
                    logger.warning(
                        "LEDBridge: Verbindung getrennt (%s) — Retry in 5 s", exc
                    )
                    await asyncio.sleep(5.0)

    def _send_json(self, payload: dict):
        """Thread-sicheres Senden in den asyncio-Loop."""
        if not self._ws or not _WS_OK:
            return
        asyncio.run_coroutine_threadsafe(
            self._ws_send(json.dumps(payload, separators=(",", ":"))),
            self._loop,
        )

    async def _ws_send(self, message: str):
        if self._ws:
            try:
                await self._ws.send(message)
            except Exception as exc:
                logger.debug("LEDBridge: Sende-Fehler: %s", exc)
                self._ws = None

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

def get_bridge(url: str = "ws://localhost:8765") -> LEDBridge:
    """Globale LEDBridge-Instanz (lazy init)."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = LEDBridge(url)
    return _bridge_instance
