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

# --- SPRITE MATRIZEN ---

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
    # Fix: Quadratische Pixel durch Verwendung eines einzigen Scale-Werts
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

# Feste Skalierung für alle Sprites (4-8 Pixel pro Matrix-Punkt)
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
for x in range(0, sw, int(sw*0.05)): pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (x, 0), (x, sh), 2)
for y in range(0, sh, int(sh*0.05)): pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (0, y), (sw, y), 2)

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
                            if aktuelles_os in ["Linux", "Darwin"]:
                                # Rechte für den gesamten Ordner fixen (Godot braucht das für .pck)
                                for f in os.listdir(game_dir):
                                    f_p = os.path.join(game_dir, f)
                                    try: os.chmod(f_p, os.stat(f_p).st_mode | 0o111)
                                    except: pass

                            screen.fill(BG_COLOR)
                            l_txt = title_font.render("LOADING...", True, NEON_CYAN)
                            screen.blit(l_txt, l_txt.get_rect(center=(sw//2, sh//2)))
                            pygame.display.flip()
                            
                            if aktuelles_os == "Darwin": pygame.display.iconify()
                            
                            if aktuelles_os == "Darwin" and exe_p.endswith(".app"):
                                subprocess.run(["open", "-W", exe_p], cwd=game_dir)
                            else:
                                subprocess.run([exe_p], cwd=game_dir, check=True)
                            
                            if aktuelles_os == "Darwin": screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            pygame.event.clear()

                        except subprocess.CalledProcessError as e:
                            if e.returncode == -11 or e.returncode == 139:
                                error_message = "CRASH -11: VULKAN/DRIVER ERROR"
                            else:
                                error_message = f"GAME CRASHED (CODE {e.returncode})"
                        except Exception as e:
                            error_message = f"ERROR: {str(e)[:25]}"
                    else:
                        error_message = "EXECUTABLE NOT FOUND"
                else:
                    error_message = "OS NOT SUPPORTED"
            elif event.key == pygame.K_ESCAPE: running = False

    # Rendering
    screen.fill(BG_COLOR)
    screen.blit(bloom_grid_surf, (0, 0))
    for s in stars:
        s[1] = (s[1] + s[2]) % sh
        pygame.draw.rect(screen, (WHITE if s[2] > 1 else (150, 150, 150)), (s[0], s[1], s[2], s[2]))

    # Titel
    t_rect = title_font.render("DIGITS ARCADE", True, WHITE).get_rect(center=(sw//2, sh*0.15))
    screen.blit(title_font.render("DIGITS ARCADE", True, (80, 0, 0)), t_rect.move(4, 4))
    screen.blit(title_font.render("DIGITS ARCADE", True, WHITE), t_rect)
    draw_punk_underline(t_rect, frame_counter)

    # Menü
    if not games:
        err = menu_font.render("games.json missing", True, RED)
        screen.blit(err, err.get_rect(center=(sw//2, sh*0.5)))
    else:
        for i, g in enumerate(games):
            sel = (i == selected_index)
            color = NEON_YELLOW if sel else (120, 120, 150)
            txt = g['display_name']
            m_rect = menu_font.render(txt, True, color).get_rect(center=(sw//2 + (math.sin(frame_counter*0.1)*8 if sel else 0), sh*0.48 + i*sh*0.12))
            screen.blit(menu_font.render(txt, True, color), m_rect)
            
            if sel:
                anim_f = (frame_counter // 15) % 2 == 0
                anim_s = (frame_counter // 25) % 2 == 0
                if "SPACE" in txt.upper():
                    s_l, s_r = (spr_invader1_a if anim_s else spr_invader1_b), (spr_invader2_a if anim_f else spr_invader2_b)
                elif "ASTEROID" in txt.upper():
                    s_l, s_r = (spr_ast_ship_thrust if anim_f else spr_ast_ship), (spr_asteroid1 if anim_s else spr_asteroid2)
                else:
                    s_l, s_r = (spr_pac_open if anim_f else spr_pac_closed), spr_ghost_red
                
                screen.blit(s_l, (m_rect.left - s_l.get_width() - 20, m_rect.centery - s_l.get_height()//2))
                screen.blit(s_r, (m_rect.right + 20, m_rect.centery - s_r.get_height()//2))

    # Laufender Pac-Man am Boden
    running_pac_x = (running_pac_x + 4) if running_pac_x < sw + 500 else -200
    screen.blit(spr_pac_open if (frame_counter//15)%2==0 else spr_pac_closed, (running_pac_x, sh*0.85))
    screen.blit(spr_ghost_cyan, (running_pac_x-80, sh*0.85))
    screen.blit(spr_ghost_red, (running_pac_x-160, sh*0.85))

    # Footer & Error
    if error_message:
        e_surf = small_font.render(error_message, True, RED)
        screen.blit(e_surf, (sw//2 - e_surf.get_width()//2, sh*0.82))
    
    if (frame_counter // 20) % 2 == 0:
        f_surf = small_font.render("PRESS ENTER TO START", True, NEON_PINK)
        screen.blit(f_surf, (sw//2 - f_surf.get_width()//2, sh*0.96))

    draw_scanlines(frame_counter)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
