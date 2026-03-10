# DIGITS ARCADE - Retro Game Launcher

Ein im Retro-Stil gehaltener, plattformübergreifender Game Launcher, geschrieben in Python mit Pygame. Der Launcher bietet dynamische Hintergrundeffekte (Sterne, Scanlines, animiertes Raumschiff), Pixel-Art-Animationen und startet Spiele nahtlos in Windows, macOS und Linux.

## 🛠 Voraussetzungen

Um den Launcher auszuführen oder selbst zu kompilieren, benötigst du:
- Python 3.x
- Pygame (`pip install pygame`)

## 📂 Ordnerstruktur

Damit der Launcher alle Grafiken und Spiele findet, muss die Ordnerstruktur nach dem Download (bzw. dem Build) wie folgt aussehen:

```text
/DeinSpieleVerzeichnis
│
├── launcher/                   #  Launcher-Ordner
│   ├── launcher.exe            # (Windows) oder "launcher" (Mac/Linux)
│   ├── _internal/              # (Systemdateien von PyInstaller für den Launcher)
│   ├── games.json              # Konfigurationsdatei für die Spiele
│   │
│   └── assets/                 # Ordner für Launcher-Grafiken und Schriften
│       ├── arcade.ttf
│       ├── player-idle.png
│       └── ... 
│
└── spiele/                     # Ordner für die eigentlichen Spiele
    │
    ├── Space-Invaders/         # Ein komplett kompiliertes Spiel
    │   ├── main.exe            # Windows Executable
    │   ├── main                # Mac / Linux Executable (ohne Endung)
    │   ├── _internal/          # (Systemdateien von PyInstaller für das Spiel)
    │   └── assets/             # (Grafiken/Sounds für das Spiel selbst)
    │
    └── Pac-Man/
        ├── game.exe            # Windows
        ├── game_mac            # Mac Executable
        ├── game.x86_64         # Linux
        ├── _internal/          
        └── assets/
