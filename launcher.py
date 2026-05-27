
import pygame
import subprocess
import sys
import os
import platform
import math
import random
import logging
import time
from LedController import LedController

from config import *
from assets import init_sprites
from led_bridge import get_bridge

# --- SDL2 Fix für Linux (Fokus-Verlust) ---
# Zwingt Pygame dazu, sich NICHT in den Hintergrund zu minimieren, 
# wenn das Spiel startet und den Fokus klaut.
os.environ['SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS'] = '0'

# --- Initialisierung: Pygame & Display ---
pygame.init()
pygame.mouse.set_visible(False)

# 1. Physische Bildschirmauflösung ermitteln (Fullscreen für ALLE Systeme)
real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
REAL_W, REAL_H = real_screen.get_size()

# 2. Virtuelle Zeichenfläche (16:9 Basis-Auflösung) für konsistentes UI-Rendering initialisieren
sw, sh = 1280, 720
screen = pygame.Surface((sw, sh)) # Sämtliche Zeichenoperationen erfolgen auf dieser virtuellen Surface.

clock = pygame.time.Clock()

# --- LED Controller Initialisierung & Aktivierung ---
led = LedController()
led.attract_resume() # Ruhezustand/Ambient-Licht beim Starten des Launchers aktivieren

logging.info(f"System-Info: {platform.system()} | Echter Monitor: {REAL_W}x{REAL_H} | Virtuell: {sw}x{sh}")

# --- LED Bridge starten (Hintergrund-Thread) ----------------------------------
led = get_bridge()
led.start()

# --- Laden der Assets & Typografie ---
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

# --- Initialisierung der visuellen Hintergrund-Effekte ---
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

# --- Ladelogik: Animiertes Hintergrund-Sprite (Asteroids-Schiff) ---
base_ship_images = []
ship_loaded = False
ship_active = False
ship_x, ship_y = -1000, -1000
ship_vx, ship_vy = 0, 0
ship_speed = sw * 0.004
ship_rotated_frames = []

