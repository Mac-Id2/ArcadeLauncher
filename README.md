# DIGITS ARCADE - Retro Game Launcher

Ein plattformübergreifender Game Launcher im Retro-Design, entwickelt in Python mittels Pygame. Die Applikation bietet hardwarebeschleunigte visuelle Effekte (Sterne, Scanlines, prozedurale Sprite-Animationen) und ermöglicht die nahtlose Ausführung externer Spiel-Binärdateien unter Windows, macOS und Linux.

## 🛠 Systemanforderungen

Um die Applikation quelloffen auszuführen oder einen Build zu generieren, werden folgende Komponenten vorausgesetzt:
- Python 3.x
- Pygame (`pip install pygame`)

## 📂 Architektur und Verzeichnisstruktur

Für eine korrekte Pfadauflösung zur Laufzeit (sowohl im Quellcode als auch als kompilierter Build) ist die Einhaltung der folgenden Verzeichnishierarchie zwingend erforderlich:

```text
/DeinSpieleVerzeichnis
│
├── launcher/                   # Root-Verzeichnis der Launcher-Applikation
│   ├── launcher.exe            # Executable (Windows) bzw. Binary "launcher" (macOS/Linux)
│   ├── _internal/              # Systembibliotheken (wird bei PyInstaller-Builds generiert)
│   ├── games.json              # Applikationskonfiguration und Spielpfade
│   │
│   └── assets/                 # Verzeichnis für statische Applikationsressourcen
│       ├── arcade.ttf
│       ├── player-idle.png
│       └── ... 
│
└── spiele/                     # Root-Verzeichnis der zu startenden Applikationen
    │
    ├── Space-Invaders/         # Applikationsverzeichnis (Spiel 1)
    │   ├── game.exe            # Windows Executable
    │   ├── game                # macOS / Linux Executable
    │   ├── _internal/          # Spielspezifische Bibliotheken
    │   └── assets/             # Spielspezifische Ressourcen
    │
    └── Pac-Man/                # Applikationsverzeichnis (Spiel 2)
        ├── game.exe            # Windows
        ├── game.app            # macOS (App-Bundle)
        ├── game.x86_64         # Linux
        ├── _internal/          
        └── assets/
```

---

## Manueller lokaler Build

__1. venv aktivieren__

source .venv/bin/activate

__2. Build__

pyinstaller --noconsole --onefile \
    --hidden-import websockets \
    --hidden-import serial \
    launcher.py

__3. Assets und Config ins Output-Verzeichnis kopieren__
  
mkdir -p dist/final_delivery
mv dist/launcher dist/final_delivery/
chmod +x dist/final_delivery/launcher
cp -r assets dist/final_delivery/
cp games.json dist/final_delivery/

Das fertige Bundle liegt danach in dist/final_delivery/. 

Starten mit: ./dist/final_delivery/launcher

__Wichtig__ 

PyInstaller baut immer nur für das aktuelle OS — auf dem Mac entsteht ein macOS-Binary, 
kein Windows-Build. Für Cross-Platform-Builds ist weiterhin der CI nötig.
