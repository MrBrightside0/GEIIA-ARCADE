"""
GEIIA ARCADE - AIR PONG
Pong 1v1 donde tu mano ES la paleta (hand tracking con MediaPipe).

Ideas de diseno para la feria:
  - Cada lado se asigna por POSICION de la mano en el cuadro, no por mano
    izquierda/derecha. Asi dos personas distintas se paran lado a lado y
    cada quien controla su paleta con la mano que quiera.
  - Si un lado no tiene mano, lo toma la CPU automaticamente. Una persona
    puede jugar sola y cuando llega un amigo solo levanta la mano y entra.
    Cero configuracion, cero explicaciones.
"""

import math
import random

import pygame

import geiia_core as core
from geiia_core import (
    C_ACCENT,
    C_BAD,
    C_BG,
    C_DIM,
    C_GOLD,
    C_P1,
    C_P2,
    C_TEXT,
    HEIGHT,
    WIDTH,
)

FIELD_TOP = 96   # debajo de la barra GEIIA + el marcador
FIELD_BOT = HEIGHT - 42  # arriba del pie compartido

PADDLE_W = 18
PADDLE_H = 140
PADDLE_MARGIN = 46

BALL_R = 13
BALL_SPEED_START = 8.5
BALL_SPEED_MAX = 20.0
BALL_SPEEDUP = 0.55

POINTS_TO_WIN = 5
HAND_TIMEOUT = 45  # frames sin mano antes de que la CPU tome el control

# La mano casi nunca llega a los bordes del cuadro, asi que estiramos el
# rango util: 0.18..0.82 del alto de la camara cubre toda la cancha.
HAND_LO, HAND_HI = 0.18, 0.82


class Paddle:
    def __init__(self, side, color):
        self.side = side  # "L" o "R"
        self.color = color
        self.h = PADDLE_H
        self.y = (FIELD_TOP + FIELD_BOT) / 2
        self.x = PADDLE_MARGIN if side == "L" else WIDTH - PADDLE_MARGIN - PADDLE_W
        self.score = 0
        self.is_cpu = True
        self.no_hand_frames = HAND_TIMEOUT
        self.grow_timer = 0
        self.hit_flash = 0

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y - self.h / 2), PADDLE_W, int(self.h))

    def update_from_hand(self, hand_y):
        """hand_y normalizado 0..1, o None si no hay mano en este lado."""
        if hand_y is None:
            self.no_hand_frames += 1
            if self.no_hand_frames >= HAND_TIMEOUT:
                self.is_cpu = True
            return
        self.no_hand_frames = 0
        self.is_cpu = False
        t = (hand_y - HAND_LO) / (HAND_HI - HAND_LO)
        t = max(0.0, min(1.0, t))
        target = FIELD_TOP + t * (FIELD_BOT - FIELD_TOP)
        self.y = core.smooth(self.y, target, 0.35)
        self._clamp()

    def update_cpu(self, balls, difficulty=0.09):
        """CPU deliberadamente imperfecta: sigue la bola mas cercana con
        retraso y un margen de error, para que sea ganable y divertida."""
        mine = [b for b in balls if (b.vx < 0) == (self.side == "L")]
        target_ball = min(mine, key=lambda b: abs(b.x - self.x), default=None)
        if target_ball is None:
            target = (FIELD_TOP + FIELD_BOT) / 2
        else:
            target = target_ball.y + target_ball.wobble
        self.y = core.smooth(self.y, target, difficulty)
        self._clamp()

    def _clamp(self):
        half = self.h / 2
        self.y = max(FIELD_TOP + half, min(FIELD_BOT - half, self.y))

    def tick(self):
        if self.grow_timer > 0:
            self.grow_timer -= 1
            if self.grow_timer == 0:
                self.h = PADDLE_H
        if self.hit_flash > 0:
            self.hit_flash -= 1
        self._clamp()

    def grow(self):
        self.h = PADDLE_H * 1.7
        self.grow_timer = 420

    def draw(self, surf):
        col = (255, 255, 255) if self.hit_flash > 0 else self.color
        core.draw_glow_rect(surf, col, self.rect, glow=14, radius=9, alpha=80)


