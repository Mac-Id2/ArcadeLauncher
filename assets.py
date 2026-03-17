"""
assets.py

Behandelt die Generierung der Menü-Sprites.
Um externe Bilddateien zu sparen, werden die Retro-Sprites hier aus 
ASCII-Matrizen direkt zur Laufzeit in Pygame-Surfaces gerendert.
"""

import pygame
from config import WHITE, NEON_GREEN, NEON_CYAN, NEON_YELLOW, RED, NEON_PINK

# --- PIXEL ART MATRIZEN ---
# Jedes Zeichen repräsentiert einen Pixel. 
# '#' = Hauptfarbe, 'W' = Weiß, 'B' = Blau, ' ' = Transparent
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
    Konvertiert eine ASCII-String-Matrix in ein Pygame Surface.
    
    :param matrix: Liste von Strings (die ASCII-Art)
    :param main_color: RGB Tuple für das Hauptzeichen '#'
    :param scale: Größe eines "Pixels" auf dem Bildschirm in echten Pixeln
    :return: Gerendertes pygame.Surface mit Alphakanal
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
    Initialisiert alle Sprites in der korrekten Skalierung für die aktuelle
    Bildschirmauflösung (berechnet anhand der Bildschirmhöhe 'sh').
    
    :param sh: Bildschirmhöhe in Pixeln
    :return: Dictionary mit allen generierten Sprite-Surfaces
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