# DIGITS ARCADE - Retro Game Launcher

Ein plattformübergreifender Game Launcher im Retro-Design, entwickelt in Python mit Pygame. Die Applikation bietet hardwarebeschleunigte visuelle Effekte (Sterne, Scanlines, prozedurale Sprite-Animationen), Hintergrundmusik und ermöglicht die nahtlose Ausführung externer Spiel-Binärdateien unter Windows, macOS und Linux. Optional wird ein ESP32-basiertes LED-System über eine serielle Verbindung und einen WebSocket-Server gesteuert.

---

## Systemanforderungen

### Laufzeit (vorkompiliertes Bundle)

- **OS**: Windows 10+, macOS 12+, Linux (Debian/Ubuntu-basiert empfohlen)
- **Hardware**: Bildschirm mit beliebiger Auflösung; optionaler ESP32 für LED-Beleuchtung

### Quellcode / Build

| Komponente | Mindestversion | Pflicht |
|---|---|---|
| Python | 3.10+ | ja |
| pygame | 2.x | ja |
| pyinstaller | 6.x | nur für Build |
| pyserial | aktuell | optional (LED-Hardware) |
| websockets | aktuell | optional (Spiel-LED-Integration) |

```bash
pip install pygame pyinstaller pyserial websockets
```

---

## Verzeichnisstruktur

Die Pfade in `games.json` werden **relativ zum Launcher-Verzeichnis** aufgelöst. Die folgende Struktur ist zwingend einzuhalten:

```text
/ArcadeRoot/                        # Beliebiges Root-Verzeichnis
│
├── launcher/                       # Launcher-Bundle (Ausgabe des Builds)
│   ├── launcher                    # Executable (macOS/Linux)
│   ├── launcher.exe                # Executable (Windows)
│   ├── _internal/                  # PyInstaller-Systembibliotheken
│   ├── games.json                  # Zentrale Konfigurationsdatei
│   ├── launcher.log                # Laufzeit-Log (wird automatisch erstellt)
│   │
│   └── assets/                     # Statische Launcher-Ressourcen
│       ├── arcade.ttf              # Retro-Schriftart
│       ├── arcade-music-loop.wav   # Hintergrundmusik (optional)
│       ├── player-idle.png         # Schiff-Sprite (Idle)
│       ├── player-boost-default.png
│       ├── player-boost-left.png
│       └── player-boost-right.png
│
└── spiele/                         # Spiele-Verzeichnis (Geschwister-Ordner)
    │
    ├── Space-Invaders/
    │   ├── game.exe                # Windows
    │   ├── game                    # macOS / Linux
    │   └── _internal/
    │
    ├── Pac-Man/
    │   ├── game.exe
    │   ├── game
    │   └── _internal/
    │
    └── Asteroids/
        ├── game.exe
        ├── game
        └── _internal/
```

> **Hinweis**: Der `spiele/`-Ordner liegt auf gleicher Ebene wie `launcher/`. Pfade in `games.json` beginnen daher mit `../spiele/...`.

---

## Konfiguration: games.json

Die Datei `games.json` ist die einzige Konfigurationsquelle. Sie enthält zwei Sektionen: `screen` und `games`.

### Bildschirmkonfiguration (`screen`)

```json
{
    "screen": {
        "width": 0,
        "height": 0,
        "fullscreen": true,
        "virtual_width": 1280,
        "virtual_height": 720
    }
}
```

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `width` | int | `0` | Fensterbreite in Pixeln. `0` = Bildschirmbreite automatisch |
| `height` | int | `0` | Fensterhöhe in Pixeln. `0` = Bildschirmhöhe automatisch |
| `fullscreen` | bool | `true` | `true` = Vollbildmodus, `false` = Fenstermodus |
| `virtual_width` | int | `1280` | Interne Renderbreite (logisches Spielfeld) |
| `virtual_height` | int | `720` | Interne Renderhöhe (logisches Spielfeld) |

**Verhalten**: Der Launcher rendert intern immer auf der virtuellen Auflösung (`virtual_width × virtual_height`) und skaliert das Ergebnis letterboxed auf die echte Bildschirmgröße. Dadurch ist das Layout unabhängig von der tatsächlichen Auflösung.

**Beispielkonfigurationen**:

```json
// Vollbild, automatische Auflösung (Standardverhalten für Arcade-Kabinett)
"screen": { "fullscreen": true, "width": 0, "height": 0, "virtual_width": 1280, "virtual_height": 720 }

// Fenstermodus 800×600 (Entwicklung / Debugging)
"screen": { "fullscreen": false, "width": 800, "height": 600, "virtual_width": 1280, "virtual_height": 720 }
```

### Spielkonfiguration (`games`)

