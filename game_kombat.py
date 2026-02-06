import sys
import os
import random
import math
import numpy as np
import subprocess

print("--- GEIIA NEON RACER: OVERDRIVE ---")

try:
    import pygame
    import cv2
    import mediapipe as mp
    print("✅ Librerías cargadas.")
except ImportError as e:
    print(f"❌ Error crítico: {e}")
    sys.exit()

WIDTH, HEIGHT = 900, 760
FPS = 30

C_BG = (5, 0, 10)
C_GRID = (200, 0, 255)
C_PLAYER = (0, 255, 255)
C_ENEMY = (255, 50, 50)
C_LASER = (255, 255, 0)
C_WALL = (255, 100, 0)
C_POWER = (50, 255, 50)
C_SHIELD = (100, 150, 255)
C_WIN = (255, 215, 0)

TARGET_SCORE = 600

try:
    pygame.mixer.pre_init(44100, -16, 1, 512, allowedchanges=0)
except:
    pygame.mixer.pre_init(44100, -16, 1, 512)

pygame.init()
pygame.font.init()

try:
    MIXER_FREQ, _, MIXER_CHANNELS = pygame.mixer.get_init()
except:
    MIXER_FREQ, MIXER_CHANNELS = 44100, 2

def create_sound(freq, duration=0.1, type="sine"):
    n_samples = int(MIXER_FREQ * duration)
    t = np.linspace(0, duration, n_samples, False)
    
    if type == "sine":
        wave = np.sin(2 * np.pi * freq * t) * np.exp(-3 * t)
    elif type == "noise":
        wave = np.random.uniform(-0.5, 0.5, n_samples) * np.exp(-5 * t)
    elif type == "saw":
        wave = (2 * (t * freq - np.floor(t * freq + 0.5))) * np.exp(-3 * t)
    
    max_val = np.max(np.abs(wave)) or 1
    audio_data = (wave * 32767 / max_val).astype(np.int16)
    
    if MIXER_CHANNELS == 2:
        snd = pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack((audio_data, audio_data))))
    else:
        snd = pygame.sndarray.make_sound(np.ascontiguousarray(audio_data))
    return snd

SND_LASER = create_sound(880, 0.15, "saw")
if SND_LASER: SND_LASER.set_volume(0.2) 

SND_EXPLODE = create_sound(100, 0.3, "noise")
SND_POWERUP = create_sound(1200, 0.2, "sine")
SND_DAMAGE = create_sound(50, 0.4, "noise")
SND_WIN = create_sound(600, 1.0, "sine")

