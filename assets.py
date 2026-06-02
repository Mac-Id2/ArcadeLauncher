import pygame
from config import WHITE, NEON_GREEN, NEON_CYAN, NEON_YELLOW, RED, NEON_PINK

# Pixel-Kodierung: '#' = Hauptfarbe, 'W' = Weiß, 'B' = Blau, ' ' = transparent
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
    "  ######   ",
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


def create_sprite(matrix: list, main_color: tuple, scale: int) -> pygame.Surface:
    """Wandelt eine ASCII-Matrix in eine skalierte Pygame-Surface um."""
    w = max(len(row) for row in matrix)
    h = len(matrix)
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for y, row in enumerate(matrix):
        for x, char in enumerate(row):
            if char == '#':
                color = main_color
            elif char == 'W':
                color = WHITE
            elif char == 'B':
                color = (30, 30, 255)
            else:
                continue
            pygame.draw.rect(surf, color, (x * scale, y * scale, scale, scale))
    return surf


def init_sprites(sh: int) -> dict:
    """Erstellt alle Menü-Sprites skaliert auf die Bildschirmhöhe sh."""
    s = max(4, int(sh * 0.008))
    return {
        'invader1_a':    create_sprite(INVADER_1,            NEON_GREEN,  s),
        'invader1_b':    create_sprite(INVADER_2,            NEON_GREEN,  s),
        'invader2_a':    create_sprite(INVADER_2,            NEON_CYAN,   s),
        'invader2_b':    create_sprite(INVADER_1,            NEON_CYAN,   s),
        'pac_open':      create_sprite(PACMAN_OPEN,          NEON_YELLOW, s),
        'pac_closed':    create_sprite(PACMAN_CLOSED,        NEON_YELLOW, s),
        'ghost_red':     create_sprite(GHOST,                RED,         s),
        'ghost_cyan':    create_sprite(GHOST,                NEON_CYAN,   s),
        'ast_ship':      create_sprite(ASTEROIDS_SHIP,       NEON_PINK,   s),
        'ast_ship_thrust': create_sprite(ASTEROIDS_SHIP_THRUST, NEON_PINK, s),
        'asteroid1':     create_sprite(ASTEROID_1,           NEON_CYAN,   s),
        'asteroid2':     create_sprite(ASTEROID_2,           NEON_CYAN,   s),
    }
