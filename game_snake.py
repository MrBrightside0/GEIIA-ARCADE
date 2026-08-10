import pygame
import random
import sys
import os
import math
import subprocess
from collections import deque

import geiia_core as core

# ==================== CONFIGURACIÓN ====================
# Mismo tamaño de ventana que los otros tres juegos: que el arcade completo
# se vea parejo importa más que los 220 px extra de cancha.
WIDTH, HEIGHT = 1120, 760
UI_HEIGHT = 106  # barra GEIIA (45) + marcador propio del juego
GRID_SIZE = 20
FPS_DRAW = 60

START_SPEED = 9       
SPEED_INCREMENT = 0.2
MAX_SPEED = 24
POWERUP_SPAWN_CHANCE = 0.02
WIN_SCORE = 8000       

# ==================== TEMAS ====================
THEMES = [
    {"name": "NEON WARFARE", "bg": (10, 10, 20), "grid": (25, 25, 45), "p1": (0, 255, 255), "ai": (255, 0, 100), "food": (255, 255, 0), "trail": True},
    {"name": "MATRIX", "bg": (0, 10, 0), "grid": (0, 40, 0), "p1": (50, 255, 50), "ai": (0, 150, 0), "food": (200, 255, 200), "trail": False},
    {"name": "VAPORWAVE", "bg": (45, 10, 80), "grid": (0, 180, 180), "p1": (255, 100, 200), "ai": (100, 255, 255), "food": (255, 255, 0), "trail": True}
]

UP = (0, -1); DOWN = (0, 1); LEFT = (-1, 0); RIGHT = (1, 0)

# ==================== CLASES VISUALES ====================
class Particle:
    def __init__(self, x, y, color):
        self.x = x; self.y = y; self.color = color
        self.size = random.randint(4, 8)
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-3, 3)
        self.life = 255

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.life -= 10; self.size *= 0.95

    def draw(self, surf):
        if self.life > 0:
            s = pygame.Surface((int(self.size)*2, int(self.size)*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, max(0, self.life)), (int(self.size), int(self.size)), int(self.size))
            surf.blit(s, (int(self.x), int(self.y)))

