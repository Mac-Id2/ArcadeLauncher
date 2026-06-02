import pygame
import subprocess
import sys
import os
import platform
import math
import random
import logging
import time
from config import *
from assets import init_sprites
from led_bridge import get_bridge

os.environ['SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS'] = '0'

VIRTUAL_W, VIRTUAL_H = 1280, 720


class DisplayManager:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.mouse.set_visible(False)
        self._real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.real_w, self.real_h = self._real_screen.get_size()
        self._virtual = pygame.Surface((VIRTUAL_W, VIRTUAL_H))

    @property
    def virtual(self) -> pygame.Surface:
        return self._virtual

    @property
    def size(self) -> tuple:
        return VIRTUAL_W, VIRTUAL_H

    def present(self) -> None:
        scale = min(self.real_w / VIRTUAL_W, self.real_h / VIRTUAL_H)
        w, h = int(VIRTUAL_W * scale), int(VIRTUAL_H * scale)
        scaled = pygame.transform.scale(self._virtual, (w, h))
        self._real_screen.fill((0, 0, 0))
        self._real_screen.blit(scaled, ((self.real_w - w) // 2, (self.real_h - h) // 2))
        pygame.display.flip()

    def show_loading(self, title_font: pygame.font.Font) -> None:
        self._virtual.fill(BG_COLOR)
        txt = title_font.render("LOADING...", True, NEON_CYAN)
        self._virtual.blit(txt, txt.get_rect(center=(VIRTUAL_W // 2, VIRTUAL_H // 2)))
        self.present()

    def reset_after_game(self, current_os: str) -> None:
        if current_os == "Linux":
            pygame.time.wait(200)
            pygame.display.quit()
            pygame.display.init()
            pygame.mouse.set_visible(False)
            self._real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        elif current_os == "Darwin":
            self._real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.event.clear()


class FontManager:
    def __init__(self, sh: int):
        try:
            path = get_path("assets/arcade.ttf")
            self.title = pygame.font.Font(path, int(sh * 0.12))
            self.menu = pygame.font.Font(path, int(sh * 0.05))
            self.small = pygame.font.Font(path, int(sh * 0.02))
        except Exception as e:
            logging.warning("Arcade-Font nicht gefunden, Fallback: %s", e)
            self.title = pygame.font.Font(None, int(sh * 0.12))
            self.menu = pygame.font.Font(None, int(sh * 0.06))
            self.small = pygame.font.Font(None, int(sh * 0.03))


class ShipSprite:
    def __init__(self, sw: int, sh: int):
        self.sw, self.sh = sw, sh
        self._speed = sw * 0.004
        self._base_images = self._load_images(sh)
        self._active = False
        self._x = self._y = -1000.0
        self._vx = self._vy = 0.0
        self._rotated_frames: list = []

    @staticmethod
    def _find_asset(name: str) -> str:
        """Sucht Asset zuerst in assets/, dann im Launcher-Verzeichnis."""
        in_assets = get_path(f"assets/{name}")
        return in_assets if os.path.exists(in_assets) else get_path(name)

    @staticmethod
    def _load_images(sh: int) -> list:
        images = []
        try:
            idle_img = pygame.image.load(ShipSprite._find_asset("player-idle.png")).convert_alpha()
            for filename in ["player-boost-default.png", "player-boost-left.png", "player-boost-right.png"]:
                boost_img = pygame.image.load(ShipSprite._find_asset(filename)).convert_alpha()
                combined = pygame.Surface(
                    (max(idle_img.get_width(), boost_img.get_width()),
                     idle_img.get_height() + boost_img.get_height()),
                    pygame.SRCALPHA,
                )
                flame_y = idle_img.get_height() - 2
                combined.blit(boost_img, ((combined.get_width() - boost_img.get_width()) // 2, flame_y))
                combined.blit(idle_img, ((combined.get_width() - idle_img.get_width()) // 2, 0))
                new_h = int(sh * 0.12)
                new_w = int(combined.get_width() * (new_h / combined.get_height()))
                images.append(pygame.transform.scale(combined, (new_w, new_h)))
            if len(images) != 3:
                return []
        except Exception as e:
            logging.warning("Schiff-Sprites konnten nicht geladen werden: %s", e)
            return []
        return images

    def update(self) -> None:
        if not self._base_images:
            return
        if not self._active:
            self._spawn()
            return
        self._x += self._vx
        self._y += self._vy
        if self._x < -300 or self._x > self.sw + 300 or self._y < -300 or self._y > self.sh + 300:
            self._active = False

    def _spawn(self) -> None:
        side = random.choice(['top', 'right', 'bottom', 'left'])
        if side == 'top':
            self._x, self._y = float(random.randint(0, self.sw)), -200.0
            tx, ty = float(random.randint(0, self.sw)), self.sh + 200.0
        elif side == 'bottom':
            self._x, self._y = float(random.randint(0, self.sw)), self.sh + 200.0
            tx, ty = float(random.randint(0, self.sw)), -200.0
        elif side == 'left':
            self._x, self._y = -200.0, float(random.randint(0, self.sh))
            tx, ty = self.sw + 200.0, float(random.randint(0, self.sh))
        else:
            self._x, self._y = self.sw + 200.0, float(random.randint(0, self.sh))
            tx, ty = -200.0, float(random.randint(0, self.sh))

        dx, dy = tx - self._x, ty - self._y
        dist = math.hypot(dx, dy)
        self._vx, self._vy = ((dx / dist) * self._speed, (dy / dist) * self._speed) if dist else (self._speed, 0.0)
        angle = math.degrees(math.atan2(-dy, dx)) - 90
        self._rotated_frames = [pygame.transform.rotate(img, angle) for img in self._base_images]
        self._active = True

    def draw(self, surface: pygame.Surface, frame: int) -> None:
        if not self._active or not self._rotated_frames:
            return
        img = self._rotated_frames[(frame // 5) % 3]
        surface.blit(img, img.get_rect(center=(int(self._x), int(self._y))))


class BackgroundScene:
    def __init__(self, sw: int, sh: int):
        self.sw, self.sh = sw, sh
        self._stars = [[random.randint(0, sw), random.randint(0, sh), random.randint(1, 3)] for _ in range(100)]
        self._bloom_grid = self._build_bloom_grid(sw, sh)
        self._scanlines = self._build_scanlines(sw, sh)
        self._ship = ShipSprite(sw, sh)

    @staticmethod
    def _build_bloom_grid(sw: int, sh: int) -> pygame.Surface:
        surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for x in range(0, sw, int(sw * 0.05)):
            pygame.draw.line(surf, (0, 20, 50, 50), (x, 0), (x, sh), 2)
        for y in range(0, sh, int(sh * 0.05)):
            pygame.draw.line(surf, (0, 20, 50, 50), (0, y), (sw, y), 2)
        return surf

    @staticmethod
    def _build_scanlines(sw: int, sh: int) -> pygame.Surface:
        surf = pygame.Surface((sw, sh + 10), pygame.SRCALPHA)
        for y in range(0, sh + 10, 6):
            pygame.draw.line(surf, (0, 0, 0, 160), (0, y), (sw, y), 2)
        return surf

    def update(self) -> None:
        for star in self._stars:
            star[1] += star[2]
            if star[1] > self.sh:
                star[1], star[0] = 0, random.randint(0, self.sw)
        self._ship.update()

    def draw(self, surface: pygame.Surface, frame: int) -> None:
        surface.blit(self._bloom_grid, (0, 0))
        for star in self._stars:
            color = (150, 150, 150) if star[2] == 1 else WHITE
            pygame.draw.rect(surface, color, (star[0], star[1], star[2], star[2]))
        self._ship.draw(surface, frame)

    def draw_scanlines(self, surface: pygame.Surface, frame: int) -> None:
        surface.blit(self._scanlines, (0, -((frame // 4) % 6)))


class TitleRenderer:
    def __init__(self, sw: int, sh: int, font: pygame.font.Font):
        self.sw, self.sh = sw, sh
        self._font = font

    def draw(self, surface: pygame.Surface, frame: int) -> None:
        glow_y = math.sin(frame * 0.05) * (self.sh * 0.01)
        shift_x = math.sin(frame * 0.1) * (self.sw * 0.005)
        t_rect = self._font.render("DIGITS ARCADE", True, WHITE).get_rect(
            center=(self.sw // 2, int(self.sh * 0.15))
        )
        surface.blit(self._font.render("DIGITS ARCADE", True, (80, 0, 0)),
                     t_rect.move(int(-6 - shift_x), int(6 + glow_y)))
        surface.blit(self._font.render("DIGITS ARCADE", True, (0, 100, 100)),
                     t_rect.move(int(6 + shift_x), int(-6 + glow_y)))
        surface.blit(self._font.render("DIGITS ARCADE", True, WHITE),
                     t_rect.move(0, int(glow_y)))
        self._draw_punk_underline(surface, t_rect, frame)

    def _draw_punk_underline(self, surface: pygame.Surface, rect: pygame.Rect, frame: int) -> None:
        num_blocks = 20
        block_width = max(1, rect.width // num_blocks)
        underline_y = rect.bottom + self.sh * 0.015
        for i in range(num_blocks):
            color = PUNK_COLORS[(i + (frame // 10)) % len(PUNK_COLORS)]
            offset_y = math.sin(frame * 0.2 + i * 0.5) * (self.sh * 0.003)
            pygame.draw.rect(
                surface, color,
                pygame.Rect(rect.left + i * block_width, underline_y + offset_y, block_width - 2, self.sh * 0.005)
            )


class MenuView:
    def __init__(self, sw: int, sh: int, fonts: FontManager, sprites: dict):
        self.sw, self.sh = sw, sh
        self._fonts = fonts
        self._sprites = sprites
        self._pac_x = -200.0

    def update(self) -> None:
        self._pac_x += 4
        if self._pac_x > self.sw + 500:
            self._pac_x = -200.0

    def draw(self, surface: pygame.Surface, games: list, selected: int, error: str, frame: int) -> None:
        fast = (frame // 15) % 2 == 0
        slow = (frame // 25) % 2 == 0

        if not games:
            surf = self._fonts.menu.render("games.json FEHLT", True, RED)
            surface.blit(surf, surf.get_rect(center=(self.sw // 2, int(self.sh * 0.5))))
        else:
            for i, game in enumerate(games):
                self._draw_item(surface, game, i, i == selected, frame, fast, slow)

        self._draw_bottom_animation(surface, fast)

        if (frame // 20) % 2 == 0:
            f_surf = self._fonts.small.render("PRESS BUTTON TO START", True, NEON_PINK)
            surface.blit(f_surf, (int(self.sw // 2 - f_surf.get_width() // 2), int(self.sh * 0.96)))

        if error:
            e_surf = self._fonts.small.render(error, True, RED)
            surface.blit(e_surf, (int(self.sw // 2 - e_surf.get_width() // 2), int(self.sh * 0.82)))

    def _draw_item(self, surface: pygame.Surface, game: dict, index: int,
                   selected: bool, frame: int, fast: bool, slow: bool) -> None:
        display = game.get('display_name', game.get('name', 'Unbekannt'))
        name    = game.get('name', '')
        wx = math.sin(frame * 0.1) * 8 if selected else 0
        wy = math.cos(frame * 0.1) * 2 if selected else 0
        m_rect = self._fonts.menu.render(display, True, WHITE).get_rect(
            center=(int(self.sw // 2 + wx), int(self.sh * 0.48 + index * self.sh * 0.12 + wy))
        )
        if selected:
            for off in [2, -2]:
                surface.blit(self._fonts.menu.render(display, True, (100, 100, 0)), m_rect.move(off, off))
            surface.blit(self._fonts.menu.render(display, True, NEON_YELLOW), m_rect)
            self._draw_selection_sprites(surface, name, m_rect, frame, fast, slow)
        else:
            surface.blit(self._fonts.menu.render(display, True, (120, 120, 150)), m_rect)

    def _draw_selection_sprites(self, surface: pygame.Surface, name: str,
                                 m_rect: pygame.Rect, frame: int, fast: bool, slow: bool) -> None:
        padding = self.sw * 0.03
        drx = math.sin(frame * 0.05) * (self.sw * 0.015)
        sl_x = m_rect.left - self._sprites['pac_open'].get_width() - padding + drx
        sr_x = m_rect.right + padding + drx
        sy = m_rect.centery - (self._sprites['pac_open'].get_height() // 2)

        name_upper = name.upper()
        if "SPACE" in name_upper:
            s_l = self._sprites['invader1_a'] if slow else self._sprites['invader1_b']
            s_r = self._sprites['invader2_a'] if fast else self._sprites['invader2_b']
        elif "ASTEROID" in name_upper:
            s_l = self._sprites['ast_ship_thrust'] if fast else self._sprites['ast_ship']
            s_r = self._sprites['asteroid1'] if slow else self._sprites['asteroid2']
        else:
            s_l = self._sprites['pac_open'] if fast else self._sprites['pac_closed']
            s_r = self._sprites['ghost_red']

        surface.blit(s_l, (int(sl_x), int(sy)))
        surface.blit(s_r, (int(sr_x), int(sy)))

    def _draw_bottom_animation(self, surface: pygame.Surface, fast: bool) -> None:
        y = int(self.sh * 0.85)
        off = int(self._sprites['ghost_red'].get_width() * 2.5)
        x = int(self._pac_x)
        surface.blit(self._sprites['pac_open'] if fast else self._sprites['pac_closed'], (x, y))
        surface.blit(self._sprites['ghost_cyan'], (x - off, y))
        surface.blit(self._sprites['ghost_red'], (x - off * 2, y))


class MusicPlayer:
    _CANDIDATES = ["assets/arcade-music-loop.mp3", "assets/arcade-music-loop.wav",]

    def __init__(self, volume: float = 0.3) -> None:
        self._available = False
        for rel in self._CANDIDATES:
            path = get_path(rel)
            if not os.path.exists(path):
                continue
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(volume)
                self._available = True
                logging.info("Hintergrundmusik geladen: %s", path)
                break
            except Exception as e:
                logging.warning("Musikdatei nicht ladbar (%s): %s", path, e)
        if not self._available:
            logging.info("Keine Musikdatei gefunden — Hintergrundmusik deaktiviert.")

    def play(self) -> None:
        if not self._available:
            return
        try:
            pygame.mixer.music.play(-1)
        except Exception as e:
            logging.warning("Musik-Wiedergabe fehlgeschlagen: %s", e)

    def stop(self) -> None:
        if not self._available:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


class GameLaunchError(Exception):
    pass


class GameRunner:
    def __init__(self, bridge, display: DisplayManager, title_font: pygame.font.Font):
        self._bridge = bridge
        self._display = display
        self._title_font = title_font
        self._current_os = platform.system()

    def launch(self, game: dict) -> None:
        game_name = game.get("name", "Unbekanntes Spiel")
        exe_path = game.get("paths", {}).get(self._current_os)

        if not exe_path:
            raise GameLaunchError("OS NOT SUPPORTED")
        if not os.path.exists(exe_path):
            raise GameLaunchError("EXECUTABLE NOT FOUND")

        env = self._build_clean_env(exe_path)
        self._display.show_loading(self._title_font)

        if self._current_os == "Darwin":
            pygame.display.iconify()

        self._bridge.notify_game_start(game_name)
        try:
            process = self._start_process(exe_path, env)
            logging.info("Spiel '%s' läuft.", game_name)
            self._wait_for_process(process)
        except Exception:
            self._bridge.notify_game_stop()
            raise

        logging.info("Spiel '%s' beendet.", game_name)
        self._bridge.notify_game_stop()
        self._display.reset_after_game(self._current_os)

    def _build_clean_env(self, exe_path: str) -> dict:
        env = os.environ.copy()
        remove = {'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'PYTHONHOME', 'PYTHONPATH', '_MEIPASS', '_MEIPASS2'}
        for key in [k for k in env if k.startswith('_PYI_') or k in remove]:
            env.pop(key, None)
        if hasattr(sys, '_MEIPASS'):
            mei = os.path.normcase(sys._MEIPASS)
            env['PATH'] = os.pathsep.join(
                p for p in env.get('PATH', '').split(os.pathsep)
                if mei not in os.path.normcase(p)
            )
        if self._current_os in ("Linux", "Darwin"):
            try:
                os.chmod(exe_path, os.stat(exe_path).st_mode | 0o111)
            except Exception as e:
                logging.warning("chmod fehlgeschlagen: %s", e)
        return env

    def _start_process(self, exe_path: str, env: dict) -> subprocess.Popen:
        game_dir = os.path.dirname(exe_path)
        if self._current_os == "Darwin" and exe_path.endswith(".app"):
            return subprocess.Popen(["open", "-W", exe_path], cwd=game_dir, env=env)
        return subprocess.Popen([exe_path], cwd=game_dir, env=env)

    @staticmethod
    def _wait_for_process(process: subprocess.Popen) -> None:
        while process.poll() is None:
            pygame.event.pump()
            pygame.event.clear()
            pygame.time.wait(1000)


class ArcadeLauncher:
    def __init__(self):
        self._display = DisplayManager()
        sw, sh = self._display.size
        self._fonts = FontManager(sh)
        self._sprites = init_sprites(sh)
        self._bridge = self._init_bridge()
        self._background = BackgroundScene(sw, sh)
        self._title = TitleRenderer(sw, sh, self._fonts.title)
        self._menu = MenuView(sw, sh, self._fonts, self._sprites)
        self._runner = GameRunner(self._bridge, self._display, self._fonts.title)
        self._music = MusicPlayer()
        self._games = games
        self._selected = 0
        self._error = ""
        self._frame = 0
        self._clock = pygame.time.Clock()

        logging.info("System: %s | Display: %dx%d → virtuell %dx%d",
                     platform.system(), self._display.real_w, self._display.real_h, sw, sh)

        if self._games:
            self._bridge.notify_selection_changed(self._games[self._selected].get("name", ""))
        self._music.play()

    @staticmethod
    def _init_bridge():
        bridge = get_bridge()
        bridge.start()
        time.sleep(2.0)
        bridge.notify_game_stop()
        return bridge

    def run(self) -> None:
        running = True
        while running:
            self._frame += 1
            running = self._handle_events()
            self._update()
            self._render()
            self._clock.tick(60)
        self._shutdown()

    def _handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if not self._handle_keydown(event.key):
                    return False
        return True

    def _handle_keydown(self, key: int) -> bool:
        self._error = ""
        if key == pygame.K_ESCAPE:
            return False
        if not self._games:
            return True
        if key == pygame.K_w:
            self._select(self._selected - 1)
        elif key == pygame.K_s:
            self._select(self._selected + 1)
        elif key == pygame.K_SPACE:
            self._launch_selected()
        return True

    def _select(self, index: int) -> None:
        self._selected = index % len(self._games)
        self._bridge.notify_selection_changed(self._games[self._selected].get("name", ""))

    def _launch_selected(self) -> None:
        self._music.stop()
        try:
            self._runner.launch(self._games[self._selected])
        except GameLaunchError as e:
            self._error = str(e)
        except Exception as e:
            logging.error("Unerwarteter Fehler beim Spielstart: %s", e)
            self._error = f"ERROR: {str(e)[:25]}"
        finally:
            self._music.play()

    def _update(self) -> None:
        self._background.update()
        self._menu.update()

    def _render(self) -> None:
        surface = self._display.virtual
        surface.fill(BG_COLOR)
        self._background.draw(surface, self._frame)
        self._title.draw(surface, self._frame)
        self._menu.draw(surface, self._games, self._selected, self._error, self._frame)
        self._background.draw_scanlines(surface, self._frame)
        self._display.present()

    def _shutdown(self) -> None:
        logging.info("=== LAUNCHER WIRD BEENDET ===")
        self._music.stop()
        self._bridge.notify_launcher_exit()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    ArcadeLauncher().run()