class PerspectiveGrid:
    def __init__(self):
        self.offset_y = 0
        self.speed = 10
        
    def update(self, speed_mult):
        self.offset_y = (self.offset_y + self.speed * speed_mult) % 40
        
    def draw(self, surf):
        pygame.draw.line(surf, C_GRID, (0, HEIGHT//2), (WIDTH, HEIGHT//2), 2)
        center_x = WIDTH // 2
        for i in range(-10, 11):
            x_start = center_x + i * 40
            pygame.draw.line(surf, (50, 0, 80), (center_x + i * 10, HEIGHT//2), (x_start * 3, HEIGHT), 2)
            
        for i in range(20):
            y = HEIGHT//2 + (i * 20) + self.offset_y
            if y < HEIGHT:
                pygame.draw.line(surf, (100, 0, 150), (0, y), (WIDTH, y), 1 + i//5)

class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.c = color
        self.vx = random.uniform(-5, 5)
        self.vy = random.uniform(-5, 5)
        self.life = 255
        self.size = random.randint(3, 8)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 15
        self.size *= 0.9

    def draw(self, surf):
        if self.life > 0:
            s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.c, self.life), (self.size, self.size), self.size)
            surf.blit(s, (self.x, self.y))

class Laser:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x - 4, y, 8, 20)
        self.speed = -20
        self.active = True

    def update(self):
        self.rect.y += self.speed
        if self.rect.y < -50: self.active = False

    def draw(self, surf):
        glow_surf = pygame.Surface((20, 30), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, (*C_LASER, 100), (0, 0, 20, 30), border_radius=10)
        surf.blit(glow_surf, (self.rect.centerx - 10, self.rect.y - 5))
        pygame.draw.rect(surf, C_LASER, self.rect, border_radius=4)

class Entity:
    def __init__(self, type_id, speed_mult):
        self.w = 60
        self.h = 60
        self.x = random.randint(50, WIDTH - 50 - self.w)
        self.y = -100
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)
        self.speed = 8 * speed_mult
        self.type = type_id 
        self.active = True
        self.rotation = 0
        
        if self.type == 0: self.color = C_WALL
        elif self.type == 1: self.color = C_ENEMY
        elif self.type == 2: self.color = C_POWER

    def update(self):
        self.y += self.speed
        self.rect.y = int(self.y)
        self.rotation = (self.rotation + 5) % 360
        if self.y > HEIGHT: self.active = False

    def draw(self, surf):
        cx, cy = self.rect.center
        
        if self.type == 0:
            pygame.draw.rect(surf, self.color, self.rect, border_radius=8)
            pygame.draw.rect(surf, (50,0,0), self.rect.inflate(-10,-10))
            
        elif self.type == 1:
            pts = [
                (cx, cy - 20),
                (cx - 20, cy + 10),
                (cx, cy + 30),
                (cx + 20, cy + 10)
            ]
            pygame.draw.polygon(surf, self.color, pts)
            pygame.draw.circle(surf, (0,0,0), (cx, cy), 5)
            
        elif self.type == 2:
            scale = math.sin(math.radians(self.rotation))
            w_scaled = max(5, abs(int(self.w * scale)))
            r = pygame.Rect(cx - w_scaled//2, self.rect.y, w_scaled, self.h)
            pygame.draw.rect(surf, self.color, r, border_radius=5)
            pygame.draw.rect(surf, (255,255,255), r, 2, border_radius=5)

class Player:
    def __init__(self):
        self.rect = pygame.Rect(WIDTH//2, HEIGHT-120, 60, 80)
        self.x = float(self.rect.x)
        self.tilt = 0
        self.shield_timer = 0
        self.rapid_fire = 0

    def update(self, target_x):
        diff = (target_x - self.rect.width//2) - self.x
        self.x += diff * 0.15
        self.rect.x = int(self.x)
        self.rect.clamp_ip(pygame.Rect(0,0,WIDTH,HEIGHT))
        self.tilt = -diff * 0.5
        
        if self.shield_timer > 0: self.shield_timer -= 1
        if self.rapid_fire > 0: self.rapid_fire -= 1

    def draw(self, surf):
        if self.shield_timer > 0:
            pygame.draw.circle(surf, (*C_SHIELD, 50), self.rect.center, 60)
            pygame.draw.circle(surf, C_SHIELD, self.rect.center, 60, 2)

        cx, cy = self.rect.centerx, self.rect.centery
        pts = [
            (cx, cy - 40),
            (cx - 30, cy + 30),
            (cx, cy + 10),
            (cx + 30, cy + 30)
        ]
        col = C_SHIELD if self.shield_timer > 0 else C_PLAYER
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, (255,255,255), pts, 2)
        
        if random.random() > 0.3:
            flame = [(cx-10, cy+30), (cx+10, cy+30), (cx, cy+60 + random.randint(0,20))]
            pygame.draw.polygon(surf, (255,100,0), flame)

class NeonRacer:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("GEIIA NEON RACER: OVERDRIVE")
        self.clock = pygame.time.Clock()
        
        print("📷 Iniciando cámara...")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened(): self.cap = cv2.VideoCapture(0)
        
        self.use_cam = self.cap.isOpened()
        if self.use_cam: 
            self.cap.set(3, 640); self.cap.set(4, 480)
        
        self.mesh = None
        if self.use_cam:
            try:
                self.mesh = mp.solutions.face_mesh.FaceMesh(
                    max_num_faces=1, 
                    refine_landmarks=True, 
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.6
                )
            except:
                print("⚠️ Error IA. Usando Mouse.")
                self.use_cam = False

        self.font_L = pygame.font.SysFont("Impact", 80)
        self.font_M = pygame.font.SysFont("Arial", 30, bold=True)
        
        self.grid = PerspectiveGrid()
        self.reset_game()
        self.state = "MENU"

    def reset_game(self):
        self.player = Player()
        self.entities = [] 
        self.lasers = []
        self.particles = []
        self.score = 0
        self.lives = 3
        self.shake = 0
        self.speed_mult = 1.0
        self.spawn_timer = 0
        self.count = 3
        self.last_tick = 0
        self.blink_cooldown = 0

    def get_control_data(self):
        target_x = WIDTH // 2
        shooting = False
        cam_surf = None

        if self.use_cam:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = self.mesh.process(rgb)
                
                if res.multi_face_landmarks:
                    lms = res.multi_face_landmarks[0].landmark
                    nose_x = lms[1].x
                    target_x = int(nose_x * WIDTH)
                    
                    eye_top = lms[159].y
                    eye_bot = lms[145].y
                    eye_dist = abs(eye_top - eye_bot)
                    
                    if eye_dist < 0.012: 
                        shooting = True
                        cv2.putText(frame, "FIRE!", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

                    nx, ny = int(nose_x * 160), int(lms[1].y * 120)
                    cv2.circle(frame, (nx, ny), 5, (255, 255, 0), -1)

                disp = cv2.resize(frame, (160, 120))
                disp = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
                disp = np.rot90(disp)
                cam_surf = pygame.surfarray.make_surface(disp)
                cam_surf = pygame.transform.flip(cam_surf, True, False)

        if not self.use_cam:
            target_x = pygame.mouse.get_pos()[0]
            if pygame.mouse.get_pressed()[0]: shooting = True

        return target_x, shooting, cam_surf

    def spawn_entities(self):
        if self.spawn_timer <= 0:
            r = random.random()
            if r < 0.1: self.entities.append(Entity(2, self.speed_mult))
            elif r < 0.4: self.entities.append(Entity(1, self.speed_mult))
            else: self.entities.append(Entity(0, self.speed_mult))
            self.spawn_timer = random.randint(30, 60)
        else:
            self.spawn_timer -= 1 * self.speed_mult

    def draw_shake(self):
        ox, oy = 0, 0
        if self.shake > 0:
            ox = random.randint(-5, 5)
            oy = random.randint(-5, 5)
            self.shake -= 1
        return ox, oy

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.quit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: self.quit()
                    if self.state != "PLAYING" and e.key == pygame.K_SPACE:
                        self.reset_game()
                        self.state = "COUNTDOWN"
                        self.last_count_tick = pygame.time.get_ticks()

            target_x, trying_shoot, cam_view = self.get_control_data()
            ox, oy = self.draw_shake()

            self.screen.fill(C_BG)
            surf_content = pygame.Surface((WIDTH, HEIGHT))
            surf_content.fill(C_BG)
            
            self.grid.update(self.speed_mult if self.state=="PLAYING" else 0.5)
            self.grid.draw(surf_content)

            if self.state == "MENU":
                t = self.font_L.render("NEON RACER", True, C_PLAYER)
                surf_content.blit(t, (WIDTH//2 - t.get_width()//2, 150))
                i = self.font_M.render("MUEVE CABEZA + PARPADEA", True, (200,200,200))
                surf_content.blit(i, (WIDTH//2 - i.get_width()//2, 300))
                s = self.font_M.render("[ESPACIO] START", True, C_LASER)
                surf_content.blit(s, (WIDTH//2 - s.get_width()//2, 400))

            elif self.state == "COUNTDOWN":
                now = pygame.time.get_ticks()
                if now - self.last_count_tick > 1000:
                    self.count -= 1; self.last_count_tick = now
                    if self.count <= 0: self.state = "PLAYING"
                txt = str(self.count) if self.count > 0 else "GO!"
                ct = self.font_L.render(txt, True, C_PLAYER)
                surf_content.blit(ct, (WIDTH//2 - ct.get_width()//2, HEIGHT//2))

            elif self.state == "PLAYING":
                if self.blink_cooldown > 0: self.blink_cooldown -= 1
                
                fire_rate = 5 if self.player.rapid_fire > 0 else 15
                if trying_shoot and self.blink_cooldown == 0:
                    self.lasers.append(Laser(self.player.rect.centerx, self.player.rect.top))
                    if SND_LASER: SND_LASER.play()
                    self.blink_cooldown = fire_rate

                self.spawn_entities()
                self.speed_mult = 1.0 + (self.score * 0.02)

                self.player.update(target_x)
                self.player.draw(surf_content)

                for l in self.lasers[:]:
                    l.update()
                    l.draw(surf_content)
                    if not l.active: self.lasers.remove(l)

                for e in self.entities[:]:
                    e.update()
                    e.draw(surf_content)
                    
                    if e.type == 1: 
                        for l in self.lasers:
                            if l.active and e.rect.colliderect(l.rect):
                                e.active = False; l.active = False
                                self.score += 50
                                self.shake = 5
                                if SND_EXPLODE: SND_EXPLODE.play()
                                for _ in range(10): 
                                    self.particles.append(Particle(e.rect.centerx, e.rect.centery, C_ENEMY))
                    
                    if e.rect.colliderect(self.player.rect):
                        e.active = False
                        if e.type == 0: 
                            if self.player.shield_timer > 0: self.score += 10
                            else:
                                self.lives -= 1
                                self.shake = 15
                                self.speed_mult = 1.0
                                if SND_DAMAGE: SND_DAMAGE.play()
                        elif e.type == 1:
                            if self.player.shield_timer > 0: self.score += 50
                            else:
                                self.lives -= 1
                                self.shake = 10
                                if SND_DAMAGE: SND_DAMAGE.play()
                        elif e.type == 2:
                            self.score += 100
                            effect = random.choice(["SHIELD", "FIRE"])
                            if effect == "SHIELD": self.player.shield_timer = 300
                            else: self.player.rapid_fire = 300
                            if SND_POWERUP: SND_POWERUP.play()

                    if not e.active: self.entities.remove(e)

                for p in self.particles: p.update(); p.draw(surf_content)
                self.particles = [p for p in self.particles if p.life > 0]

                sc = self.font_M.render(f"SCORE: {self.score}/{TARGET_SCORE}", True, C_PLAYER)
                lv = self.font_M.render(f"LIVES: {'❤'*self.lives}", True, C_WALL)
                surf_content.blit(sc, (20, 10))
                surf_content.blit(lv, (WIDTH - 200, 10))
                
                if self.player.shield_timer > 0:
                    sh = self.font_M.render("ESCUDO ACTIVO", True, C_SHIELD)
                    surf_content.blit(sh, (WIDTH//2 - sh.get_width()//2, 80))

                if self.lives <= 0: self.state = "GAMEOVER"
                if self.score >= TARGET_SCORE: 
                    self.state = "WIN"
                    if SND_WIN: SND_WIN.play()

            elif self.state == "GAMEOVER":
                t = self.font_L.render("GAME OVER", True, C_WALL)
                s = self.font_M.render(f"SCORE: {self.score}", True, (255,255,255))
                r = self.font_M.render("[ESPACIO] REINTENTAR", True, (150,150,150))
                surf_content.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//2 - 80))
                surf_content.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2))
                surf_content.blit(r, (WIDTH//2 - r.get_width()//2, HEIGHT//2 + 60))

            elif self.state == "WIN":
                surf_content.fill((0,0,0))
                t = self.font_L.render("VICTORIA SUPREMA", True, C_WIN)
                s = self.font_M.render("RECLAMA TU PREMIO", True, C_PLAYER)
                
                box = pygame.Rect(WIDTH//2 - 250, HEIGHT//2 - 60, 500, 120)
                pygame.draw.rect(surf_content, (20, 20, 50), box, border_radius=20)
                pygame.draw.rect(surf_content, C_WIN, box, 4, border_radius=20)
                
                surf_content.blit(t, (WIDTH//2 - t.get_width()//2, 100))
                surf_content.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 - 20))
                
                r = self.font_M.render("[ESPACIO] REINTENTAR", True, (150,150,150))
                surf_content.blit(r, (WIDTH//2 - r.get_width()//2, HEIGHT - 100))

            self.screen.blit(surf_content, (ox, oy))

            if cam_view:
                pygame.draw.rect(self.screen, (255,255,255), (10, HEIGHT-130, 164, 124), 2)
                self.screen.blit(cam_view, (12, HEIGHT-128))

            pygame.display.flip()
            self.clock.tick(FPS)

    def quit(self):
        if self.use_cam: self.cap.release()
        pygame.quit()
        try: subprocess.Popen([sys.executable, "main_menu.py"])
        except: pass
        sys.exit()

if __name__ == "__main__":
    NeonRacer().run()