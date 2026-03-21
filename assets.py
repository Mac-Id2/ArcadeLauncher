"""
assets.py

Modul zur prozeduralen Generierung von UI- und Menü-Sprites.
Konvertiert ASCII-basierte Bildmatrizen zur Laufzeit in native Pygame-Surfaces,
um den Speicherbedarf zu minimieren und externe Dateiabhängigkeiten zu reduzieren.
"""

import pygame
from config import WHITE, NEON_GREEN, NEON_CYAN, NEON_YELLOW, RED, NEON_PINK

# --- Sprite-Definitionen (Pixel-Art-Matrizen) ---
# Kodierung der Pixel-Werte:
# '#' = Primärfarbe (wird beim Rendering dynamisch übergeben)
# 'W' = Weiß (RGB: 255, 255, 255)
# 'B' = Blau (RGB: 30, 30, 255)
# ' ' (Leerzeichen) = Transparent (Alpha-Kanal 0)
INVADER_1 = [
    "  #     #  ",
    "   #   #   ",
    "  #######  ",
    " ## ### ## ",
    "###########",
    "# ####### #",
    "# #     # #",
    "   ## ##   "
]

INVADER_2 = [
    "  #     #  ",
    "#  #   #  #",
    "# ####### #",
    "### ### ###",
    "###########",
    "  #######  ",
    " # #   # # ",
    "#         #"
]

PACMAN_OPEN = [
    "    #####    ",
    "  #########  ",
    " ########### ",
    "#############",
    "############ ",
    "##########   ",
    "########     ",
    "######       ",
    "########     ",
    "##########   ",
    " ########### ",
    "  #########  ",
    "    #####    "
]

PACMAN_CLOSED = [
    "    #####    ",
    "  #########  ",
    " ########### ",
    "#############",
    "#############",
    "#############",
    "#############",
    "#############",
    "#############",
    "#############",
    " ########### ",
    "  #########  ",
    "    #####    "
]

GHOST = [
    "    ######    ",
    "  ##########  ",
    " ############ ",
    " ###WW###WW## ",
    " ##WWBB#WWBB# ",
    " ##WWBB#WWBB# ",
    " ###WW###WW## ",
    " ############ ",
    " ############ ",
    " ############ ",
    " ############ ",
    " ############ ",
    " ##  ####  ## ",
    " #    ##    # "
]

ASTEROIDS_SHIP = [
    "     #     ",
    "    ###    ",
    "   ##W##   ",
    "  #######  ",
    " ######### ",
    "###########",
    "###     ###",
    "##       ##"
]

ASTEROIDS_SHIP_THRUST = [
    "     #     ",
    "    ###    ",
    "   ##W##   ",
    "  #######  ",
    " ######### ",
    "###########",
    "### ### ###",
    "##  ###  ##",
    "     #     "
]

ASTEROID_1 = [
    "  ######  ",
    " ######### ",
    "###########",
    "####   ####",
    "###     ###",
    "#####   ###",
    "###########",
    " ######### ",
    "  #######  "
]

ASTEROID_2 = [
    "  ######   ",
    " ########  ",
    "########## ",
    "###    ####",
    "##      ###",
    "####   ####",
    " ##########",
    "  ######## ",
    "   ######  "
]

def create_sprite(matrix, main_color, scale):
    """
    Konvertiert eine ASCII-String-Matrix in ein renderfähiges Pygame-Surface mit Alphakanal.
    
    :param matrix: List[str] - Die ASCII-Art-Repräsentation des Sprites.
    :param main_color: Tuple[int, int, int] - RGB-Farbwert für den Hauptpixel ('#').
    :param scale: int - Skalierungsfaktor (Größe eines logischen Pixels in physischen Pixeln).
    :return: pygame.Surface - Das gerenderte Sprite-Objekt.
    """
    w, h = len(matrix[0]), len(matrix)
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    
    for y, row in enumerate(matrix):
        for x, char in enumerate(row):
            color = None
            if char == '#': color = main_color
            elif char == 'W': color = WHITE
            elif char == 'B': color = (30, 30, 255)
            
            if color:
                pygame.draw.rect(surf, color, (x * scale, y * scale, scale, scale))
    return surf

def init_sprites(sh):
    """
    Initialisiert und skaliert alle System-Sprites dynamisch basierend auf der vertikalen Bildschirmauflösung.
    
    :param sh: int - Aktuelle Bildschirmhöhe in Pixeln zur Berechnung des Skalierungsfaktors.
    :return: dict - Dictionary mit allen initialisierten und skalierten pygame.Surface-Objekten.
    """
    scale_size = max(4, int(sh * 0.008))
    
    sprites = {
        'invader1_a': create_sprite(INVADER_1, NEON_GREEN, scale_size),
        'invader1_b': create_sprite(INVADER_2, NEON_GREEN, scale_size),
        'invader2_a': create_sprite(INVADER_2, NEON_CYAN, scale_size),
        'invader2_b': create_sprite(INVADER_1, NEON_CYAN, scale_size),
        'pac_open': create_sprite(PACMAN_OPEN, NEON_YELLOW, scale_size),
        'pac_closed': create_sprite(PACMAN_CLOSED, NEON_YELLOW, scale_size),
        'ghost_red': create_sprite(GHOST, RED, scale_size),
        'ghost_cyan': create_sprite(GHOST, NEON_CYAN, scale_size),
        'ast_ship': create_sprite(ASTEROIDS_SHIP, NEON_PINK, scale_size),
        'ast_ship_thrust': create_sprite(ASTEROIDS_SHIP_THRUST, NEON_PINK, scale_size),
        'asteroid1': create_sprite(ASTEROID_1, NEON_CYAN, scale_size),
        'asteroid2': create_sprite(ASTEROID_2, NEON_CYAN, scale_size)
    }
    return sprites