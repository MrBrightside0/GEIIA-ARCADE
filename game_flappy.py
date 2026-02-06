import pygame
import sys
import os
import random
import math
import numpy as np
import subprocess

try:
    import sounddevice as sd
    AUDIO_INPUT_AVAILABLE = True
except ImportError:
    AUDIO_INPUT_AVAILABLE = False

WIDTH, HEIGHT = 900, 760
FPS = 60

C_BG = (5, 5, 12)
C_GRID = (30, 30, 60)
C_TEXT = (255, 255, 255)
C_ACCENT = (0, 255, 255)
C_LIFE = (255, 50, 80)

GRAVITY = 0.4
FLAP_FORCE = -9
FLAP_SUSTAIN = -0.8
MAX_FALL = 8
PIPE_GAP = 280
PIPE_SPEED_START = 3.5

class AudioHandler:
    def __init__(self):
        self.volume = 0
        self.stream = None
        if AUDIO_INPUT_AVAILABLE:
            try:
                self.stream = sd.InputStream(callback=self.callback)
                self.stream.start()
            except: pass

    def callback(self, indata, frames, time, status):
        if indata.any():
            self.volume = np.linalg.norm(indata) * 10
        else:
            self.volume = 0

    def close(self):
        if self.stream: self.stream.stop(); self.stream.close()