```json
{
    "games": [
        {
            "display_name": "SPACE INVADERS",
            "name": "space_invaders",
            "paths": {
                "Windows": "../spiele/Space-Invaders/game.exe",
                "Darwin":  "../spiele/Space-Invaders/game",
                "Linux":   "../spiele/Space-Invaders/game"
            }
        }
    ]
}
```

| Schlüssel | Beschreibung |
|---|---|
| `display_name` | Anzeigename im Menü (Großbuchstaben empfohlen) |
| `name` | Interner Bezeichner (wird für LED-Farben und Logging verwendet) |
| `paths.Windows` | Relativer Pfad zur Windows-Executable |
| `paths.Darwin` | Relativer Pfad zur macOS-Executable |
| `paths.Linux` | Relativer Pfad zur Linux-Executable |

Fehlt der Pfad für das aktuelle OS, wird beim Start eine Fehlermeldung im Launcher angezeigt.

### LED-Konfiguration (Umgebungsvariablen)

Die LED-Bridge wird über Umgebungsvariablen konfiguriert — kein Eintrag in `games.json` erforderlich:

| Variable | Standardwert | Beschreibung |
|---|---|---|
| `ARCADE_SERIAL_PORT` | `/dev/ttyACM0` | Serieller Port des ESP32 |
| `ARCADE_ATTRACT_TIMEOUT` | `30` | Sekunden Inaktivität bis Attract-Mode |

---

## Architektur

```text
ArcadeLauncher (launcher.py)
├── config.py          — Pfadauflösung, Farbkonstanten, Konfigurationsloader
├── assets.py          — Prozedurale Pixel-Sprites (ASCII-Art → Pygame Surface)
└── led_bridge.py      — LED-Hardware-Integration (optional)

Klassen in launcher.py:
  ArcadeLauncher       — Orchestrator: Game-Loop, Event-Handling
  DisplayManager       — Pygame-Init, virtuelles Rendering + Letterbox-Scaling
  FontManager          — Schriftarten (Arcade TTF mit Fallback)
  BackgroundScene      — Sterne, Bloom-Grid, Scanlines, fliegendes Schiff
  TitleRenderer        — Animierter Titel mit Glitch-Effekt
  MenuView             — Spielauswahl-Liste mit spielspezifischen Sprites
  MusicPlayer          — Hintergrundmusik-Loop
  GameRunner           — Prozessstart (subprocess), Env-Bereinigung für PyInstaller
  ShipSprite           — Animiertes Raumschiff (traversiert den Bildschirm)

led_bridge.py (Fassade: LEDBridge):
  SerialTransport      — Serielles I/O zum ESP32 mit Auto-Reconnect
  EffectDispatcher     — Prioritätsbasiertes Effekt-Routing + Keepalive
  AttractMode          — Idle-Farbrotation nach konfigurierbarem Timeout
  GameWebSocketServer  — WS-Server ws://localhost:8765 für Spiel-LED-Kommandos
```

### Datenfluss

```
games.json
    └─► config.py (load_games_config, load_screen_config)
            └─► launcher.py
                    ├── DisplayManager  ──► Pygame Window (real screen)
                    │       └── virtual Surface ──► letterbox scale ──► real screen
                    ├── GameRunner      ──► subprocess (Spiel-Binary)
                    └── LEDBridge
                            ├── SerialTransport ──► ESP32 (Serial JSON)
                            └── WS-Server       ◄── Spiele (ws://localhost:8765)
```

### Navigation & Steuerung

| Taste | Funktion |
|---|---|
| `W` / `S` | Menü hoch / runter |
| `Leertaste` | Spiel starten |
| `ESC` | Launcher beenden |

---

## Build

### 1. venv aktivieren

```bash
source .venv/bin/activate
```

### 2. Build

```bash
pyinstaller --noconsole --onefile \
    --hidden-import websockets \
    --hidden-import serial \
    launcher.py
```

### 3. Assets und Config ins Output-Verzeichnis kopieren

```bash
mkdir -p dist/final_delivery
mv dist/launcher dist/final_delivery/
chmod +x dist/final_delivery/launcher
cp -r assets dist/final_delivery/
cp games.json dist/final_delivery/
```

Das fertige Bundle liegt danach in `dist/final_delivery/`.

Starten mit:

```bash
./dist/final_delivery/launcher
```

**Wichtig**: PyInstaller baut immer nur für das aktuelle OS — auf dem Mac entsteht ein macOS-Binary, kein Windows-Build. Für Cross-Platform-Builds ist der CI erforderlich.

---

## Logging

Der Launcher schreibt ein Laufzeit-Log in `launcher.log` im selben Verzeichnis wie die Executable. Das Log enthält Spielstarts/-stopps, LED-Status, Konfigurationsfehler und Display-Informationen.
