import pygame
import subprocess
import sys
import os
import platform
import math
import json
import random

# --- Pfad-Logik für PyInstaller ---
if getattr(sys, "frozen", False):
    RESOURCE_PATH = os.path.dirname(sys.executable)
else:
    RESOURCE_PATH = os.path.dirname(os.path.abspath(__file__))

GAME_BASE_PATH = RESOURCE_PATH
os.chdir(RESOURCE_PATH)

def get_path(rel_path):
    return os.path.abspath(os.path.join(RESOURCE_PATH, rel_path))

def get_game_path(rel_path):
    return os.path.abspath(os.path.join(GAME_BASE_PATH, rel_path))

# --- Pygame Setup ---
pygame.init()
pygame.mouse.set_visible(True)
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
sw, sh = screen.get_size()
clock = pygame.time.Clock()

# --- Farben ---
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

# --- Schriftarten ---
try:
    font_path = get_path("assets/arcade.ttf")
    title_font = pygame.font.Font(font_path, int(sh * 0.12))
    menu_font = pygame.font.Font(font_path, int(sh * 0.05))
    small_font = pygame.font.Font(font_path, int(sh * 0.02))
except:
    title_font = pygame.font.Font(None, int(sh * 0.12))
    menu_font = pygame.font.Font(None, int(sh * 0.06))
    small_font = pygame.font.Font(None, int(sh * 0.03))

CONFIG_FILE = os.path.join(RESOURCE_PATH, "games.json")

def load_games_config():
    if not os.path.exists(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            loaded_games = data.get("games", [])
            for game in loaded_games:
                for os_name, rel_path in game["paths"].items():
                    game["paths"][os_name] = get_game_path(rel_path)
            return loaded_games
    except Exception:
        return []

games = load_games_config()

# --- PIXEL ART MATRIZEN ---

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
    "    ######  ",
    " ######### ",
    "###########",
    "####    ####",
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
    "###    #### ",
    "##     ### ",
    "####    ####",
    " ##########",
    "  ######## ",
    "   ######  "
]

def create_sprite(matrix, main_color, scale):
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

scale_size = max(4, int(sh * 0.008))

spr_invader1_a = create_sprite(INVADER_1, NEON_GREEN, scale_size)
spr_invader1_b = create_sprite(INVADER_2, NEON_GREEN, scale_size)
spr_invader2_a = create_sprite(INVADER_2, NEON_CYAN, scale_size)
spr_invader2_b = create_sprite(INVADER_1, NEON_CYAN, scale_size)
spr_pac_open = create_sprite(PACMAN_OPEN, NEON_YELLOW, scale_size)
spr_pac_closed = create_sprite(PACMAN_CLOSED, NEON_YELLOW, scale_size)
spr_ghost_red = create_sprite(GHOST, RED, scale_size)
spr_ghost_cyan = create_sprite(GHOST, NEON_CYAN, scale_size)
spr_ast_ship = create_sprite(ASTEROIDS_SHIP, NEON_PINK, scale_size)
spr_ast_ship_thrust = create_sprite(ASTEROIDS_SHIP_THRUST, NEON_PINK, scale_size)
spr_asteroid1 = create_sprite(ASTEROID_1, NEON_CYAN, scale_size)
spr_asteroid2 = create_sprite(ASTEROID_2, NEON_CYAN, scale_size)

# --- Effekte ---
stars = [[random.randint(0, sw), random.randint(0, sh), random.randint(1, 3)] for _ in range(100)]
bloom_grid_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
for x in range(0, sw, int(sw*0.05)): 
    pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (x, 0), (x, sh), 2)
for y in range(0, sh, int(sh*0.05)): 
    pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (0, y), (sw, y), 2)

