"""
config.py

Zentrales Konfigurationsmodul für den Arcade-Launcher.
Inklusive Fail-Safe Logging und defensivem JSON-Parsing für Produktionssicherheit.
"""

import os
import sys
import json
import logging
import pygame

# --- Pfad-Logik für PyInstaller ---
if getattr(sys, "frozen", False):
    RESOURCE_PATH = os.path.dirname(sys.executable)
else:
    RESOURCE_PATH = os.path.dirname(os.path.abspath(__file__))

GAME_BASE_PATH = RESOURCE_PATH
os.chdir(RESOURCE_PATH)

# --- PRODUKTIONS-LOGGING (Fail-Safe) ---
LOG_FILE = os.path.join(GAME_BASE_PATH, "launcher.log")
try:
    # Versuche, eine Log-Datei im Spielordner anzulegen
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.info("=== LAUNCHER GESTARTET ===")
except Exception:
    # Fallback: Wenn Schreibrechte fehlen, logge nur kritische Fehler ins Nichts (kein Crash!)
    logging.basicConfig(level=logging.CRITICAL)

def get_path(rel_path):
    return os.path.abspath(os.path.join(RESOURCE_PATH, rel_path))

def get_game_path(rel_path):
    return os.path.abspath(os.path.join(GAME_BASE_PATH, rel_path))

# --- Globale Farbkonstanten ---
BG_COLOR = (5, 5, 15)      
NEON_CYAN = (0, 255, 255)
NEON_PINK = (255, 20, 147)
NEON_YELLOW = (255, 255, 0)
NEON_GREEN = (57, 255, 20)
NEON_RED = (255, 10, 10) 
WHITE = (255, 255, 255)
RED = (255, 0, 0)
DARK_RED = (100, 0, 0)
DARK_CYAN = (0, 100, 100)
PUNK_COLORS = [NEON_CYAN, NEON_PINK, NEON_YELLOW, NEON_GREEN, NEON_RED]

CONFIG_FILE = os.path.join(RESOURCE_PATH, "games.json")

def load_games_config():
    """Lädt die games.json defensiv. Stürzt nie ab, selbst bei fehlerhafter Datei."""
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"Konfigurationsdatei fehlt: {CONFIG_FILE}")
        return []
        
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Defensiver Zugriff: Wenn "games" fehlt, nimm eine leere Liste
            loaded_games = data.get("games", [])
            valid_games = []
            
            for game in loaded_games:
                # Prüfe, ob das Dictionary gültig ist und einen "paths" Key hat
                if not isinstance(game, dict):
                    continue
                    
                paths = game.get("paths", {})
                if not isinstance(paths, dict):
                    logging.warning(f"Spiel '{game.get('display_name', 'Unbekannt')}' hat ungültige Pfade. Wird ignoriert.")
                    continue
                
                # Pfade sicher umwandeln
                game["paths"] = {}
                for os_name, rel_path in paths.items():
                    game["paths"][os_name] = get_game_path(rel_path)
                    
                valid_games.append(game)
                
            logging.info(f"{len(valid_games)} Spiele erfolgreich aus games.json geladen.")
            return valid_games
            
    except json.JSONDecodeError as e:
        logging.error(f"JSON Syntax-Fehler in games.json: {e}")
        return []
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Laden der Config: {e}")
        return []

games = load_games_config()