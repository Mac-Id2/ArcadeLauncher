"""
launcher_test.py

TEST-VERSION des Arcade-Launchers.
Simuliert den Spielstart und die LED-Effekte, AUCH WENN die Spiele
nicht im Verzeichnis existieren.
"""

import pygame
import sys
import os
import platform
import math
import random
import logging
import time
from LedController import LedController

# --- Fallback-Konfiguration (falls config.py fehlt) ---
try:
    from config import *
except ImportError:
    # Fallback-Werte, falls die config-Datei im Testordner fehlt
    BG_COLOR = (10, 10, 25)
    WHITE = (255, 255, 255)
    RED = (255, 50, 50)
    NEON_CYAN = (0, 255, 255)
    NEON_YELLOW = (255, 255, 0)
    NEON_PINK = (255, 20, 147)
    PUNK_COLORS = [(255, 0, 128), (0, 255, 255), (255, 255, 0)]
    def get_path(p): return p
    # Dummy-Spieleliste für den Test
    games = [
        {"display_name": "PAC-MAN", "paths": {"Windows": "dummy.exe", "Linux": "dummy", "Darwin": "dummy.app"}},
        {"display_name": "SPACE INVADERS", "paths": {"Windows": "dummy.exe", "Linux": "dummy", "Darwin": "dummy.app"}},
        {"display_name": "ASTEROIDS", "paths": {"Windows": "dummy.exe", "Linux": "dummy", "Darwin": "dummy.app"}}
    ]

# --- Fallback-Sprites (falls assets.py fehlt) ---
try:
    from assets import init_sprites
except ImportError:
    def init_sprites(sh):
        # Erstellt Dummy-Oberflächen, falls keine echten Bilder da sind
        d = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(d, (255, 255, 0), (16, 16), 14)
        return {
            'pac_open': d, 'pac_closed': d, 'ghost_red': d, 
            'ghost_cyan': d, 'invader1_a': d, 'invader1_b': d, 
            'invader2_a': d, 'invader2_b': d, 'ast_ship': d, 
            'ast_ship_thrust': d, 'asteroid1': d, 'asteroid2': d
        }

# --- Initialisierung: Pygame & Display ---
pygame.init()
pygame.mouse.set_visible(False)

# Physische Bildschirmauflösung ermitteln (Fullscreen)
real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
REAL_W, REAL_H = real_screen.get_size()

# Virtuelle Zeichenfläche (16:9)
sw, sh = 1280, 720
screen = pygame.Surface((sw, sh))

clock = pygame.time.Clock()

# --- LED Controller Initialisierung & Start ---
logging.basicConfig(level=logging.INFO)
led = LedController()
led.attract_resume() # Starte direkt den Attract Mode (Ruhelicht)

logging.info(f"[TEST] Monitor: {REAL_W}x{REAL_H} | Virtuell: {sw}x{sh}")

# --- Typografie ---
try:
    font_path = get_path("assets/arcade.ttf")
    title_font = pygame.font.Font(font_path, int(sh * 0.12))
    menu_font = pygame.font.Font(font_path, int(sh * 0.05))
    small_font = pygame.font.Font(font_path, int(sh * 0.02))
except:
    logging.warning("Arcade-Font nicht gefunden, nutze System-Fallback.")
    title_font = pygame.font.Font(None, int(sh * 0.12))
    menu_font = pygame.font.Font(None, int(sh * 0.06))
    small_font = pygame.font.Font(None, int(sh * 0.03))

sprites = init_sprites(sh)

# --- Visuelle Hintergrund-Effekte ---
stars = [[random.randint(0, sw), random.randint(0, sh), random.randint(1, 3)] for _ in range(100)]

bloom_grid_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
for x in range(0, sw, int(sw*0.05)): 
    pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (x, 0), (x, sh), 2)
for y in range(0, sh, int(sh*0.05)): 
    pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (0, y), (sw, y), 2)

scanline_surf = pygame.Surface((sw, sh + 10), pygame.SRCALPHA)
for y in range(0, sh + 10, 6):
    pygame.draw.line(scanline_surf, (0, 0, 0, 160), (0, y), (sw, y), 2)

