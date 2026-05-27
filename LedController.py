import asyncio
import threading
import json
import websockets
import time

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
            print(f"[LED-Controller] Asynchroner Loop abgebrochen: {e}")

    async def _main_logic(self):
        while True:
            try:
                async with websockets.connect(self._url, ping_interval=5, ping_timeout=5) as ws:
                    self._ws = ws
                    self._connected_event.set()
                    print(f"[LED-Controller] Verbindung erfolgreich aufgebaut zu {self._url}")
                    await ws.wait_closed()
            except Exception as e:
                print(f"[LED-Controller] Verbindungsfehler: {e}. Reconnect in 2 Sek...")
                self._ws = None
                self._connected_event.clear()
                await asyncio.sleep(2)

    def send_effect(self, chain, effect_type, segment, r, g, b, speed=100, length=5, repeat=1, dir=1, priority=2, event_key=None):
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
            "dir": dir,        
            "priority": priority,
        }
        self._safe_send(json.dumps(payload))

    def attract_pause(self):
        self._safe_send('{"cmd":"attract","state":"pause"}')

    def attract_resume(self):
        self._safe_send('{"cmd":"attract","state":"resume"}')

    def _safe_send(self, message):
        if self._ws and self._connected_event.is_set():
            try:
                async def silent_send():
                    try:
                        if self._ws: await self._ws.send(message)
                    except Exception as e:
                        print(f"[LED-Controller] WebSocket Sende-Fehler: {e}")
                self._loop.call_soon_threadsafe(lambda: asyncio.create_task(silent_send()))
            except Exception as e:
                print(f"[LED-Controller] Threadsafe-Fehler beim Queueing: {e}")

    # ─── LAUNCHER EVENTS ───


    def effect_start_pacman(self):
        """Start Pac-Man: Gelber Chase/Lauflicht-Effekt"""
        self.send_effect(chain="A", effect_type="chase", segment=99, r=255, g=230, b=0, speed=25, length=8, repeat=4, priority=4, event_key="start_pacman")

    def effect_start_space_invaders(self):
        """Start Space Invaders: Grüner Matrix-Wipe-Effekt"""
        self.send_effect(chain="A", effect_type="wipe", segment=99, r=0, g=255, b=0, speed=20, repeat=2, priority=2, event_key="start_si")

    def effect_start_asteroids(self):
        """Start Asteroids: Weißer, kühler Puls-Effekt"""
        self.send_effect(chain="A", effect_type="wipe", segment=99, r=200, g=220, b=255, speed=20, repeat=1, priority=2, event_key="start_asteroids")

    def effect_game_ended(self):
        """Spiel endet: Roter Wipe signalisiert Rückkehr zum Menü"""
        self.send_effect(chain="A", effect_type="wipe", segment=99, r=255, g=0, b=0, speed=30, repeat=1, priority=2, event_key="game_ended")

    def effect_highscore(self):
        """Highscore-Anzeige: Farbwechselndes, magisches Funkeln"""
        self.send_effect(chain="A", effect_type="sparkle", segment=99, r=255, g=0, b=255, speed=40, repeat=6, priority=2, event_key="launcher_highscore")