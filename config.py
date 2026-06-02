import os
import sys
import json
import logging

if getattr(sys, "frozen", False):
    RESOURCE_PATH = os.path.dirname(sys.executable)
else:
    RESOURCE_PATH = os.path.dirname(os.path.abspath(__file__))

os.chdir(RESOURCE_PATH)

try:
    logging.basicConfig(
        filename=os.path.join(RESOURCE_PATH, "launcher.log"),
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    logging.info("=== LAUNCHER GESTARTET ===")
except Exception:
    logging.basicConfig(level=logging.CRITICAL)


def get_path(rel_path: str) -> str:
    """Löst einen relativen Pfad relativ zum Launcher-Verzeichnis auf."""
    return os.path.abspath(os.path.join(RESOURCE_PATH, rel_path))


BG_COLOR    = (5, 5, 15)
NEON_CYAN   = (0, 255, 255)
NEON_PINK   = (255, 20, 147)
NEON_YELLOW = (255, 255, 0)
NEON_GREEN  = (57, 255, 20)
NEON_RED    = (255, 10, 10)
WHITE       = (255, 255, 255)
RED         = (255, 0, 0)
PUNK_COLORS = [NEON_CYAN, NEON_PINK, NEON_YELLOW, NEON_GREEN, NEON_RED]

_CONFIG_FILE = os.path.join(RESOURCE_PATH, "games.json")


def load_games_config() -> list:
    if not os.path.exists(_CONFIG_FILE):
        logging.warning("Konfigurationsdatei fehlt: %s", _CONFIG_FILE)
        return []
    try:
        with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        valid = []
        for game in data.get("games", []):
            if not isinstance(game, dict):
                continue
            paths = game.get("paths", {})
            if not isinstance(paths, dict):
                logging.warning("Ungültige Pfadstruktur bei '%s'.", game.get('name', '?'))
                continue
            game["paths"] = {os_key: get_path(rel) for os_key, rel in paths.items()}
            valid.append(game)
        logging.info("%d Spiele aus games.json geladen.", len(valid))
        return valid
    except json.JSONDecodeError as e:
        logging.error("JSON-Fehler in games.json: %s", e)
        return []
    except Exception as e:
        logging.error("Fehler beim Laden von games.json: %s", e)
        return []


games = load_games_config()
