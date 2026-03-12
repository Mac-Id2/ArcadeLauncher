import pygame
import subprocess
import sys
import os
import platform
import math
import json
import random

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

pygame.init()
pygame.mouse.set_visible(True)
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
sw, sh = screen.get_size()
clock = pygame.time.Clock()

BG_COLOR = (5, 5, 15)      
NEON_CYAN = (0, 255, 255)
NEON_PINK = (255, 20, 147)
NEON_YELLOW = (255, 255, 0)
NEON_GREEN = (57, 255, 20)
NEON_RED = (255, 10, 10) 
WHITE = (255, 255, 255)
RED = (255, 0, 0)
DARK_CYAN = (0, 100, 100)
DARK_PINK = (100, 10, 60)
DARK_RED = (100, 0, 0)
PUNK_COLORS = [NEON_CYAN, NEON_PINK, NEON_YELLOW, NEON_GREEN, NEON_RED]

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
    except Exception as e:
        return []

games = load_games_config()

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
    "   ######  ",
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
    "###   #### ",
    "##     ### ",
    "####   ####",
    " ##########",
    "  ######## ",
    "   ######  "
]

def create_sprite(matrix, main_color, scale):
    w, h = len(matrix[0]), len(matrix)
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for y, row in enumerate(matrix):
        for x, char in enumerate(row):
            color = main_color if char == '#' else (255, 255, 255) if char == 'W' else (30, 30, 255) if char == 'B' else None
            if color: pygame.draw.rect(surf, color, (x * scale, y * scale, scale, scale))
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

stars = [[random.randint(0, sw), random.randint(0, sh), random.randint(1, 3)] for _ in range(100)]
scanline_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
bloom_grid_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
for x in range(0, sw, int(sw*0.05)):
    pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (x, 0), (x, sh), 2)
for y in range(0, sh, int(sh*0.05)):
    pygame.draw.line(bloom_grid_surf, (0, 20, 50, 50), (0, y), (sw, y), 2)