class FloatingText:
    def __init__(self, text, x, y, color, font):
        self.text = text; self.x = x; self.y = y; self.color = color; self.font = font
        self.life = 60; self.y_offset = 0
    def update(self): self.life -= 1; self.y_offset -= 1.5
    def draw(self, surf):
        if self.life > 0:
            alpha = min(255, self.life * 5)
            txt_surf = self.font.render(self.text, True, self.color)
            txt_surf.set_alpha(alpha)
            surf.blit(txt_surf, (self.x - txt_surf.get_width()//2, self.y + self.y_offset))

class Trail:
    def __init__(self, x, y, color):
        self.x = x; self.y = y; self.color = color; self.life = 100
    def update(self): self.life -= 5
    def draw(self, surf):
        if self.life > 0:
            s = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)
            s.fill((*self.color, max(0, self.life//2))) 
            surf.blit(s, (self.x, self.y))

# ==================== MAIN GAME ====================
class SnakeGame:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        try: pygame.mixer.init()
        except: pass
        
        self.load_assets()
        
        # Misma ventana que los demas juegos: SCALED es lo que hace que F11
        # funcione, y trae respaldo si SDL no consigue renderer acelerado.
        self.screen = core.abrir_pantalla("GEIIA NEURAL SNAKE")
        self.clock = pygame.time.Clock()
        
        # Misma escala tipografica que el resto del arcade
        self.fonts = core.build_fonts()
        self.font_big = self.fonts["xl"]
        self.font_ui = self.fonts["sm"]
        self.font_float = self.fonts["xs"]
        
        self.theme_idx = 0
        self.state = "MENU"
        self.menu_anim = 0
        self.score_p1 = 0
        self.score_ai = 0
        self.win_reason = ""
        
        self.reset_game_vars()

    def load_assets(self):
        self.sounds = {}
        files = {
            "eat": "eat.wav", "crash": "crash.wav", "start": "start.wav",
            "powerup": "powerup.wav", "win": "win.wav", "warp": "warp.wav", "break": "break.wav" 
        }
        base_path = os.path.join("sounds", "snake")
        
        if not os.path.exists(base_path):
            os.makedirs(base_path, exist_ok=True)
        
        for name, filename in files.items():
            full_path = os.path.join(base_path, filename)
            if os.path.exists(full_path):
                try:
                    self.sounds[name] = pygame.mixer.Sound(full_path)
                    self.sounds[name].set_volume(0.4)
                except: self.sounds[name] = None
            else: self.sounds[name] = None

    def safe_play(self, name):
        if self.sounds.get(name):
            try: self.sounds[name].play()
            except: pass

    def return_to_main(self):
        """Cierra el juego y regresa al menú principal.

        Si el menú fue quien nos lanzó, él ya está esperando a que salgamos y
        se muestra solo: abrir otro proceso apilaría menús duplicados.
        """
        pygame.quit()
        if not os.environ.get("GEIIA_FROM_MENU"):
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                subprocess.Popen([sys.executable, os.path.join(base, "main_menu.py")])
            except Exception as e:
                print(f"Error launching menu: {e}")
        sys.exit()

    def reset_game_vars(self):
        self.powerup = None
        
        mid_y = HEIGHT // 2
        start_y = (mid_y // GRID_SIZE) * GRID_SIZE 
        
        self.player = {
            "body": deque([(140, start_y), (120, start_y), (100, start_y)]), 
            "dir": RIGHT, "next_dir": RIGHT, "score": 0, "alive": True,
            "shield": False, "speed_boost": 0, "invulnerable": 0, "combo": 0, "combo_timer": 0
        }
        self.ai = {
            "body": deque([(WIDTH-140, start_y), (WIDTH-120, start_y), (WIDTH-100, start_y)]), 
            "dir": LEFT, "score": 0, "alive": True,
            "shield": False, "speed_boost": 0, "invulnerable": 0, "combo": 0, "combo_timer": 0
        }
        
        self.particles = []
        self.floating_texts = []
        self.trails = []
        self.snake_speed = START_SPEED
        self.move_timer = 0
        self.shake = 0
        self.food = self.get_random_pos()

    def spawn_particles(self, x, y, color, count=10):
        for _ in range(count):
            px = x + GRID_SIZE // 2
            py = y + GRID_SIZE // 2
            self.particles.append(Particle(px, py, color))

    def get_random_pos(self):
        while True:
            available_h = HEIGHT - UI_HEIGHT
            rows = available_h // GRID_SIZE
            cols = WIDTH // GRID_SIZE
            r_col = random.randint(1, cols - 2)
            r_row = random.randint(1, rows - 2)
            x = r_col * GRID_SIZE
            y = UI_HEIGHT + (r_row * GRID_SIZE)
            y = (y // GRID_SIZE) * GRID_SIZE
            pos = (x, y)
            
            collision = False
            for b in self.player["body"]:
                if pos == b: collision = True
            for b in self.ai["body"]:
                if pos == b: collision = True
            if self.powerup and pos == self.powerup["pos"]: collision = True
            
            if not collision: return pos

    def spawn_powerup(self):
        if self.powerup is None and random.random() < POWERUP_SPAWN_CHANCE:
            types = ["SHIELD", "SHIELD", "SPEED", "POINTS"]
            self.powerup = {
                "pos": self.get_random_pos(),
                "type": random.choice(types),
                "life": 600 
            }

    def teleport_safe(self, snake):
        safe_pos = self.get_random_pos()
        head_x, head_y = safe_pos
        
        new_body = deque([])
        direction_x = -GRID_SIZE if head_x > WIDTH//2 else GRID_SIZE
        length = len(snake["body"])
        for i in range(length):
            new_body.append((head_x + (i * direction_x), head_y))
            
        snake["body"] = new_body
        new_dir = LEFT if direction_x == GRID_SIZE else RIGHT
        snake["dir"] = new_dir
        if snake == self.player: snake["next_dir"] = new_dir
            
        snake["invulnerable"] = 60 
        self.safe_play("warp") 
        self.spawn_particles(head_x, head_y, (255, 255, 255), 30)

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    core.alternar_pantalla_completa()
                    continue
                if event.key == pygame.K_ESCAPE:
                    if self.state == "MENU":
                        self.return_to_main()
                    else:
                        self.state = "MENU"; self.safe_play("start")
                
                if self.state == "MENU":
                    if event.key == pygame.K_SPACE:
                        self.reset_game_vars(); self.state = "PLAYING"; self.safe_play("start")
                    if event.key == pygame.K_RIGHT: 
                        self.theme_idx = (self.theme_idx + 1) % len(THEMES); self.safe_play("eat")
                
                elif self.state == "GAMEOVER":
                    if event.key == pygame.K_r: 
                        self.reset_game_vars(); self.state = "PLAYING"; self.safe_play("start")
                    if event.key == pygame.K_SPACE:
                        self.state = "MENU"; self.safe_play("start")

                elif self.state == "PLAYING":
                    d = self.player["dir"]
                    if event.key == pygame.K_UP and d != DOWN: self.player["next_dir"] = UP
                    elif event.key == pygame.K_DOWN and d != UP: self.player["next_dir"] = DOWN
                    elif event.key == pygame.K_LEFT and d != RIGHT: self.player["next_dir"] = LEFT
                    elif event.key == pygame.K_RIGHT and d != LEFT: self.player["next_dir"] = RIGHT

    def move_logic(self):
        self.spawn_powerup()
        if self.powerup:
            self.powerup["life"] -= 1
            if self.powerup["life"] <= 0: self.powerup = None

        for s in [self.player, self.ai]:
            if s["speed_boost"] > 0: s["speed_boost"] -= 1
            if s["invulnerable"] > 0: s["invulnerable"] -= 1
            if s["combo_timer"] > 0: s["combo_timer"] -= 1
            else: s["combo"] = 0

        p_ate = self.step(self.player, False, self.ai)
        ai_ate = self.step(self.ai, True, self.player)

        if p_ate or ai_ate:
            self.food = self.get_random_pos()
            self.snake_speed = min(MAX_SPEED, self.snake_speed + SPEED_INCREMENT)

        if self.player["score"] >= WIN_SCORE:
            self.state = "GAMEOVER"; self.win_reason = "SCORE LIMIT REACHED!"
            self.score_p1 += 1; self.safe_play("win")
            return
        elif self.ai["score"] >= WIN_SCORE:
            self.state = "GAMEOVER"; self.win_reason = "AI REACHED SCORE LIMIT!"
            self.score_ai += 1; self.safe_play("crash")
            return

        if not self.player["alive"] or not self.ai["alive"]:
            self.state = "GAMEOVER"; self.shake = 20; self.safe_play("crash")
            if self.player["alive"]: 
                self.score_p1 += 1; self.win_reason = "OPPONENT ELIMINATED"
            elif self.ai["alive"]: 
                self.score_ai += 1; self.win_reason = "ELIMINATED"
            else:
                self.win_reason = "DOUBLE CRASH"

    def step(self, snake, is_ai, enemy):
        if not snake["alive"]: return False
        if is_ai: self.ai_logic(snake, enemy)
        else: snake["dir"] = snake["next_dir"]

        head = snake["body"][0]
        dx, dy = snake["dir"]
        new_head = (head[0] + dx*GRID_SIZE, head[1] + dy*GRID_SIZE)

        hit_wall = not (0 <= new_head[0] < WIDTH and UI_HEIGHT <= new_head[1] < HEIGHT)
        hit_self = new_head in snake["body"]
        hit_enemy = new_head in enemy["body"]

        if hit_wall or hit_self or hit_enemy:
            if snake["invulnerable"] > 0:
                snake["dir"] = (-dx, -dy)
                if not is_ai: snake["next_dir"] = (-dx, -dy)
                return False
            if snake["shield"]:
                snake["shield"] = False
                self.teleport_safe(snake)
                self.floating_texts.append(FloatingText("SHIELD SAVED!", head[0], head[1], (200, 200, 255), self.font_ui))
                return False
            else:
                snake["alive"] = False
                self.spawn_particles(head[0], head[1], (255, 50, 50), 30)
                return False

        snake["body"].appendleft(new_head)
        if THEMES[self.theme_idx].get("trail", False):
            t_col = THEMES[self.theme_idx]["ai"] if is_ai else THEMES[self.theme_idx]["p1"]
            self.trails.append(Trail(new_head[0], new_head[1], t_col))

        if new_head == self.food:
            snake["score"] += 100
            self.safe_play("eat")
            self.spawn_particles(new_head[0], new_head[1], THEMES[self.theme_idx]["food"], 15)
            
            snake["combo"] += 1; snake["combo_timer"] = 120 
            
            if enemy["combo"] > 0:
                enemy["combo"] = 0
                e_head = enemy["body"][0]
                self.floating_texts.append(FloatingText("COMBO BROKEN!", e_head[0], e_head[1]-30, (255, 50, 50), self.font_float))
                self.safe_play("break")

            if snake["combo"] > 1:
                txt = f"{snake['combo']}x COMBO!"
                col = (255, 215, 0) if not is_ai else (255, 150, 150)
                self.floating_texts.append(FloatingText(txt, new_head[0], new_head[1]-20, col, self.font_float))
                snake["score"] += 50 * snake["combo"]
            return True
        
        elif self.powerup and new_head == self.powerup["pos"]:
            ptype = self.powerup["type"]
            self.safe_play("powerup")
            if ptype == "SHIELD":
                snake["shield"] = True
                self.floating_texts.append(FloatingText("SHIELD!", new_head[0], new_head[1], (200, 200, 255), self.font_float))
            elif ptype == "SPEED":
                snake["speed_boost"] = 80
                self.floating_texts.append(FloatingText("SPEED!", new_head[0], new_head[1], (100, 255, 255), self.font_float))
            elif ptype == "POINTS":
                snake["score"] += 500
                self.floating_texts.append(FloatingText("+500!", new_head[0], new_head[1], (255, 255, 100), self.font_float))
            self.powerup = None
            snake["body"].pop()
        else:
            snake["body"].pop()
        return False

    def ai_logic(self, snake, enemy):
        head = snake["body"][0]
        target = self.food
        if self.powerup: target = self.powerup["pos"]
        
        valid_moves = []
        for d in [UP, DOWN, LEFT, RIGHT]:
            new_pos = (head[0] + d[0]*GRID_SIZE, head[1] + d[1]*GRID_SIZE)
            if (0 <= new_pos[0] < WIDTH and UI_HEIGHT <= new_pos[1] < HEIGHT and 
                new_pos not in snake["body"] and new_pos not in enemy["body"]):
                dist = abs(new_pos[0] - target[0]) + abs(new_pos[1] - target[1])
                valid_moves.append((dist, d))
        
        if valid_moves:
            valid_moves.sort(key=lambda x: x[0])
            if random.random() < 0.05 and len(valid_moves) > 1: snake["dir"] = valid_moves[1][1]
            else: snake["dir"] = valid_moves[0][1]

    def draw_glow_rect(self, surf, color, rect, glow_size=8):
        s = pygame.Surface((rect[2]+glow_size*2, rect[3]+glow_size*2), pygame.SRCALPHA)
        pygame.draw.rect(s, (*color, 60), (0, 0, rect[2]+glow_size*2, rect[3]+glow_size*2), border_radius=glow_size)
        surf.blit(s, (rect[0]-glow_size, rect[1]-glow_size))
        pygame.draw.rect(surf, color, rect, border_radius=4)

    def draw(self):
        t = THEMES[self.theme_idx]
        ox, oy = 0, 0
        if self.shake > 0:
            ox, oy = random.randint(-4, 4), random.randint(-4, 4)
            self.shake -= 1

        canvas = pygame.Surface((WIDTH, HEIGHT))
        canvas.fill(t["bg"])

        for x in range(0, WIDTH, GRID_SIZE): pygame.draw.line(canvas, t["grid"], (x, UI_HEIGHT), (x, HEIGHT))
        for y in range(UI_HEIGHT, HEIGHT, GRID_SIZE): pygame.draw.line(canvas, t["grid"], (0, y), (WIDTH, y))

        for trail in self.trails: trail.update(); trail.draw(canvas)
        self.trails = [tr for tr in self.trails if tr.life > 0]

        if self.state in ["PLAYING", "GAMEOVER", "MENU"]:
            pulse = math.sin(pygame.time.get_ticks() * 0.01) * 3
            f_rect = (self.food[0]-pulse, self.food[1]-pulse, GRID_SIZE+pulse*2, GRID_SIZE+pulse*2)
            self.draw_glow_rect(canvas, t["food"], f_rect, 12)

            if self.powerup:
                p_colors = {"SHIELD": (200, 200, 255), "SPEED": (100, 255, 255), "POINTS": (255, 215, 0)}
                col = p_colors[self.powerup["type"]]
                p_rect = (self.powerup["pos"][0]-2, self.powerup["pos"][1]-2, GRID_SIZE+4, GRID_SIZE+4)
                self.draw_glow_rect(canvas, col, p_rect, 15)
                font = pygame.font.SysFont("Arial", 12, bold=True)
                letter = self.powerup["type"][0]
                txt = font.render(letter, True, (0,0,0))
                canvas.blit(txt, (self.powerup["pos"][0]+6, self.powerup["pos"][1]+4))

            for snake, color in [(self.player, t["p1"]), (self.ai, t["ai"])]:
                for i, segment in enumerate(snake["body"]):
                    rect = (segment[0], segment[1], GRID_SIZE-1, GRID_SIZE-1)
                    if snake["invulnerable"] > 0 and (pygame.time.get_ticks() // 100) % 2 == 0: continue
                    if snake["shield"]:
                        pygame.draw.rect(canvas, (255, 255, 255), (segment[0]-2, segment[1]-2, GRID_SIZE+3, GRID_SIZE+3), 1)
                    if i == 0: 
                        self.draw_glow_rect(canvas, color, rect, 8)
                        eye_col = (0,0,0)
                        pygame.draw.circle(canvas, eye_col, (segment[0]+5, segment[1]+5), 2)
                        pygame.draw.circle(canvas, eye_col, (segment[0]+15, segment[1]+5), 2)
                    else: 
                        pygame.draw.rect(canvas, color, rect, border_radius=2)

            for p in self.particles: p.update(); p.draw(canvas)
            self.particles = [p for p in self.particles if p.life > 0]
            for txt in self.floating_texts: txt.update(); txt.draw(canvas)
            self.floating_texts = [txt for txt in self.floating_texts if txt.life > 0]

            top = core.snap(46)
            core.block(canvas, core.C_BG, (0, top, WIDTH, UI_HEIGHT - top))
            core.block(canvas, core.C_GRID, (0, UI_HEIGHT - core.PIXEL, WIDTH, core.PIXEL))
            cy = top + (UI_HEIGHT - top) // 2

            core.text_at(canvas, self.font_ui, f"P1 {self.player['score']}", t["p1"], 34, cy, "midleft")
            core.text_at(canvas, self.font_ui, f"IA {self.ai['score']}", t["ai"], WIDTH - 34, cy, "midright")
            core.text_at(canvas, self.font_ui, f"{self.score_p1} - {self.score_ai}",
                         core.C_INK, WIDTH // 2, cy)
            core.text_at(canvas, self.font_float, "RONDAS", core.C_DIM, WIDTH // 2, top + 14)

            estados = []
            if self.player["shield"]:
                estados.append(("ESCUDO", core.C_AZUL))
            if self.player["speed_boost"] > 0:
                estados.append(("TURBO", core.C_AMBAR))
            for i, (txt, col) in enumerate(estados):
                core.text_at(canvas, self.font_float, txt, col, 34, UI_HEIGHT + 18 + i * 22, "midleft")

        if self.state == "MENU":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180)); canvas.blit(overlay, (0, 0))
            # Sin latido de escala: deformar texto pixelado lo despedaza.
            self.menu_anim += 0.05
            title = self.font_big.render("NEURAL SNAKE", True, t["p1"])
            sub = self.font_ui.render("TOURNAMENT EDITION", True, (200, 200, 200))
            parpadeo = (pygame.time.get_ticks() // 450) % 2 == 0
            start = self.font_ui.render("> ESPACIO PARA JUGAR <" if parpadeo else "", True, core.C_INK)
            skin = self.font_ui.render(f"< ESTILO: {t['name']} >", True, t["food"])
            
            global_stat = self.font_ui.render(f"GOAL: {WIN_SCORE} PTS", True, (255, 215, 0))

            cx, cy = WIDTH//2, HEIGHT//2
            canvas.blit(title, (cx - title.get_width()//2, cy - 150))
            canvas.blit(sub, (cx - sub.get_width()//2, cy - 70))
            canvas.blit(global_stat, (cx - global_stat.get_width()//2, cy))
            canvas.blit(skin, (cx - skin.get_width()//2, cy + 60))
            canvas.blit(start, (cx - start.get_width()//2, cy + 150))
            legend = self.font_float.render("S = SPEED   W = SHIELD   P = POINTS", True, (150, 150, 150))
            canvas.blit(legend, (cx - legend.get_width()//2, HEIGHT - 50))

        elif self.state == "GAMEOVER":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150)); canvas.blit(overlay, (0, 0))
            if self.player["alive"] and not self.ai["alive"]:
                msg = "VICTORY!"; col = t["p1"]
            elif not self.player["alive"]:
                msg = "DEFEAT"; col = t["ai"]
            elif self.player["score"] >= WIN_SCORE:
                msg = "SCORE VICTORY!"; col = t["p1"]
            elif self.ai["score"] >= WIN_SCORE:
                msg = "AI VICTORY"; col = t["ai"]
            else:
                msg = "DRAW"; col = (255, 255, 255)
            
            t_msg = self.font_big.render(msg, True, col)
            t_reason = self.font_ui.render(self.win_reason if self.win_reason else "GAME OVER", True, (200, 200, 200))
            t_r = self.font_ui.render("[R] REVANCHA   -   [ESC] MENU", True, (255, 255, 255))
            
            canvas.blit(t_msg, (WIDTH//2 - t_msg.get_width()//2, HEIGHT//2 - 80))
            canvas.blit(t_reason, (WIDTH//2 - t_reason.get_width()//2, HEIGHT//2))
            canvas.blit(t_r, (WIDTH//2 - t_r.get_width()//2, HEIGHT//2 + 80))

        core.draw_chrome(canvas, self.fonts, "NEURAL SNAKE",
                         "ESC MENU    ESPACIO JUGAR    F11 PANTALLA")
        core.presentar(canvas, (ox, oy))

    def run(self):
        while True:
            self.handle_input()
            if self.state == "PLAYING":
                self.move_timer += 1
                limit = 60 / self.snake_speed
                if self.player["speed_boost"] > 0: limit *= 0.7 
                
                if self.move_timer >= limit:
                    self.move_timer = 0
                    self.move_logic()
            self.draw()
            self.clock.tick(FPS_DRAW)

if __name__ == "__main__":
    game = SnakeGame()
    game.run()