import sys
import os
import random
import math
import numpy as np
import subprocess

print("--- GEIIA HUMAN PIANO: ARCADE NEON ---")
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

C_BG = (5, 5, 15)
C_GRID = (20, 20, 40)
C_TEXT = (255, 255, 255)
C_ACCENT = (0, 255, 255)
C_WIN = (255, 215, 0)

COLORS = [
    (255, 0, 0),
    (255, 127, 0),
    (255, 255, 0),
    (0, 255, 0),
    (0, 255, 255),
    (0, 0, 255),
    (128, 0, 255),
    (255, 0, 255)
]
NOTES_FREQ = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
NOTE_NAMES = ["DO", "RE", "MI", "FA", "SOL", "LA", "SI", "DO"]

TARGET_SCORE = 30

try:
    pygame.mixer.pre_init(44100, -16, 1, 512, allowedchanges=0)
except TypeError:
    pygame.mixer.pre_init(44100, -16, 1, 512)

pygame.init()
pygame.font.init()

try:
    MIXER_FREQ, _, MIXER_CHANNELS = pygame.mixer.get_init()
except:
    MIXER_FREQ, MIXER_CHANNELS = 44100, 2

def create_sound(freq, duration=0.3):
    n_samples = int(MIXER_FREQ * duration)
    t = np.linspace(0, duration, n_samples, False)
    
    wave = np.sin(2 * np.pi * freq * t)
    wave += 0.5 * np.sin(2 * np.pi * freq * 2 * t)
    wave *= np.exp(-5 * t)
    
    max_val = np.max(np.abs(wave))
    if max_val == 0: max_val = 1
    audio_data = (wave * 32767 / max_val).astype(np.int16)
    
    if MIXER_CHANNELS == 2:
        stereo = np.column_stack((audio_data, audio_data))
        return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))
    else:
        return pygame.sndarray.make_sound(np.ascontiguousarray(audio_data))

print("🎵 Generando audio...")
PIANO_SOUNDS = [create_sound(f) for f in NOTES_FREQ]
SFX_WIN = create_sound(880, 1.0) 

class Star:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        self.size = random.randint(1, 3)
        self.speed = random.uniform(0.5, 2)
        self.color = (random.randint(200, 255), 255, random.randint(200, 255))

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.y = 0
            self.x = random.randint(0, WIDTH)

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.size)

class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y
        self.c = color
        self.s = random.randint(5, 12)
        self.vy = random.uniform(-8, -2)
        self.vx = random.uniform(-3, 3)
        self.life = 255

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 15
        self.s *= 0.9

    def draw(self, surf):
        if self.life > 0:
            s = pygame.Surface((int(self.s)*2, int(self.s)*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.c, self.life), (int(self.s), int(self.s)), int(self.s))
            surf.blit(s, (self.x-self.s, self.y-self.s))

class FallingNote:
    def __init__(self, lane_index, lane_width):
        self.lane = lane_index
        self.w = lane_width - 10
        self.h = 40
        self.x = lane_index * lane_width + 5
        self.y = -50 
        self.speed = 6 
        self.color = COLORS[lane_index]
        self.rect = pygame.Rect(self.x, self.y, self.w, self.h)

    def update(self):
        self.y += self.speed
        self.rect.y = int(self.y)
        if self.y > HEIGHT:
            return "MISS"
        return None

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect, border_radius=8)
        pygame.draw.rect(surf, (255,255,255), self.rect.inflate(-10, -10), 2, border_radius=5)

