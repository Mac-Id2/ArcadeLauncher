"""
config.py

Zentrales Konfigurationsmodul des Arcade-Launchers.
Implementiert die Umgebungserkennung (PyInstaller-Kompatibilität), robustes
Fallback-Logging und das defensive Parsing der Anwendungsdaten.
"""

import os
import sys
import json
import logging
import pygame

# --- Ermittlung des Ausführungskontexts (PyInstaller Bundle vs. reguläres Python-Skript) ---
if getattr(sys, "frozen", False):
    RESOURCE_PATH = os.path.dirname(sys.executable)
else:
    RESOURCE_PATH = os.path.dirname(os.path.abspath(__file__))

GAME_BASE_PATH = RESOURCE_PATH
os.chdir(RESOURCE_PATH)

# --- Initialisierung des Fehlerprotokolls (Fail-Safe Logging) ---
LOG_FILE = os.path.join(GAME_BASE_PATH, "launcher.log")
try:
    # Primärer Logging-Ansatz: Dateibasierte Aufzeichnung im Anwendungsverzeichnis
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.info("=== LAUNCHER GESTARTET ===")
except Exception:
    # Fallback: Reduziertes Logging ohne Datei-I/O bei fehlenden Schreibberechtigungen zur Vermeidung von Applikationsabstürzen.
    logging.basicConfig(level=logging.CRITICAL)

def get_path(rel_path):
    """Löst relative Pfade für systeminterne Launcher-Ressourcen auf."""
    return os.path.abspath(os.path.join(RESOURCE_PATH, rel_path))

def get_game_path(rel_path):
    """Löst relative Pfade für externe Spiel-Binärdateien auf."""
    return os.path.abspath(os.path.join(GAME_BASE_PATH, rel_path))

# --- Definition globaler Farbkonstanten (RGB-Werte) ---
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
    """
    Parst die Konfigurationsdatei (games.json) defensiv und validiert die Datenstruktur.
    Implementiert Fallbacks für fehlende oder fehlerhafte Einträge, um Laufzeitfehler zu vermeiden.
    
    :return: List[dict] - Eine validierte Liste von Spiel-Definitionen und deren plattformspezifischen Pfaden.
    """
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"Konfigurationsdatei fehlt: {CONFIG_FILE}")
        return []
        
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Defensive Extraktion: Fallback auf leere Liste bei fehlendem Root-Element.
            loaded_games = data.get("games", [])
            valid_games = []
            
            for game in loaded_games:
                # Typenprüfung der iterierten Entität
                if not isinstance(game, dict):
                    continue
                    
                paths = game.get("paths", {})
                if not isinstance(paths, dict):
                    logging.warning(f"Spiel '{game.get('display_name', 'Unbekannt')}' weist ungültige Pfadstruktur auf. Entität wird ignoriert.")
                    continue
                
                # Konvertierung relativer Konfigurationspfade in absolute Systempfade
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
        logging.error(f"Unerwarteter Fehler bei der Konfigurationsauflösung: {e}")
        return []

games = load_games_config()