def draw_scanlines(frame):
    s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    offset = (frame // 4) % 8
    for y in range(offset, sh, 6):
        pygame.draw.line(s, (0, 0, 0, 160), (0, y), (sw, y), 2)
    screen.blit(s, (0, 0))

def draw_punk_underline(rect, frame):
    num_blocks = 20
    block_width = rect.width // num_blocks
    underline_y = rect.bottom + sh * 0.015
    for i in range(num_blocks):
        color = PUNK_COLORS[(i + (frame // 10)) % len(PUNK_COLORS)]
        offset_y = math.sin(frame * 0.2 + i * 0.5) * (sh * 0.003)
        block_rect = pygame.Rect(rect.left + i * block_width, underline_y + offset_y, block_width - 2, sh * 0.005)
        pygame.draw.rect(screen, color, block_rect, 0, 2)

# --- Schiff Background Logik ---
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
        combined.blit(idle_img, ((combined.get_width()-idle_img.get_width())//2, 0))
        combined.blit(b_img, ((combined.get_width()-b_img.get_width())//2, idle_img.get_height()-5))
        new_h = int(sh * 0.12)
        new_w = int(combined.get_width() * (new_h / combined.get_height()))
        base_ship_images.append(pygame.transform.scale(combined, (new_w, new_h)))
    if len(base_ship_images) == 3: ship_loaded = True
except: pass

# --- MAIN LOOP ---
selected_index = 0
error_message = ""
frame_counter = 0
running_pac_x = -100
running = True

while running:
    frame_counter += 1
    aktuelles_os = platform.system()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        if event.type == pygame.KEYDOWN:
            error_message = ""
            if not games:
                if event.key == pygame.K_ESCAPE: running = False
                continue
            
            if event.key == pygame.K_UP: selected_index = (selected_index - 1) % len(games)
            elif event.key == pygame.K_DOWN: selected_index = (selected_index + 1) % len(games)
            elif event.key == pygame.K_RETURN:
                p_dict = games[selected_index]["paths"]
                if aktuelles_os in p_dict:
                    exe_p = p_dict[aktuelles_os]
                    if os.path.exists(exe_p):
                        try:
                            game_dir = os.path.dirname(exe_p)
                            
                            # --- FIX FÜR LINUX KONFLIKTE ---
                            clean_env = os.environ.copy()
                            for var in ['LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'PYTHONHOME', 'PYTHONPATH']:
                                clean_env.pop(var, None)

                            if aktuelles_os in ["Linux", "Darwin"]:
                                try: os.chmod(exe_p, os.stat(exe_p).st_mode | 0o111)
                                except: pass

                            screen.fill(BG_COLOR)
                            l_txt = title_font.render("LOADING...", True, NEON_CYAN)
                            screen.blit(l_txt, l_txt.get_rect(center=(sw//2, sh//2)))
                            pygame.display.flip()
                            
                            if aktuelles_os == "Darwin": pygame.display.iconify()
                            
                            if aktuelles_os == "Darwin" and exe_p.endswith(".app"):
                                subprocess.run(["open", "-W", exe_p], cwd=game_dir, env=clean_env)
                            else:
                                subprocess.run([exe_p], cwd=game_dir, check=True, env=clean_env)
                            
                            if aktuelles_os == "Darwin": screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            pygame.event.clear()

                        except subprocess.CalledProcessError as e:
                            error_message = f"GAME CRASHED (CODE {e.returncode})"
                        except Exception as e:
                            error_message = f"ERROR: {str(e)[:25]}"
                    else:
                        error_message = "EXECUTABLE NOT FOUND"
                else:
                    error_message = "OS NOT SUPPORTED"
            elif event.key == pygame.K_ESCAPE: running = False

    # Stern-Animation
    for star in stars:
        star[1] += star[2]
        if star[1] > sh:
            star[1], star[0] = 0, random.randint(0, sw)

    # Pac-Man Lauf-Animation
    running_pac_x += 4
    if running_pac_x > sw + 500:
        running_pac_x = -200

    anim_toggle_fast = (frame_counter // 15) % 2 == 0
    anim_toggle_slow = (frame_counter // 25) % 2 == 0

    # Rendering
    screen.fill(BG_COLOR)
    screen.blit(bloom_grid_surf, (0, 0))

    for star in stars:
        color = (150,150,150) if star[2]==1 else WHITE
        pygame.draw.rect(screen, color, (star[0], star[1], star[2], star[2]))

    # --- Fliegendes Schiff im Hintergrund ---
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

    # Titel Rendering
    glow_y = math.sin(frame_counter * 0.05) * (sh * 0.01)
    shift_x = math.sin(frame_counter * 0.1) * (sw * 0.005)
    t_rect = title_font.render("DIGITS ARCADE", True, WHITE).get_rect(center=(sw//2, sh*0.15))
    
    screen.blit(title_font.render("DIGITS ARCADE", True, (80, 0, 0)), t_rect.move(-6 - shift_x, 6 + glow_y))
    screen.blit(title_font.render("DIGITS ARCADE", True, (0, 100, 100)), t_rect.move(6 + shift_x, -6 + glow_y))
    screen.blit(title_font.render("DIGITS ARCADE", True, WHITE), t_rect.move(0, glow_y))
    draw_punk_underline(t_rect, frame_counter)

    # Menü-Einträge
    if not games:
        err_surf = menu_font.render("games.json FEHLT", True, RED)
        screen.blit(err_surf, err_surf.get_rect(center=(sw//2, sh*0.5)))
    else:
        for i, game in enumerate(games):
            sel = (i == selected_index)
            txt = game['display_name']
            
            wx = math.sin(frame_counter*0.1)*8 if sel else 0
            wy = math.cos(frame_counter*0.1)*2 if sel else 0
            m_rect = menu_font.render(txt, True, WHITE).get_rect(center=(sw//2 + wx, sh*0.48 + i*sh*0.12 + wy))
            
            if sel:
                for off in [2, -2]:
                    screen.blit(menu_font.render(txt, True, (200, 200, 0, 150)), m_rect.move(off, off))
                screen.blit(menu_font.render(txt, True, NEON_YELLOW), m_rect)
                
                # Menü-Sprites (Pac-Man, Invader, Asteroids)
                padding = sw * 0.03
                drx = math.sin(frame_counter * 0.05) * (sw * 0.015)
                sl_x = m_rect.left - spr_pac_open.get_width() - padding + drx
                sr_x = m_rect.right + padding + drx
                sy = m_rect.centery - (spr_pac_open.get_height() // 2)
                
                if "SPACE" in txt.upper():
                    s_l, s_r = (spr_invader1_a if anim_toggle_slow else spr_invader1_b), (spr_invader2_a if anim_toggle_fast else spr_invader2_b)
                elif "ASTEROID" in txt.upper():
                    s_l, s_r = (spr_ast_ship_thrust if anim_toggle_fast else spr_ast_ship), (spr_asteroid1 if anim_toggle_slow else spr_asteroid2)
                else:
                    s_l, s_r = (spr_pac_open if anim_toggle_fast else spr_pac_closed), spr_ghost_red
                    
                screen.blit(s_l, (sl_x, sy))
                screen.blit(s_r, (sr_x, sy))
            else:
                screen.blit(menu_font.render(txt, True, (120, 120, 150)), m_rect)

    # Laufender Pac-Man am Boden
    y_btm = sh * 0.85
    off_btm = int(spr_ghost_red.get_width() * 2.5)
    screen.blit(spr_pac_open if anim_toggle_fast else spr_pac_closed, (running_pac_x, y_btm))
    screen.blit(spr_ghost_cyan, (running_pac_x - off_btm, y_btm))
    screen.blit(spr_ghost_red, (running_pac_x - (off_btm * 2), y_btm))

    if (frame_counter // 20) % 2 == 0:
        f_surf = small_font.render("PRESS ENTER TO START", True, NEON_PINK)
        screen.blit(f_surf, (sw//2 - f_surf.get_width()//2, sh*0.96))

    if error_message:
        e_surf = small_font.render(error_message, True, RED)
        screen.blit(e_surf, (sw//2 - e_surf.get_width()//2, sh*0.82))

    draw_scanlines(frame_counter)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