def draw_scanlines(frame):
    offset = (frame // 4) % 6
    screen.blit(scanline_surf, (0, -offset))

def draw_punk_underline(rect, frame):
    num_blocks = 20
    block_width = max(1, rect.width // num_blocks)
    underline_y = rect.bottom + sh * 0.015
    for i in range(num_blocks):
        color = PUNK_COLORS[(i + (frame // 10)) % len(PUNK_COLORS)]
        offset_y = math.sin(frame * 0.2 + i * 0.5) * (sh * 0.003)
        block_rect = pygame.Rect(rect.left + i * block_width, underline_y + offset_y, block_width - 2, sh * 0.005)
        pygame.draw.rect(screen, color, block_rect)

# --- Animiertes Deko-Schiff ---
ship_active = False
ship_x, ship_y = -1000, -1000

# --- Hauptschleife Setup ---
selected_index = 0
error_message = ""
frame_counter = 0
running_pac_x = -200
running = True

while running:
    frame_counter += 1
    aktuelles_os = platform.system()

    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT: 
            running = False
        
        if event.type == pygame.KEYDOWN:
            error_message = ""
            if event.key == pygame.K_ESCAPE:
                running = False
                continue

            if not games:
                continue
            
            # Navigation mit LED-Feedback
            if event.key == pygame.K_w: 
                selected_index = (selected_index - 1) % len(games)
                led.send_effect(chain="A", effect_type="blink", segment=99, r=0, g=230, b=255, speed=80, repeat=1, priority=2, event_key="menu_scroll")
            elif event.key == pygame.K_s: 
                selected_index = (selected_index + 1) % len(games)
                led.send_effect(chain="A", effect_type="blink", segment=99, r=0, g=230, b=255, speed=80, repeat=1, priority=2, event_key="menu_scroll")
            
            # --- SIMULIERTER SPIELSTART (LEERTASTE) ---
            elif event.key == pygame.K_SPACE:
                game = games[selected_index]
                game_name = game.get("display_name", "Unbekanntes Spiel")
                
                logging.info(f"[TEST-START] Simuliere Start von: {game_name}")
                
                # 1. LED-Effekt je nach Spiel zünden
                led.attract_pause() # Stoppe die Ambient-Beleuchtung
                game_identifier = game_name.upper()
                
                if "SPACE" in game_identifier:
                    led.effect_start_space_invaders() # Grüner Matrix Wipe
                elif "ASTEROID" in game_identifier:
                    led.effect_start_asteroids()      # Weißer Puls
                else:
                    led.effect_start_pacman()         # Gelber Lauflicht-Chase

                # 2. Test-Ladebildschirm auf den Monitor zeichnen
                screen.fill(BG_COLOR)
                l_txt = title_font.render("LOADING...", True, NEON_CYAN)
                screen.blit(l_txt, l_txt.get_rect(center=(sw//2, sh//2)))
                
                sub_txt = menu_font.render("SIMULATION (4 SEKUNDEN)", True, WHITE)
                screen.blit(sub_txt, sub_txt.get_rect(center=(sw//2, sh//2 + 80)))
                
                # Auf Fullscreen skalieren
                scale_f = min(REAL_W / sw, REAL_H / sh)
                temp_scaled = pygame.transform.scale(screen, (int(sw * scale_f), int(sh * scale_f)))
                real_screen.fill((0, 0, 0))
                real_screen.blit(temp_scaled, ((REAL_W - temp_scaled.get_width()) // 2, (REAL_H - temp_scaled.get_height()) // 2))
                pygame.display.flip()
                
                # 3. Wartezeit blockieren (Simuliert die Spielzeit im Vordergrund)
                pygame.time.wait(4000)
                
                # 4. Spielende-Effekte feuern
                logging.info(f"[TEST-ENDE] Simuliere Beendigung von: {game_name}")
                led.effect_game_ended()  # Roter Wipe
                led.attract_resume()     # Reaktiviert den Ruhezustand
                
                # Alte Tastendrücke löschen, um sofortiges Re-Triggern zu verhindern
                pygame.event.clear()

    # --- Update Logik ---
    for star in stars:
        star[1] += star[2]
        if star[1] > sh:
            star[1], star[0] = 0, random.randint(0, sw)

    running_pac_x += 4
    if running_pac_x > sw + 500:
        running_pac_x = -200

    anim_toggle_fast = (frame_counter // 15) % 2 == 0
    anim_toggle_slow = (frame_counter // 25) % 2 == 0

    # --- UI Rendering ---
    screen.fill(BG_COLOR)
    screen.blit(bloom_grid_surf, (0, 0))

    for star in stars:
        color = (150,150,150) if star[2] == 1 else WHITE
        pygame.draw.rect(screen, color, (star[0], star[1], star[2], star[2]))

    # Titel
    glow_y = math.sin(frame_counter * 0.05) * (sh * 0.01)
    shift_x = math.sin(frame_counter * 0.1) * (sw * 0.005)
    t_rect = title_font.render("DIGITS ARCADE", True, WHITE).get_rect(center=(sw//2, int(sh*0.15)))
    screen.blit(title_font.render("DIGITS ARCADE", True, (80, 0, 0)), t_rect.move(int(-6 - shift_x), int(6 + glow_y)))
    screen.blit(title_font.render("DIGITS ARCADE", True, (0, 100, 100)), t_rect.move(int(6 + shift_x), int(-6 + glow_y)))
    screen.blit(title_font.render("DIGITS ARCADE", True, WHITE), t_rect.move(0, int(glow_y)))
    draw_punk_underline(t_rect, frame_counter)

    # Menü-Einträge rendern
    for i, game in enumerate(games):
        sel = (i == selected_index)
        txt = game.get('display_name', 'Unbekannt')
        
        wx = math.sin(frame_counter*0.1)*8 if sel else 0
        wy = math.cos(frame_counter*0.1)*2 if sel else 0
        m_rect = menu_font.render(txt, True, WHITE).get_rect(center=(int(sw//2 + wx), int(sh*0.48 + i*sh*0.12 + wy)))
        
        if sel:
            screen.blit(menu_font.render(txt, True, NEON_YELLOW), m_rect)
            padding = sw * 0.03
            drx = math.sin(frame_counter * 0.05) * (sw * 0.015)
            sl_x = m_rect.left - sprites['pac_open'].get_width() - padding + drx
            sr_x = m_rect.right + padding + drx
            sy = m_rect.centery - (sprites['pac_open'].get_height() // 2)
            
            screen.blit(sprites['pac_open'] if anim_toggle_fast else sprites['pac_closed'], (int(sl_x), int(sy)))
            screen.blit(sprites['ghost_red'], (int(sr_x), int(sy)))
        else:
            screen.blit(menu_font.render(txt, True, (120, 120, 150)), m_rect)

    # Deko-Footer Animation
    y_btm = sh * 0.85
    off_btm = 60
    screen.blit(sprites['pac_open'] if anim_toggle_fast else sprites['pac_closed'], (int(running_pac_x), int(y_btm)))
    screen.blit(sprites['ghost_cyan'], (int(running_pac_x - off_btm), int(y_btm)))
    screen.blit(sprites['ghost_red'], (int(running_pac_x - (off_btm * 2)), int(y_btm)))

    if (frame_counter // 20) % 2 == 0:
        f_surf = small_font.render("PRESS SPACE TO TEST LIGHTS", True, NEON_PINK)
        screen.blit(f_surf, (int(sw//2 - f_surf.get_width()//2), int(sh*0.96)))

    draw_scanlines(frame_counter)

    # --- Skalierung & Ausgabe ---
    scale_factor = min(REAL_W / sw, REAL_H / sh)
    new_w = int(sw * scale_factor)
    new_h = int(sh * scale_factor)
    
    scaled_screen = pygame.transform.scale(screen, (new_w, new_h))
    x_offset = (REAL_W - new_w) // 2
    y_offset = (REAL_H - new_h) // 2
    
    real_screen.fill((0, 0, 0))
    real_screen.blit(scaled_screen, (x_offset, y_offset))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()