class KeyZone:
    def __init__(self, i, w):
        self.i = i
        self.rect = pygame.Rect(i*w + 5, HEIGHT - 150, w - 10, 100)
        self.c = COLORS[i % 8]
        self.name = NOTE_NAMES[i]
        self.active = False
        self.timer = 0

    def trigger(self):
        self.active = True
        self.timer = 5
        if PIANO_SOUNDS[self.i]: PIANO_SOUNDS[self.i].play()

    def update(self):
        if self.timer > 0: self.timer -= 1
        else: self.active = False

    def draw(self, surf):
        r = self.rect
        alpha = 150 if self.active else 40
        
        s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(s, (*self.c, alpha), (0,0,r.w,r.h), border_radius=10)
        surf.blit(s, r.topleft)
        
        pygame.draw.rect(surf, self.c, r, 3, border_radius=10)
        
        f = pygame.font.SysFont("Arial", 20, bold=True)
        t = f.render(self.name, True, (255,255,255))
        surf.blit(t, (r.centerx - t.get_width()//2, r.bottom + 10))

class HumanPiano:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("GEIIA HUMAN PIANO: NEON ARCADE")
        self.clock = pygame.time.Clock()
        
        print("📷 Conectando cámara...")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened(): self.cap = cv2.VideoCapture(0)
        
        self.use_cam = self.cap.isOpened()
        if self.use_cam: 
            self.cap.set(3, 640)
            self.cap.set(4, 480)
        else: 
            print("⚠️ Sin cámara. Usando Mouse.")

        self.hands = None
        if self.use_cam:
            try:
                self.hands = mp.solutions.hands.Hands(
                    max_num_hands=2,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.6
                )
            except:
                print("⚠️ Error IA. Usando Mouse.")
                self.use_cam = False

        self.music_loaded = False
        mp3_path = "musica.mp3"
        if os.path.exists(mp3_path):
            try:
                pygame.mixer.music.load(mp3_path)
                pygame.mixer.music.set_volume(0.4)
                self.music_loaded = True
                print("🎵 MP3 detectado y cargado.")
            except:
                print("⚠️ Error cargando MP3.")

        self.font_L = pygame.font.SysFont("Impact", 80)
        self.font_M = pygame.font.SysFont("Arial", 30, bold=True)
        self.stars = [Star() for _ in range(50)]
        
        self.reset_game()
        self.state = "MENU"

    def reset_game(self):
        self.lane_width = WIDTH // 8
        self.keys = [KeyZone(i, self.lane_width) for i in range(8)]
        self.notes = []
        self.particles = []
        self.score = 0
        self.lives = 5
        self.spawn_timer = 0
        self.count_val = 3
        self.last_count_tick = 0
        if self.music_loaded:
            pygame.mixer.music.stop()

    def get_input(self):
        fingers = []
        bg_surf = None
        
        if self.use_cam:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                if self.hands:
                    res = self.hands.process(rgb)
                    if res.multi_hand_landmarks:
                        for h in res.multi_hand_landmarks:
                            for id in [8, 12]:
                                lm = h.landmark[id]
                                fingers.append((int(lm.x * WIDTH), int(lm.y * HEIGHT)))
                
                disp = cv2.resize(np.rot90(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), (HEIGHT, WIDTH))
                bg_surf = pygame.transform.flip(pygame.surfarray.make_surface(disp), True, False)
                bg_surf = pygame.transform.scale(bg_surf, (WIDTH, HEIGHT))

        if not fingers:
            mx, my = pygame.mouse.get_pos()
            if pygame.mouse.get_pressed()[0]: fingers.append((mx, my))
            else: fingers.append((mx, my))

        return fingers, bg_surf

    def draw_menu(self):
        self.screen.fill(C_BG)
        for s in self.stars: s.update(); s.draw(self.screen)
        
        self.draw_overlay("NEON PIANO", "USA TUS MANOS PARA TOCAR", "[ESPACIO] PARA INICIAR")

    def draw_overlay(self, title, sub, action):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0,0))
        
        t_surf = self.font_L.render(title, True, C_ACCENT)
        s_surf = self.font_M.render(sub, True, (200, 200, 200))
        a_surf = self.font_M.render(action, True, (255, 255, 255))
        
        cx, cy = WIDTH//2, HEIGHT//2
        self.screen.blit(t_surf, (cx - t_surf.get_width()//2, cy - 100))
        self.screen.blit(s_surf, (cx - s_surf.get_width()//2, cy + 20))
        self.screen.blit(a_surf, (cx - a_surf.get_width()//2, cy + 80))

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.quit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE: 
                        if self.state == "MENU": self.quit()
                        else: self.state = "MENU"; pygame.mixer.music.stop()
                    
                    if self.state == "MENU" or self.state == "GAMEOVER" or self.state == "WIN":
                        if e.key == pygame.K_SPACE:
                            self.reset_game()
                            self.state = "COUNTDOWN"
                            self.last_count_tick = pygame.time.get_ticks()

            fingers, cam_surf = self.get_input()

            self.screen.fill(C_BG)
            if cam_surf:
                self.screen.blit(cam_surf, (0,0))
                dark = pygame.Surface((WIDTH, HEIGHT))
                dark.set_alpha(150)
                self.screen.blit(dark, (0,0))
            
            for s in self.stars: s.update(); s.draw(self.screen)

            if self.state == "MENU":
                self.draw_menu()
            
            elif self.state == "COUNTDOWN":
                now = pygame.time.get_ticks()
                if now - self.last_count_tick > 1000:
                    self.count_val -= 1
                    self.last_count_tick = now
                    if self.count_val <= 0: 
                        self.state = "PLAYING"
                        if self.music_loaded: pygame.mixer.music.play(-1)
                
                txt = str(self.count_val) if self.count_val > 0 else "GO!"
                ct = self.font_L.render(txt, True, C_ACCENT)
                self.screen.blit(ct, (WIDTH//2 - ct.get_width()//2, HEIGHT//2))

            elif self.state == "PLAYING":
                if self.spawn_timer <= 0:
                    lane = random.randint(0, 7)
                    self.notes.append(FallingNote(lane, self.lane_width))
                    self.spawn_timer = random.randint(20, 60)
                else:
                    self.spawn_timer -= 1

                for k in self.keys: k.update(); k.draw(self.screen)

                for note in self.notes[:]:
                    res = note.update()
                    if res == "MISS":
                        self.notes.remove(note)
                        self.lives -= 1
                    
                    note.draw(self.screen)
                    
                    key_rect = self.keys[note.lane].rect
                    if note.rect.colliderect(key_rect):
                        for fx, fy in fingers:
                            if key_rect.collidepoint(fx, fy):
                                self.keys[note.lane].trigger()
                                self.score += 1
                                for _ in range(5): 
                                    self.particles.append(Particle(note.rect.centerx, note.rect.centery, note.color))
                                if note in self.notes: self.notes.remove(note)
                                break

                for p in self.particles: p.update(); p.draw(self.screen)
                self.particles = [p for p in self.particles if p.life > 0]

                pygame.draw.rect(self.screen, (0,0,0), (0,0,WIDTH, 50))
                sc = self.font_M.render(f"SCORE: {self.score}/{TARGET_SCORE}", True, (0,255,0))
                lv = self.font_M.render(f"VIDAS: {self.lives}", True, (255,50,50))
                self.screen.blit(sc, (20, 10))
                self.screen.blit(lv, (WIDTH - 150, 10))

                for fx, fy in fingers:
                    pygame.draw.circle(self.screen, (255,255,255), (fx, fy), 10)
                    pygame.draw.circle(self.screen, C_ACCENT, (fx, fy), 16, 2)

                if self.lives <= 0: 
                    self.state = "GAMEOVER"
                    pygame.mixer.music.stop()
                if self.score >= TARGET_SCORE: 
                    self.state = "WIN"
                    pygame.mixer.music.stop()
                    if SFX_WIN: SFX_WIN.play()

            elif self.state == "GAMEOVER":
                self.draw_overlay("GAME OVER", f"PUNTOS: {self.score}", "[ESPACIO] REINTENTAR")

            elif self.state == "WIN":
                self.screen.fill((0,0,0))
                for _ in range(5):
                    cx, cy = random.randint(0,WIDTH), random.randint(0,HEIGHT)
                    pygame.draw.circle(self.screen, random.choice(COLORS), (cx,cy), random.randint(2,5))
                
                t1 = self.font_L.render("¡FELICIDADES!", True, (0, 255, 0))
                t2 = self.font_M.render("HAS COMPLETADO EL RETO", True, (255, 255, 255))
                
                box = pygame.Rect(WIDTH//2 - 250, HEIGHT//2 - 80, 500, 160)
                pygame.draw.rect(self.screen, (20, 20, 50), box, border_radius=20)
                pygame.draw.rect(self.screen, C_ACCENT, box, 4, border_radius=20)
                
                p = self.font_L.render("🎫 PREMIO 🎫", True, C_WIN)
                
                self.screen.blit(t1, (WIDTH//2 - t1.get_width()//2, 100))
                self.screen.blit(t2, (WIDTH//2 - t2.get_width()//2, 180))
                self.screen.blit(p, (WIDTH//2 - p.get_width()//2, HEIGHT//2 - 30))
                
                hint = self.font_M.render("[ESC] SALIR", True, (150,150,150))
                self.screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT - 100))

            pygame.display.flip()
            self.clock.tick(FPS)

    def quit(self):
        if self.use_cam: self.cap.release()
        pygame.quit()
        try: subprocess.Popen([sys.executable, "main_menu.py"])
        except: pass
        sys.exit()

if __name__ == "__main__":
    HumanPiano().run()