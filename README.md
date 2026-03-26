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