class SkinManager:
    def __init__(self):
        self.skins = [
            {"name": "NEON JET", "color": (0, 255, 255), "trail": (255, 0, 128)},
            {"name": "U.F.O.",   "color": (0, 255, 0),   "trail": (50, 255, 50)},
            {"name": "GHOST",    "color": (255, 255, 255),"trail": (100, 100, 255)},
            {"name": "MUSIC",    "color": (255, 0, 255), "trail": (0, 255, 255)}
        ]
        self.current_idx = 0

    def get_current(self):
        return self.skins[self.current_idx]

    def next_skin(self):
        self.current_idx = (self.current_idx + 1) % len(self.skins)

    def prev_skin(self):
        self.current_idx = (self.current_idx - 1) % len(self.skins)

    def draw_player(self, surf, x, y, size, angle, glow_radius):
        skin = self.skins[self.current_idx]
        col = skin["color"]
        
        glow_size = int(size + 5 + glow_radius)
        glow_s = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*col, 40), (glow_size, glow_size), glow_size)
        surf.blit(glow_s, (x + size//2 - glow_size, y + size//2 - glow_size))

        cx, cy = x + size//2, y + size//2
        
        if skin["name"] == "NEON JET":
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            pts = [(18, 0), (-12, -12), (-12, 12)]
            r_pts = []
            for px, py in pts:
                r_pts.append((cx + px*cos_a - py*sin_a, cy + px*sin_a + py*cos_a))
            pygame.draw.polygon(surf, col, r_pts, 2)
            pygame.draw.polygon(surf, (255,255,255), r_pts, 0)

        elif skin["name"] == "U.F.O.":
            rect = pygame.Rect(x, y + 5, size, size//1.5)
            pygame.draw.ellipse(surf, col, rect, 2)
            pygame.draw.arc(surf, (200, 200, 255), (x+5, y-5, size-10, size), 0, 3.14, 2)
            pygame.draw.circle(surf, (255,0,0), (x+5, y+15), 2)
            pygame.draw.circle(surf, (255,0,0), (x+size-5, y+15), 2)

        elif skin["name"] == "GHOST":
            rect = pygame.Rect(x+5, y, size-10, size-5)
            pygame.draw.rect(surf, col, rect, border_top_left_radius=10, border_top_right_radius=10)
            pygame.draw.circle(surf, (0,0,0), (x+12, y+10), 4)
            pygame.draw.circle(surf, (0,0,0), (x+size-12, y+10), 4)

        elif skin["name"] == "MUSIC":
            pygame.draw.circle(surf, col, (x+10, y+25), 8)
            pygame.draw.line(surf, col, (x+16, y+25), (x+16, y-5), 4)
            pygame.draw.line(surf, col, (x+16, y-5), (x+26, y+5), 4)

class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.vx = -5
        self.vy = random.uniform(-2, 2)
        self.life = 255
        self.color = color
        self.size = random.randint(3, 6)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 15
        self.size *= 0.9

    def draw(self, surf):
        if self.life > 0:
            s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, self.life), (self.size, self.size), self.size)
            surf.blit(s, (self.x, self.y))

class Player:
    def __init__(self, skin_mgr):
        self.x, self.y = 150, HEIGHT // 2
        self.vel = 0
        self.size = 32
        self.rect = pygame.Rect(self.x, self.y, self.size, self.size)
        self.angle = 0
        self.glow = 0
        self.skin_mgr = skin_mgr
        self.invulnerable = 0 

    def update(self, is_screaming, vol):
        self.vel += GRAVITY
        if is_screaming:
            self.vel += FLAP_SUSTAIN
            if self.vel < -8: self.vel = -8
        
        if self.vel > MAX_FALL: self.vel = MAX_FALL
        self.y += self.vel
        self.rect.y = int(self.y)

        if self.y < 0: self.y = 0; self.vel = 0
        if self.y > HEIGHT - self.size: self.y = HEIGHT - self.size; self.vel = 0

        target = -self.vel * 3
        self.angle += (target - self.angle) * 0.1
        self.glow += (vol * 40 - self.glow) * 0.2
        
        if self.invulnerable > 0: self.invulnerable -= 1

    def draw(self, surf):
        if self.invulnerable > 0 and (pygame.time.get_ticks() // 100) % 2 == 0:
            return 
        self.skin_mgr.draw_player(surf, int(self.x), int(self.y), self.size, self.angle, self.glow)

class Pipe:
    def __init__(self, x):
        self.x = x
        self.w = 70
        self.top_h = random.randint(50, HEIGHT - 50 - PIPE_GAP)
        self.passed = False
        self.color = (random.randint(50,100), random.randint(150,255), 255)

    def update(self, speed):
        self.x -= speed

    def draw(self, surf, pulse):
        glow_w = int(2 + pulse)
        r_top = pygame.Rect(self.x, 0, self.w, self.top_h)
        r_bot = pygame.Rect(self.x, self.top_h + PIPE_GAP, self.w, HEIGHT)
        
        for r in [r_top, r_bot]:
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill((*self.color, 50))
            surf.blit(s, (r.x, r.y))
            pygame.draw.rect(surf, self.color, r, 2, border_radius=4)
            pygame.draw.line(surf, self.color, (r.centerx, r.y), (r.centerx, r.y+r.h), 1)

    def collide(self, rect):
        r_top = pygame.Rect(self.x+5, 0, self.w-10, self.top_h)
        r_bot = pygame.Rect(self.x+5, self.top_h + PIPE_GAP, self.w-10, HEIGHT)
        return r_top.colliderect(rect) or r_bot.colliderect(rect)

class FlappyGame:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        try: pygame.mixer.init()
        except: pass
        
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("GEIIA NEON SCREAM")
        self.clock = pygame.time.Clock()
        
        self.font_L = pygame.font.SysFont("Impact", 80)
        self.font_M = pygame.font.SysFont("Arial", 30, bold=True)
        self.font_S = pygame.font.SysFont("Arial", 18)
        
        self.audio = AudioHandler()
        self.skin_mgr = SkinManager()
        self.sounds = {}
        self.load_sounds()
        
        self.threshold = 0.15
        self.high_score = 0
        self.scroll = 0
        
        self.reset()
        self.state = "MENU"

    def load_sounds(self):
        files = {"jump": "jump.wav", "hit": "hit.wav", "score": "score.wav", "gameover": "gameover.wav"}
        base = os.path.join("sounds", "flappy")
        if not os.path.exists(base): os.makedirs(base, exist_ok=True)
        
        for name, fname in files.items():
            path = os.path.join(base, fname)
            if os.path.exists(path):
                try: self.sounds[name] = pygame.mixer.Sound(path)
                except: self.sounds[name] = None
            else: self.sounds[name] = None

    def play_sound(self, name):
        if self.sounds.get(name):
            try: self.sounds[name].play()
            except: pass

    def reset(self):
        self.player = Player(self.skin_mgr)
        self.pipes = [Pipe(WIDTH + i * 400) for i in range(3)]
        self.particles = []
        self.score = 0
        self.lives = 3 
        self.speed = PIPE_SPEED_START
        self.shake = 0
        self.count = 3
        self.last_tick = 0

    def background_fx(self, vol):
        self.scroll -= 2 + (vol * 2)
        if self.scroll <= -40: self.scroll = 0
        intensity = min(255, 30 + int(vol * 150))
        col_grid = (intensity//2, intensity//2, intensity)
        for x in range(int(self.scroll), WIDTH, 40):
            pygame.draw.line(self.screen, col_grid, (x, 0), (x, HEIGHT), 1)
        for y in range(0, HEIGHT, 40):
            pygame.draw.line(self.screen, col_grid, (0, y), (WIDTH, y), 1)

    def draw_ui(self):
        h = 200
        vol = min(1.0, self.audio.volume / 8.0)
        pygame.draw.rect(self.screen, (30,30,50), (20, HEIGHT-220, 15, h), border_radius=5)
        fh = int(h * vol)
        col = (0, 255, 0) if vol > self.threshold else (100, 100, 100)
        pygame.draw.rect(self.screen, col, (20, HEIGHT-20-fh, 15, fh), border_radius=5)
        ty = HEIGHT - 20 - int(h * self.threshold)
        pygame.draw.line(self.screen, (255, 255, 0), (15, ty), (40, ty), 2)
        txt = self.font_S.render(f"SENS: {int(self.threshold*100)}%", True, (150,150,150))
        self.screen.blit(txt, (45, ty-10))
        
        for i in range(self.lives):
            pygame.draw.circle(self.screen, C_LIFE, (40 + i*30, 40), 10)

    def update(self):
        vol = min(1.0, self.audio.volume / 8.0)
        
        if self.state == "COUNTDOWN":
            now = pygame.time.get_ticks()
            if now - self.last_tick > 1000:
                self.count -= 1; self.last_tick = now
                if self.count <= 0: self.state = "PLAYING"

        elif self.state == "PLAYING":
            is_loud = vol > self.threshold
            if is_loud:
                t_col = self.skin_mgr.get_current()["trail"]
                self.particles.append(Particle(self.player.x, self.player.y + 15, t_col))

            self.player.update(is_loud, vol)
            
            if self.player.y >= HEIGHT - self.player.size:
                self.player.vel = -5 
            
            for p in self.pipes:
                p.update(self.speed)
                
                if self.player.invulnerable == 0 and p.collide(self.player.rect):
                    self.lives -= 1
                    self.play_sound("hit")
                    self.player.invulnerable = 90
                    self.shake = 20
                    self.player.x -= 20 
                    if self.player.x < 0: self.player.x = 50
                    
                    if self.lives <= 0:
                        self.state = "GAMEOVER"
                        self.play_sound("gameover")

                if not p.passed and p.x < self.player.x:
                    self.score += 1; p.passed = True
                    self.play_sound("score")
            
            if self.pipes[-1].x < WIDTH - 400: self.pipes.append(Pipe(WIDTH))
            if self.pipes[0].x < -100: self.pipes.pop(0)
            
            for p in self.particles: p.update()
            self.particles = [p for p in self.particles if p.life > 0]
            
            self.speed = PIPE_SPEED_START + (self.score * 0.05)
            if self.score > self.high_score: self.high_score = self.score

    def draw(self):
        ox, oy = 0, 0
        if self.shake > 0:
            ox = random.randint(-5, 5); oy = random.randint(-5, 5)
            self.shake -= 1
            
        self.screen.fill(C_BG)
        self.background_fx(min(1.0, self.audio.volume / 8.0))
        
        for p in self.particles: p.draw(self.screen)
        for p in self.pipes: p.draw(self.screen, self.audio.volume)
        self.player.draw(self.screen)
        
        sc_txt = self.font_L.render(str(self.score), True, (255, 255, 255))
        sc_txt.set_alpha(40)
        self.screen.blit(sc_txt, (WIDTH//2 - sc_txt.get_width()//2, 100))
        
        if self.shake > 0:
            temp = self.screen.copy()
            self.screen.fill(C_BG); self.screen.blit(temp, (ox, oy))
            
        self.draw_ui()
        
        if self.state == "MENU":
            self.draw_overlay("NEON SCREAM", "GRITA PARA VOLAR", "[ESPACIO] JUGAR")
            skin_name = self.skin_mgr.get_current()["name"]
            st = self.font_M.render(f"< SKIN: {skin_name} >", True, self.skin_mgr.get_current()["color"])
            self.screen.blit(st, (WIDTH//2 - st.get_width()//2, HEIGHT//2 + 100))
            
        elif self.state == "COUNTDOWN":
            txt = "¡YA!" if self.count == 0 else str(self.count)
            ct = self.font_L.render(txt, True, C_ACCENT)
            self.screen.blit(ct, (WIDTH//2 - ct.get_width()//2, HEIGHT//2 - 50))
            
        elif self.state == "GAMEOVER":
            self.draw_overlay("GAME OVER", f"MEJOR: {self.high_score}", "[ESPACIO] REINTENTAR")

        pygame.display.flip()

    def draw_overlay(self, t1, t2, t3):
        bg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        bg.fill((0,0,0,180))
        self.screen.blit(bg, (0,0))
        tt1 = self.font_L.render(t1, True, C_ACCENT)
        tt2 = self.font_M.render(t2, True, (200,200,200))
        tt3 = self.font_S.render(t3, True, (255,255,255))
        cx, cy = WIDTH//2, HEIGHT//2
        self.screen.blit(tt1, (cx - tt1.get_width()//2, cy - 100))
        self.screen.blit(tt2, (cx - tt2.get_width()//2, cy + 20))
        self.screen.blit(tt3, (cx - tt3.get_width()//2, cy + 60))

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.close()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        if self.state == "MENU": self.return_main()
                        else: self.state = "MENU"
                    if self.state == "MENU":
                        if e.key == pygame.K_RIGHT: self.skin_mgr.next_skin()
                        if e.key == pygame.K_LEFT: self.skin_mgr.prev_skin()
                        if e.key == pygame.K_SPACE:
                            self.reset(); self.state = "COUNTDOWN"; self.last_tick = pygame.time.get_ticks()
                    if self.state == "GAMEOVER" and e.key == pygame.K_SPACE:
                        self.reset(); self.state = "COUNTDOWN"; self.last_tick = pygame.time.get_ticks()
                    if e.key == pygame.K_UP: self.threshold = min(1.0, self.threshold + 0.05)
                    if e.key == pygame.K_DOWN: self.threshold = max(0.05, self.threshold - 0.05)

            self.update()
            self.draw()
            self.clock.tick(FPS)

    def return_main(self):
        self.audio.close(); pygame.quit()
        try: subprocess.Popen([sys.executable, "main_menu.py"])
        except: pass
        sys.exit()

    def close(self):
        self.audio.close(); pygame.quit(); sys.exit()

if __name__ == "__main__":
    game = FlappyGame()
    game.run()