class Ball:
    def __init__(self, direction=None):
        self.x = WIDTH / 2
        self.y = (FIELD_TOP + FIELD_BOT) / 2
        self.speed = BALL_SPEED_START
        ang = random.uniform(-0.45, 0.45)
        d = direction if direction is not None else random.choice((-1, 1))
        self.vx = math.cos(ang) * self.speed * d
        self.vy = math.sin(ang) * self.speed
        self.trail = []
        self.wobble = random.uniform(-45, 45)  # error que la CPU comete
        self.last_hit = None

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.trail.append((self.x, self.y))
        if len(self.trail) > 12:
            self.trail.pop(0)

        if self.y - BALL_R <= FIELD_TOP:
            self.y = FIELD_TOP + BALL_R
            self.vy = abs(self.vy)
            return "wall"
        if self.y + BALL_R >= FIELD_BOT:
            self.y = FIELD_BOT - BALL_R
            self.vy = -abs(self.vy)
            return "wall"
        return None

    def bounce_off(self, paddle):
        """El angulo de salida depende de DONDE pegaste: centro = recto,
        orillas = muy abierto. Es lo que hace que el Pong se sienta con skill."""
        offset = (self.y - paddle.y) / (paddle.h / 2)
        offset = max(-1.0, min(1.0, offset))
        angle = offset * (math.pi / 3.2)

        self.speed = min(BALL_SPEED_MAX, self.speed + BALL_SPEEDUP)
        direction = 1 if paddle.side == "L" else -1
        self.vx = math.cos(angle) * self.speed * direction
        self.vy = math.sin(angle) * self.speed

        # sacar la bola de la paleta para que no rebote dos veces
        if paddle.side == "L":
            self.x = paddle.x + PADDLE_W + BALL_R + 1
        else:
            self.x = paddle.x - BALL_R - 1

        self.wobble = random.uniform(-45, 45)
        self.last_hit = paddle.side

    @property
    def rect(self):
        return pygame.Rect(int(self.x - BALL_R), int(self.y - BALL_R), BALL_R * 2, BALL_R * 2)

    def draw(self, surf):
        # Estela de bloques cada vez mas chicos, sin transparencia.
        for i, (tx, ty) in enumerate(self.trail):
            if i % 2:
                continue
            lado = core.snap(BALL_R * (0.3 + 0.7 * i / len(self.trail)))
            if lado >= core.PIXEL:
                pygame.draw.rect(surf, core.C_GRID, (core.snap(tx), core.snap(ty), lado, lado))
        lado = core.snap(BALL_R * 1.6)
        core.block(surf, C_TEXT, (self.x - lado // 2, self.y - lado // 2, lado, lado))


class PowerUp:
    KINDS = [
        ("GRANDE", (80, 255, 140), "Tu paleta crece"),
        ("DOBLE", (255, 200, 0), "Aparece otra bola"),
        ("TURBO", (255, 90, 160), "La bola acelera"),
    ]

    def __init__(self):
        self.kind, self.color, self.desc = random.choice(self.KINDS)
        self.x = random.uniform(WIDTH * 0.32, WIDTH * 0.68)
        self.y = random.uniform(FIELD_TOP + 70, FIELD_BOT - 70)
        self.life = 600
        self.phase = random.uniform(0, 6.28)

    @property
    def rect(self):
        return pygame.Rect(int(self.x - 22), int(self.y - 22), 44, 44)

    def update(self):
        self.life -= 1
        self.phase += 0.09

    def draw(self, surf, font):
        # Bloque que late en escalones, no con una senoide suave.
        lado = core.snap(40 + (core.PIXEL * 2 if int(self.phase * 2) % 2 else 0))
        x, y = core.snap(self.x - lado // 2), core.snap(self.y - lado // 2)
        core.block(surf, self.color, (x, y, lado, lado), borde=core.C_BG)
        core.text_at(surf, font, self.kind[0], core.C_BG, x + lado // 2, y + lado // 2)


class AirPong:
    def __init__(self):
        self.screen, self.clock, self.fonts = core.boot("GEIIA AIR PONG")
        self.synth = core.Synth()

        self.snd_hit = self.synth.tone(520, 0.09, 14, "square", 0.30)
        self.snd_wall = self.synth.tone(240, 0.07, 18, "square", 0.20)
        self.snd_point = self.synth.sweep(700, 180, 0.32, 0.35)
        self.snd_power = self.synth.sweep(400, 1100, 0.28, 0.35)
        self.snd_win = self.synth.chord([523, 659, 784, 1047], 1.0, 0.45)
        self.snd_beep = self.synth.tone(880, 0.10, 12, "sine", 0.30)

        self.camera = core.VisionWorker("hands", max_items=2)
        self.camera.start()

        self.fx = core.FxLayer()
        self.state = "MENU"
        self.grid_offset = 0.0
        self.shake = 0
        self.reset_match()

    # ---------- estado ----------
    def reset_match(self):
        self.left = Paddle("L", C_P1)
        self.right = Paddle("R", C_P2)
        self.balls = []
        self.powerup = None
        self.powerup_cooldown = 320
        self.winner = None
        self.count = 3
        self.count_tick = 0
        self.rally = 0
        self.best_rally = 0

    def serve(self, direction=None):
        self.balls = [Ball(direction)]
        self.rally = 0

    # ---------- entrada ----------
    def read_hands(self):
        """Devuelve (y_izq, y_der) normalizados, o None si ese lado no tiene mano."""
        hands = self.camera.latest()
        left_y = right_y = None
        best_left = best_right = None

        for h in hands:
            hx, hy = h.palm
            if hx < 0.5:
                # la mano mas a la izquierda manda en ese lado
                if best_left is None or hx < best_left:
                    best_left, left_y = hx, hy
            else:
                if best_right is None or hx > best_right:
                    best_right, right_y = hx, hy

        # Sin camara: el mouse controla la paleta izquierda para poder probar.
        if not self.camera.available and self.camera.error is not None:
            my = pygame.mouse.get_pos()[1]
            left_y = HAND_LO + (my / HEIGHT) * (HAND_HI - HAND_LO)

        return left_y, right_y

    def on_key(self, e):
        if e.key == pygame.K_ESCAPE:
            if self.state == "MENU":
                core.exit_game(self.camera)
            self.state = "MENU"
        elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.state in ("MENU", "GAMEOVER"):
                self.reset_match()
                self.state = "COUNTDOWN"
                self.count = 3
                self.count_tick = pygame.time.get_ticks()
                self.synth.play(self.snd_beep)

    # ---------- logica ----------
    def update_play(self):
        left_y, right_y = self.read_hands()
        self.left.update_from_hand(left_y)
        self.right.update_from_hand(right_y)
        if self.left.is_cpu:
            self.left.update_cpu(self.balls)
        if self.right.is_cpu:
            self.right.update_cpu(self.balls)
        self.left.tick()
        self.right.tick()

        # power-ups
        if self.powerup is None:
            self.powerup_cooldown -= 1
            if self.powerup_cooldown <= 0:
                self.powerup = PowerUp()
        else:
            self.powerup.update()
            if self.powerup.life <= 0:
                self.powerup = None
                self.powerup_cooldown = random.randint(300, 620)

        scored = None
        for ball in list(self.balls):
            if ball.update() == "wall":
                self.synth.play(self.snd_wall)

            paddle = self.left if ball.vx < 0 else self.right
            if ball.rect.colliderect(paddle.rect):
                ball.bounce_off(paddle)
                paddle.hit_flash = 6
                self.rally += 1
                self.best_rally = max(self.best_rally, self.rally)
                self.synth.play(self.snd_hit)
                self.fx.burst(ball.x, ball.y, paddle.color, 10, 5)
                if self.rally > 0 and self.rally % 5 == 0:
                    self.fx.say(f"¡{self.rally} SEGUIDOS!", WIDTH // 2, FIELD_TOP + 60, C_GOLD, self.fonts["md"])

            if self.powerup and ball.rect.colliderect(self.powerup.rect):
                self.apply_powerup(ball)

            if ball.x < -40:
                scored = "R"
                self.balls.remove(ball)
            elif ball.x > WIDTH + 40:
                scored = "L"
                self.balls.remove(ball)

        if not self.balls and scored:
            self.award_point(scored)
        elif not self.balls:
            self.serve()

    def apply_powerup(self, ball):
        owner = ball.last_hit
        kind = self.powerup.kind
        color = self.powerup.color
        self.synth.play(self.snd_power)
        self.fx.burst(self.powerup.x, self.powerup.y, color, 26, 8)

        if kind == "GRANDE" and owner:
            (self.left if owner == "L" else self.right).grow()
            self.fx.say("¡PALETA GRANDE!", WIDTH // 2, FIELD_TOP + 100, color, self.fonts["md"])
        elif kind == "DOBLE":
            extra = Ball()
            extra.x, extra.y = ball.x, ball.y
            extra.speed = ball.speed
            extra.vx, extra.vy = -ball.vy, ball.vx  # sale perpendicular
            extra.last_hit = owner
            self.balls.append(extra)
            self.fx.say("¡DOBLE BOLA!", WIDTH // 2, FIELD_TOP + 100, color, self.fonts["md"])
        else:  # TURBO
            for b in self.balls:
                b.speed = min(BALL_SPEED_MAX, b.speed + 3.0)
                mag = math.hypot(b.vx, b.vy) or 1
                b.vx, b.vy = b.vx / mag * b.speed, b.vy / mag * b.speed
            self.fx.say("¡TURBO!", WIDTH // 2, FIELD_TOP + 100, color, self.fonts["md"])

        self.powerup = None
        self.powerup_cooldown = random.randint(300, 620)

    def award_point(self, side):
        winner = self.left if side == "L" else self.right
        winner.score += 1
        self.shake = 14
        self.synth.play(self.snd_point)
        self.fx.burst(WIDTH // 2, HEIGHT // 2, winner.color, 34, 10)

        if winner.score >= POINTS_TO_WIN:
            self.winner = winner
            self.state = "GAMEOVER"
            self.synth.play(self.snd_win)
        else:
            self.state = "COUNTDOWN"
            self.count = 2
            self.count_tick = pygame.time.get_ticks()
            self.serve_dir = -1 if side == "L" else 1

    # ---------- dibujo ----------
    def draw_field(self, surf):
        surf.fill(C_BG)
        core.draw_grid(surf, step=48)

        # Bordes de la cancha como franjas solidas
        core.block(surf, core.C_GRID, (0, FIELD_TOP - core.PIXEL, WIDTH, core.PIXEL))
        core.block(surf, core.C_GRID, (0, FIELD_BOT, WIDTH, core.PIXEL))

        # Red central: bloques con hueco, como en las maquinas originales
        for y in range(FIELD_TOP + 12, FIELD_BOT, 30):
            core.block(surf, core.C_GRID, (WIDTH // 2 - core.PIXEL, y, core.PIXEL * 2, 15))

    def draw_hud(self, surf):
        top = core.snap(46)
        franja = pygame.Rect(0, top, WIDTH, FIELD_TOP - top - core.PIXEL)
        core.block(surf, core.C_BG, franja)

        cy = franja.centery
        for paddle, x, anchor in ((self.left, 34, "midleft"), (self.right, WIDTH - 34, "midright")):
            etiqueta = "CPU" if paddle.is_cpu else "JUGADOR"
            signo = -1 if anchor == "midleft" else 1
            core.text_at(surf, self.fonts["lg"], str(paddle.score), paddle.color, x, cy, anchor)
            ancho = self.fonts["lg"].size(str(paddle.score))[0]
            core.text_at(surf, self.fonts["xs"], etiqueta, C_DIM,
                         x + signo * (ancho + 14), cy, anchor)

        if self.rally > 1:
            core.text_at(surf, self.fonts["sm"], f"RACHA {self.rally}", C_GOLD, WIDTH // 2, cy)
        else:
            core.text_at(surf, self.fonts["xs"], f"PRIMERO A {POINTS_TO_WIN}", C_DIM, WIDTH // 2, cy)

    def draw_hand_hint(self, surf):
        """Marca en el lado que le falta jugador, para invitar a entrar."""
        encendido = (pygame.time.get_ticks() // 450) % 2 == 0
        for paddle, cx in ((self.left, WIDTH // 4), (self.right, WIDTH * 3 // 4)):
            if not paddle.is_cpu:
                continue
            col = C_TEXT if encendido else C_DIM
            core.text_at(surf, self.fonts["sm"], "LEVANTA LA MANO", col, cx, FIELD_BOT - 52)
            core.text_at(surf, self.fonts["xs"], "PARA TOMAR EL CONTROL", C_DIM, cx, FIELD_BOT - 26)

    def draw_menu(self, surf):
        core.draw_overlay(surf, 225)
        cx = WIDTH // 2
        core.text_at(surf, self.fonts["xl"], "AIR PONG", C_TEXT, cx, 172)
        core.block(surf, C_ACCENT, (cx - 150, 210, 300, core.PIXEL))
        core.text_at(surf, self.fonts["sm"], "TU MANO ES LA PALETA", C_ACCENT, cx, 240)

        panel = pygame.Rect(cx - 300, 296, 600, 214)
        core.draw_frame(surf, panel, core.C_GRID, "COMO SE JUEGA", self.fonts["xs"], C_DIM)
        y = panel.y + 46
        for num, text in [
            ("01", "PARATE FRENTE A LA CAMARA, MANO ABIERTA"),
            ("02", "MANO DEL LADO IZQUIERDO = PALETA IZQUIERDA"),
            ("03", "MANO DEL LADO DERECHO = PALETA DERECHA"),
            ("04", "SI UN LADO ESTA VACIO, LO JUEGA LA CPU"),
        ]:
            core.text_at(surf, self.fonts["xs"], num, C_ACCENT, panel.x + 28, y, "midleft")
            core.text_at(surf, self.fonts["xs"], text, C_TEXT, panel.x + 74, y, "midleft")
            y += 40

        if (pygame.time.get_ticks() // 450) % 2 == 0:
            core.text_at(surf, self.fonts["md"], "> ESPACIO PARA JUGAR <", C_ACCENT, cx, 570)

        estado, col = core.camera_status(self.camera)
        if self.camera.error:
            estado += " - PUEDES JUGAR CON EL MOUSE"
        core.text_at(surf, self.fonts["xs"], estado, col, cx, 626)

    def draw_gameover(self, surf):
        core.draw_overlay(surf, 215)
        cx = WIDTH // 2
        lado = "IZQUIERDA" if self.winner.side == "L" else "DERECHA"

        if self.winner.is_cpu:
            core.text_at(surf, self.fonts["xl"], "GANA LA CPU", C_BAD, cx, 236)
        else:
            core.text_at(surf, self.fonts["xl"], "VICTORIA", self.winner.color, cx, 236)
            core.text_at(surf, self.fonts["sm"], f"JUGADOR {lado}", self.winner.color, cx, 296)

        marcador = pygame.Rect(cx - 170, 348, 340, 96)
        core.block(surf, core.C_PANEL, marcador, borde=core.C_GRID)
        core.text_at(surf, self.fonts["lg"], str(self.left.score), self.left.color, cx - 96, marcador.centery)
        core.text_at(surf, self.fonts["md"], "-", C_DIM, cx, marcador.centery)
        core.text_at(surf, self.fonts["lg"], str(self.right.score), self.right.color, cx + 96, marcador.centery)

        core.text_at(surf, self.fonts["xs"], f"MEJOR RACHA: {self.best_rally} GOLPES", C_GOLD, cx, 478)
        if (pygame.time.get_ticks() // 450) % 2 == 0:
            core.text_at(surf, self.fonts["md"], "> ESPACIO REVANCHA <", C_TEXT, cx, 556)

    # ---------- bucle ----------
    def run(self):
        while True:
            core.handle_window_events(self.camera, self.on_key)

            canvas = pygame.Surface((WIDTH, HEIGHT))
            self.draw_field(canvas)

            if self.state == "COUNTDOWN":
                now = pygame.time.get_ticks()
                if now - self.count_tick >= 800:
                    self.count -= 1
                    self.count_tick = now
                    self.synth.play(self.snd_beep)
                    if self.count <= 0:
                        self.serve(getattr(self, "serve_dir", None))
                        self.state = "PLAYING"
                left_y, right_y = self.read_hands()
                self.left.update_from_hand(left_y)
                self.right.update_from_hand(right_y)
                self.left.tick()
                self.right.tick()

            elif self.state == "PLAYING":
                self.update_play()

            if self.state in ("PLAYING", "COUNTDOWN", "GAMEOVER"):
                self.left.draw(canvas)
                self.right.draw(canvas)
                if self.powerup:
                    self.powerup.draw(canvas, self.fonts["xs"])
                for ball in self.balls:
                    ball.draw(canvas)
                self.draw_hud(canvas)
                if self.state != "GAMEOVER":
                    self.draw_hand_hint(canvas)

            self.fx.update_and_draw(canvas)

            if self.state == "COUNTDOWN":
                txt = str(self.count) if self.count > 0 else "¡VA!"
                core.text_at(canvas, self.fonts["xl"], txt, C_GOLD, WIDTH // 2, HEIGHT // 2)
            elif self.state == "MENU":
                self.draw_menu(canvas)
            elif self.state == "GAMEOVER":
                self.draw_gameover(canvas)

            core.draw_camera_pip(canvas, self.camera, self.fonts)
            # La barra va hasta el final para que nada la tape.
            core.draw_chrome(canvas, self.fonts, "AIR PONG")

            ox = oy = 0
            if self.shake > 0:
                ox, oy = random.randint(-5, 5), random.randint(-5, 5)
                self.shake -= 1
            self.screen.fill((0, 0, 0))
            self.screen.blit(canvas, (ox, oy))
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == "__main__":
    AirPong().run()