try:
    idle_path = get_path("assets/player-idle.png") if os.path.exists(get_path("assets/player-idle.png")) else get_path("player-idle.png")
    idle_img = pygame.image.load(idle_path).convert_alpha()
    for filename in ["player-boost-default.png", "player-boost-left.png", "player-boost-right.png"]:
        p = get_path(f"assets/{filename}") if os.path.exists(get_path(f"assets/{filename}")) else get_path(filename)
        b_img = pygame.image.load(p).convert_alpha()
        
        combined = pygame.Surface((max(idle_img.get_width(), b_img.get_width()), idle_img.get_height() + b_img.get_height()), pygame.SRCALPHA)
        flame_y = idle_img.get_height() - 2
        combined.blit(b_img, ((combined.get_width() - b_img.get_width()) // 2, flame_y))
        combined.blit(idle_img, ((combined.get_width() - idle_img.get_width()) // 2, 0))
        
        new_h = int(sh * 0.12)
        new_w = int(combined.get_width() * (new_h / combined.get_height()))
        base_ship_images.append(pygame.transform.scale(combined, (new_w, new_h)))
        
    if len(base_ship_images) == 3: 
        ship_loaded = True
except: pass

# --- Hauptschleife (Main Loop) Setup ---
selected_index = 0
prev_selected_index = -1   # LED: Selektionsänderung erkennen
error_message = ""
frame_counter = 0
running_pac_x = -200
running = True

# Initiale LED-Selektion setzen sobald Spiele geladen sind
if games:
    led.notify_selection_changed(games[0].get("display_name", ""))

while running:
    frame_counter += 1
    aktuelles_os = platform.system()

    # --- Ereignisverarbeitung (Event Handling) ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT: 
            logging.info("Beenden durch User (QUIT Event).")
            running = False
        
        if event.type == pygame.KEYDOWN:
            error_message = ""
            if not games:
                if event.key == pygame.K_ESCAPE: 
                    running = False
                continue
            
            # Navigation mit LED-Feedback (Kurzer Cyan-Blink)
            if event.key == pygame.K_w: 
                selected_index = (selected_index - 1) % len(games)
                led.send_effect(chain="A", effect_type="blink", segment=99, r=0, g=230, b=255, speed=80, repeat=1, priority=2, event_key="menu_scroll")
            elif event.key == pygame.K_s: 
                selected_index = (selected_index + 1) % len(games)
                led.send_effect(chain="A", effect_type="blink", segment=99, r=0, g=230, b=255, speed=80, repeat=1, priority=2, event_key="menu_scroll")
            
            # --- ECHTEN SPIELSTART TRIGGERN ---
            elif event.key == pygame.K_SPACE:
                game = games[selected_index]
                game_name = game.get("display_name", "Unbekanntes Spiel")
                p_dict = game.get("paths", {})
                
                logging.info(f"Start-Versuch: {game_name} auf OS: {aktuelles_os}")
                
                if aktuelles_os in p_dict:
                    exe_p = p_dict[aktuelles_os]
                    
                    if os.path.exists(exe_p):
                        try:
                            game_dir = os.path.dirname(exe_p)

                            # LED-Startsequenz zünden & Ambient-Modus pausieren
                            led.attract_pause()
                            game_identifier = game_name.upper()
                            if "SPACE" in game_identifier:
                                led.effect_start_space_invaders()  # Grüner Matrix-Wipe
                            elif "ASTEROID" in game_identifier:
                                led.effect_start_asteroids()       # Weißer, kühler Puls
                            else:
                                led.effect_start_pacman()          # Gelber Chase/Lauflicht-Effekt
                            
                            # --- 1. PYINSTALLER ENVIRONMENT CLEANUP ---
                            clean_env = os.environ.copy()
                            vars_to_remove = [
                                'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'PYTHONHOME', 'PYTHONPATH', 
                                '_MEIPASS', '_MEIPASS2'
                            ]
                            for k in list(clean_env.keys()):
                                if k.startswith('_PYI_') or k in vars_to_remove:
                                    clean_env.pop(k, None)
                                
                            if hasattr(sys, '_MEIPASS'):
                                mei_path = os.path.normcase(sys._MEIPASS) 
                                current_path = clean_env.get('PATH', '')
                                clean_paths = [
                                    p for p in current_path.split(os.pathsep) 
                                    if mei_path not in os.path.normcase(p)
                                ]
                                clean_env['PATH'] = os.pathsep.join(clean_paths)

                            if aktuelles_os in ["Linux", "Darwin"]:
                                try: os.chmod(exe_p, os.stat(exe_p).st_mode | 0o111)
                                except Exception as e: logging.warning(f"Konnte chmod nicht setzen: {e}")

                            # --- 2. LADEBILDSCHIRM ANZEIGEN ---
                            screen.fill(BG_COLOR)
                            l_txt = title_font.render("LOADING...", True, NEON_CYAN)
                            screen.blit(l_txt, l_txt.get_rect(center=(sw//2, sh//2)))
                            
                            scale_f = min(REAL_W / sw, REAL_H / sh)
                            temp_scaled = pygame.transform.scale(screen, (int(sw * scale_f), int(sh * scale_f)))
                            real_screen.fill((0, 0, 0))
                            real_screen.blit(temp_scaled, ((REAL_W - temp_scaled.get_width()) // 2, (REAL_H - temp_scaled.get_height()) // 2))
                            pygame.display.flip()
                            
                            if aktuelles_os == "Darwin": pygame.display.iconify()
                            
                            # --- 3. PROZESS STARTEN ---

                            # --- LED: Spiel-Start-Effekt ---
                            led.notify_game_start(game_name)

                            # --- SPIEL STARTEN ---
                            if aktuelles_os == "Darwin" and exe_p.endswith(".app"):
                                process = subprocess.Popen(["open", "-W", exe_p], cwd=game_dir, env=clean_env)
                            else:
                                process = subprocess.Popen([exe_p], cwd=game_dir, env=clean_env)

                            logging.info(f"Spiel läuft im Vordergrund.")
                            
                            # Blockierende Überwachungsschleife: Wartet, bis das Spiel geschlossen wird

                            # Blockierende Überwachungsschleife: Prüft periodisch den Prozessstatus
                            while True:
                                if process.poll() is not None:
                                    logging.info(f"Erfolgreich beendet: {game_name}")
                                    
                                    # LED-Beendigungssequenz zünden & Ambient wieder anwerfen
                                    led.attract_resume()     # Reaktiviert das Ambient-Menü-Licht
                                    break
                                    
                                # WICHTIG: Sagt dem OS, dass das Fenster noch "lebt", und leert angestaute Events (verhindert das Einfrieren)
                                pygame.event.pump()
                                pygame.event.clear()
                                
                                pygame.time.wait(1000) # Polling-Intervall (1 Sekunde)

                            # --- OS-Workaround: Fenster-Fokus (Linux & Mac) ---
                            if aktuelles_os == "Linux":
                                logging.info("Linux: Führe Display-Reset durch, um Fokus zurückzuholen.")
                                pygame.time.wait(200)
                                pygame.display.quit()
                                pygame.display.init()
                                pygame.mouse.set_visible(False)
                                real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            elif aktuelles_os == "Darwin":
                                real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                                
                            pygame.event.clear()

                        except Exception as e:
                            logging.error(f"UNERWARTETER FEHLER beim Start von {game_name}: {e}")
                            error_message = f"ERROR: {str(e)[:25]}"
                            led.attract_resume() # Notfall-Fallback, damit LEDs nicht aus bleiben
                    else:
                        error_message = "EXECUTABLE NOT FOUND"
                else:
                    error_message = "OS NOT SUPPORTED"
            
            elif event.key == pygame.K_ESCAPE: 
                running = False

    # --- Aktualisierung der Spiel- und Animationslogik ---
    for star in stars:
        star[1] += star[2]
        if star[1] > sh:
            star[1], star[0] = 0, random.randint(0, sw)

    running_pac_x += 4
    if running_pac_x > sw + 500:
        running_pac_x = -200

    anim_toggle_fast = (frame_counter // 15) % 2 == 0
    anim_toggle_slow = (frame_counter // 25) % 2 == 0

    # --- Rendern der Szene (Virtuelle Surface) ---
    screen.fill(BG_COLOR)
    screen.blit(bloom_grid_surf, (0, 0))

    for star in stars:
        color = (150,150,150) if star[2] == 1 else WHITE
        pygame.draw.rect(screen, color, (star[0], star[1], star[2], star[2]))

    if ship_loaded:
        if not ship_active:
            side = random.choice(['top', 'right', 'bottom', 'left'])
            if side == 'top':
                ship_x, ship_y = random.randint(0, sw), -200
                target_x, target_y = random.randint(0, sw), sh + 200
            elif side == 'bottom':
                ship_x, ship_y = random.randint(0, sw), sh + 200
                target_x, target_y = random.randint(0, sw), -200
            elif side == 'left':
                ship_x, ship_y = -200, random.randint(0, sh)
                target_x, target_y = sw + 200, random.randint(0, sh)
            else:
                ship_x, ship_y = sw + 200, random.randint(0, sh)
                target_x, target_y = -200, random.randint(0, sh)

            dx = target_x - ship_x
            dy = target_y - ship_y
            dist = math.hypot(dx, dy)
            if dist != 0:
                ship_vx = (dx / dist) * ship_speed
                ship_vy = (dy / dist) * ship_speed
            else:
                ship_vx, ship_vy = ship_speed, 0

            angle = math.degrees(math.atan2(-dy, dx)) - 90
            ship_rotated_frames = [pygame.transform.rotate(img, angle) for img in base_ship_images]
            ship_active = True

        ship_x += ship_vx
        ship_y += ship_vy

        if ship_x < -300 or ship_x > sw + 300 or ship_y < -300 or ship_y > sh + 300:
            ship_active = False

        if ship_active:
            boost_index = (frame_counter // 5) % 3
            current_ship = ship_rotated_frames[boost_index]
            ship_rect = current_ship.get_rect(center=(int(ship_x), int(ship_y)))
            screen.blit(current_ship, ship_rect)

    glow_y = math.sin(frame_counter * 0.05) * (sh * 0.01)
    shift_x = math.sin(frame_counter * 0.1) * (sw * 0.005)
    t_rect = title_font.render("DIGITS ARCADE", True, WHITE).get_rect(center=(sw//2, int(sh*0.15)))
    
    screen.blit(title_font.render("DIGITS ARCADE", True, (80, 0, 0)), t_rect.move(int(-6 - shift_x), int(6 + glow_y)))
    screen.blit(title_font.render("DIGITS ARCADE", True, (0, 100, 100)), t_rect.move(int(6 + shift_x), int(-6 + glow_y)))
    screen.blit(title_font.render("DIGITS ARCADE", True, WHITE), t_rect.move(0, int(glow_y)))
    draw_punk_underline(t_rect, frame_counter)

    if not games:
        err_surf = menu_font.render("games.json FEHLT", True, RED)
        screen.blit(err_surf, err_surf.get_rect(center=(sw//2, int(sh*0.5))))
    else:
        for i, game in enumerate(games):
            sel = (i == selected_index)
            txt = game.get('display_name', 'Unbekannt')
            
            wx = math.sin(frame_counter*0.1)*8 if sel else 0
            wy = math.cos(frame_counter*0.1)*2 if sel else 0
            m_rect = menu_font.render(txt, True, WHITE).get_rect(center=(int(sw//2 + wx), int(sh*0.48 + i*sh*0.12 + wy)))
            
            if sel:
                for off in [2, -2]:
                    shadow_surf = menu_font.render(txt, True, (100, 100, 0))
                    screen.blit(shadow_surf, m_rect.move(off, off))
                    
                screen.blit(menu_font.render(txt, True, NEON_YELLOW), m_rect)
                
                padding = sw * 0.03
                drx = math.sin(frame_counter * 0.05) * (sw * 0.015)
                sl_x = m_rect.left - sprites['pac_open'].get_width() - padding + drx
                sr_x = m_rect.right + padding + drx
                sy = m_rect.centery - (sprites['pac_open'].get_height() // 2)
                
                if "SPACE" in txt.upper():
                    s_l, s_r = (sprites['invader1_a'] if anim_toggle_slow else sprites['invader1_b']), (sprites['invader2_a'] if anim_toggle_fast else sprites['invader2_b'])
                elif "ASTEROID" in txt.upper():
                    s_l, s_r = (sprites['ast_ship_thrust'] if anim_toggle_fast else sprites['ast_ship']), (sprites['asteroid1'] if anim_toggle_slow else sprites['asteroid2'])
                else:
                    s_l, s_r = (sprites['pac_open'] if anim_toggle_fast else sprites['pac_closed']), sprites['ghost_red']
                    
                screen.blit(s_l, (int(sl_x), int(sy)))
                screen.blit(s_r, (int(sr_x), int(sy)))
            else:
                screen.blit(menu_font.render(txt, True, (120, 120, 150)), m_rect)

    y_btm = sh * 0.85
    off_btm = int(sprites['ghost_red'].get_width() * 2.5)
    screen.blit(sprites['pac_open'] if anim_toggle_fast else sprites['pac_closed'], (int(running_pac_x), int(y_btm)))
    screen.blit(sprites['ghost_cyan'], (int(running_pac_x - off_btm), int(y_btm)))
    screen.blit(sprites['ghost_red'], (int(running_pac_x - (off_btm * 2)), int(y_btm)))

    if (frame_counter // 20) % 2 == 0:
        f_surf = small_font.render("PRESS BUTTON TO START", True, NEON_PINK)
        screen.blit(f_surf, (int(sw//2 - f_surf.get_width()//2), int(sh*0.96)))

    if error_message:
        e_surf = small_font.render(error_message, True, RED)
        screen.blit(e_surf, (int(sw//2 - e_surf.get_width()//2), int(sh*0.82)))

    draw_scanlines(frame_counter)

    # --- Finales Rendering: Letterboxing & Skalierung ---
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

logging.info("=== LAUNCHER WIRD BEENDET ===")
led.notify_launcher_exit()   # Power-Down-Animation → alle LEDs aus
pygame.quit()
sys.exit()