def draw_scanlines(frame):
    scanline_surf.fill((0,0,0,0))
    offset = (frame // 4) % 8
    for y in range(offset, sh, 6):
        pygame.draw.line(scanline_surf, (0, 0, 0, 160), (0, y), (sw, y), 2)
    screen.blit(scanline_surf, (0, 0))

def draw_punk_underline(rect, frame):
    num_blocks = 20
    block_width = rect.width // num_blocks
    underline_y = rect.bottom + sh * 0.015
    wiggle_speed = 0.2
    for i in range(num_blocks):
        color_idx = (i + (frame // 10)) % len(PUNK_COLORS)
        color = PUNK_COLORS[color_idx]
        offset_y = math.sin(frame * wiggle_speed + i * 0.5) * (sh * 0.003)
        offset_x = math.cos(frame * wiggle_speed + i * 0.5) * (sw * 0.001)
        block_rect = pygame.Rect(rect.left + i * block_width + offset_x, underline_y + offset_y, block_width - (sw * 0.002), sh * 0.005)
        glow_surf = pygame.Surface((block_rect.width + 4, block_rect.height + 4), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (color[0], color[1], color[2], 100), (0, 0, glow_surf.get_width(), glow_surf.get_height()), 0, 2)
        screen.blit(glow_surf, (block_rect.x - 2, block_rect.y - 2))
        pygame.draw.rect(screen, color, block_rect, 0, 2)

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
    w_idle, h_idle = idle_img.get_size()
    
    boost_filenames = ["player-boost-default.png", "player-boost-left.png", "player-boost-right.png"]
    for filename in boost_filenames:
        boost_path = get_path(f"assets/{filename}") if os.path.exists(get_path(f"assets/{filename}")) else get_path(filename)
        boost_img = pygame.image.load(boost_path).convert_alpha()
        w_boost, h_boost = boost_img.get_size()
        
        max_w = max(w_idle, w_boost)
        total_h = h_idle + h_boost
        combined_img = pygame.Surface((max_w, total_h), pygame.SRCALPHA)
        
        combined_img.blit(idle_img, ((max_w - w_idle) // 2, 0))
        overlap = int(h_idle * 0.1)
        combined_img.blit(boost_img, ((max_w - w_boost) // 2, h_idle - overlap))
        
        target_height = int(sh * 0.12)
        ratio = target_height / total_h
        target_width = int(max_w * ratio)
        combined_img = pygame.transform.scale(combined_img, (target_width, target_height))
        
        base_ship_images.append(combined_img)
        
    if len(base_ship_images) == 3:
        ship_loaded = True
except Exception as e:
    pass

selected_index = 0
error_message = ""
frame_counter = 0
running_pac_x = -100

running = True
while running:
    frame_counter += 1
    aktuelles_os = platform.system()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            error_message = ""

            if len(games) == 0:
                if event.key == pygame.K_ESCAPE: running = False
                else: error_message = "KEINE SPIELE IN GAMES.JSON GEFUNDEN"
                continue

            if event.key == pygame.K_UP:
                selected_index = (selected_index - 1) % len(games)
            elif event.key == pygame.K_DOWN:
                selected_index = (selected_index + 1) % len(games)
            elif event.key == pygame.K_RETURN:
                path_dict = games[selected_index]["paths"]
                if aktuelles_os in path_dict:
                    exe_path = path_dict[aktuelles_os]
                    
                    is_mac_app = aktuelles_os == "Darwin" and exe_path.endswith(".app")
                    
                    if os.path.exists(exe_path):
                        try:
                            screen.fill(BG_COLOR)
                            loading_txt = title_font.render("LOADING...", True, NEON_CYAN)
                            screen.blit(loading_txt, loading_txt.get_rect(center=(sw//2, sh//2)))
                            pygame.display.flip()
                            
                            spiel_ordner = os.path.dirname(exe_path)

                            if aktuelles_os == "Darwin":
                                pygame.display.set_mode((sw, sh)) 
                                pygame.display.iconify() 
                            
                            if is_mac_app:
                                subprocess.run(["open", "-W", exe_path], cwd=spiel_ordner)
                            else:
                                subprocess.run([exe_path], cwd=spiel_ordner)
                            
                            if aktuelles_os == "Darwin":
                                screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                            
                            pygame.event.clear()
                        except Exception as e:
                            error_message = f"ERROR: {e}"
                    else:
                        error_message = f"NOT FOUND: {os.path.basename(exe_path)}"
                else:
                    error_message = f"OS '{aktuelles_os}' NOT SUPPORTED"
            elif event.key == pygame.K_ESCAPE:
                running = False
                
    for star in stars:
        star[1] += star[2]
        if star[1] > sh:
            star[1], star[0] = 0, random.randint(0, sw)

    running_pac_x += 4
    if running_pac_x > sw + 500:
        running_pac_x = -200

    anim_toggle_fast = (frame_counter // 15) % 2 == 0
    anim_toggle_slow = (frame_counter // 25) % 2 == 0

    screen.fill(BG_COLOR)
    screen.blit(bloom_grid_surf, (0, 0))

    for star in stars:
        color = (150,150,150) if star[2]==1 else WHITE
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
    title_rect = title_font.render("DIGITS ARCADE", True, WHITE).get_rect(center=(sw//2, sh*0.15))
    
    glow_surf = title_font.render("DIGITS ARCADE", True, (DARK_RED[0], 20, 20))
    screen.blit(glow_surf, title_rect.move(-6 - shift_x, 6 + glow_y))
    screen.blit(title_font.render("DIGITS ARCADE", True, (DARK_CYAN[0], 100, 100)), title_rect.move(6 + shift_x, -6 + glow_y))
    screen.blit(title_font.render("DIGITS ARCADE", True, WHITE), title_rect.move(0, glow_y))
    draw_punk_underline(title_rect, frame_counter)

    if not games:
        err_surf = menu_font.render("games.json FEHLT", True, RED)
        screen.blit(err_surf, err_surf.get_rect(center=(sw//2, sh*0.5)))
    else:
        for i, game in enumerate(games):
            is_selected = (i == selected_index)
            txt = game['display_name']
            
            wiggle_x = math.sin(frame_counter*0.1)*8 if is_selected else 0
            wiggle_y = math.cos(frame_counter*0.1)*2 if is_selected else 0
            game_rect = menu_font.render(txt, True, WHITE).get_rect(center=(sw//2 + wiggle_x, sh*0.48 + i*sh*0.12 + wiggle_y))
            
            if is_selected:
                color = NEON_YELLOW
                for off in [2, -2]:
                    glow_surf = menu_font.render(txt, True, (200, 200, 0, 150))
                    screen.blit(glow_surf, game_rect.move(off, off))
                
                game_surf = menu_font.render(txt, True, color)
                screen.blit(game_surf, game_rect)
                
                padding = sw * 0.03
                drift_speed = 0.05
                drift_range = sw * 0.015
                drift_x = math.sin(frame_counter * drift_speed) * drift_range
                
                sprite_left_x = game_rect.left - spr_pac_open.get_width() - padding + drift_x
                sprite_right_x = game_rect.right + padding + drift_x
                sprite_y = game_rect.centery - (spr_pac_open.get_height() // 2) + int(sh * 0.010)
                
                if "SPACE" in txt.upper():
                    spr_left = spr_invader1_a if anim_toggle_slow else spr_invader1_b
                    spr_right = spr_invader2_a if anim_toggle_fast else spr_invader2_b
                elif "ASTEROID" in txt.upper():
                    spr_left = spr_ast_ship_thrust if anim_toggle_fast else spr_ast_ship
                    spr_right = spr_asteroid1 if anim_toggle_slow else spr_asteroid2
                else:
                    spr_left = spr_pac_open if anim_toggle_fast else spr_pac_closed
                    spr_right = spr_ghost_red
                    
                screen.blit(spr_left, (sprite_left_x, sprite_y))
                screen.blit(spr_right, (sprite_right_x, sprite_y))
                
            else:
                color = (120, 120, 150)
                game_surf = menu_font.render(txt, True, color)
                screen.blit(game_surf, game_rect)

    y_pos_bottom = sh * 0.85
    offset = int(spr_ghost_red.get_width() * 2.5)
    screen.blit(spr_pac_open if anim_toggle_fast else spr_pac_closed, (running_pac_x, y_pos_bottom))
    screen.blit(spr_ghost_cyan, (running_pac_x - offset, y_pos_bottom))
    screen.blit(spr_ghost_red, (running_pac_x - (offset*2), y_pos_bottom))

    if (frame_counter // 20) % 2 == 0:
        footer_surf = small_font.render("PRESS ENTER TO START", True, NEON_PINK)
        screen.blit(footer_surf, (sw//2 - footer_surf.get_width()//2, sh*0.96))

    if error_message:
        err_surf = small_font.render(error_message, True, RED)
        screen.blit(err_surf, (sw//2 - err_surf.get_width()//2, sh*0.82))

    draw_scanlines(frame_counter)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()