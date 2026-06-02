import asyncio
import logging
import threading
import json
import websockets
import time

logger = logging.getLogger(__name__)

class LedController:
    def __init__(self, url: str = "ws://localhost:8765"):
        self._url = url
        self._ws = None
        self._connected_event = threading.Event()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Cooldowns in Sekunden pro Effekttyp zur Spam-Vermeidung
        self._cooldowns = {
            "sparkle": 0.05,
            "pulse": 0.1,
            "wipe": 0.2,
            "blink": 0.05,
            "chase": 0.1,
            "fill": 0.5
        }
        self._last_sent = {}

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_logic())
        except Exception as e:
            logger.warning("[LED-Controller] Asynchroner Loop abgebrochen: %s", e)

    async def _main_logic(self):
        while True:
            try:
                async with websockets.connect(self._url, ping_interval=5, ping_timeout=5) as ws:
                    self._ws = ws
                    self._connected_event.set()
                    logger.info("[LED-Controller] Verbindung erfolgreich aufgebaut zu %s", self._url)
                    await ws.wait_closed()
            except Exception as e:
                logger.debug("[LED-Controller] Verbindungsfehler: %s. Reconnect in 2 Sek...", e)
                self._ws = None
                self._connected_event.clear()
                await asyncio.sleep(2)

    def send_effect(self, chain, effect_type, segment, r, g, b, speed=100, length=5, repeat=1, direction=1, priority=2, event_key=None):
        current_time = time.time()
        cooldown_key = event_key if event_key else effect_type
        cd = self._cooldowns.get(effect_type, 0)

        if cd > 0 and (current_time - self._last_sent.get(cooldown_key, 0) < cd):
            return

        self._last_sent[cooldown_key] = current_time

        payload = {
            "cmd": "effect",
            "chain": chain,
            "type": effect_type,
            "segment": segment,
            "color": {"r": r, "g": g, "b": b},
            "speed": speed,
            "length": length,
            "repeat": repeat,
            "dir": direction,
            "priority": priority,
        }
        self._safe_send(json.dumps(payload))

    def stop(self):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._loop.close()

    def _safe_send(self, message):
        if self._ws and self._connected_event.is_set():
            try:
                async def silent_send():
                    try:
                        if self._ws: await self._ws.send(message)
                    except Exception as e:
                        logger.warning("[LED-Controller] WebSocket Sende-Fehler: %s", e)
                asyncio.run_coroutine_threadsafe(silent_send(), self._loop)
            except Exception as e:
                logger.warning("[LED-Controller] Threadsafe-Fehler beim Queueing: %s", e)


