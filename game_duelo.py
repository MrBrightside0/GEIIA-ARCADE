"""
GEIIA ARCADE - MENTE vs MAQUINA
Piedra, papel o tijera contra una IA que aprende TUS patrones.

El gancho didactico: los humanos somos malisimos siendo aleatorios. La IA
usa una cadena de Markov (mira tus ultimas 2 jugadas para predecir la
siguiente) y en 15-20 rondas ya te esta ganando bastante mas del 33% que
sacaria jugando al azar. El marcador de "acierto de la IA" es justo la
demostracion de que aprendio algo.

Detalle importante: la IA fija su prediccion ANTES de que juegues, pero la
muestra DESPUES. Si la ensenara antes, la contrarrestarias y no probaria nada.
"""

import math
import random
from collections import Counter, defaultdict, deque

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

PIEDRA, PAPEL, TIJERA = 0, 1, 2
NOMBRES = ["PIEDRA", "PAPEL", "TIJERA"]
COLORES = [core.C_ROJO, core.C_AZUL, core.C_MORA]

# gesto de MediaPipe -> jugada
GESTO_A_JUGADA = {
    "Closed_Fist": PIEDRA,
    "Open_Palm": PAPEL,
    "Victory": TIJERA,
}

ROUNDS_TO_WIN = 5
LOCK_WINDOW = 12  # frames que promediamos para decidir tu jugada


def gana_a(jugada):
    """Devuelve la jugada que VENCE a la dada."""
    return (jugada + 1) % 3


def resultado(jugador, ia):
    if jugador == ia:
        return "EMPATE"
    return "GANAS" if gana_a(ia) == jugador else "PIERDES"


class PredictorMarkov:
    """Cadena de Markov de orden 2 con respaldo a orden 1 y a frecuencias.

    Con pocos datos las tablas de orden alto son ruido puro, asi que solo
    usamos cada nivel cuando ya vio suficientes ejemplos.
    """

    def __init__(self):
        self.hist = []
        self.t2 = defaultdict(Counter)  # (a,b) -> siguiente
        self.t1 = defaultdict(Counter)  # a     -> siguiente
        self.t0 = Counter()
        self.aciertos = 0
        self.intentos = 0

    def distribucion(self):
        """Probabilidad estimada de tu proxima jugada, y de donde salio."""
        h = self.hist
        if len(h) >= 3:
            ctx = (h[-2], h[-1])
            c = self.t2[ctx]
            if sum(c.values()) >= 2:
                return self._norm(c), "orden 2"
        if len(h) >= 2:
            c = self.t1[h[-1]]
            if sum(c.values()) >= 3:
                return self._norm(c), "orden 1"
        if sum(self.t0.values()) >= 4:
            return self._norm(self.t0), "frecuencia"
        return [1 / 3, 1 / 3, 1 / 3], "sin datos"

    @staticmethod
    def _norm(counter):
        total = sum(counter.values()) or 1
        return [counter[i] / total for i in range(3)]

    def predecir(self):
        dist, fuente = self.distribucion()
        mejor = max(range(3), key=lambda i: dist[i])
        # Si no hay senal clara, jugamos al azar en vez de fingir certeza.
        if dist[mejor] <= 0.4:
            return random.randrange(3), dist, fuente
        return mejor, dist, fuente

    def registrar(self, jugada, prediccion):
        self.intentos += 1
        if prediccion == jugada:
            self.aciertos += 1

        h = self.hist
        if len(h) >= 2:
            self.t2[(h[-2], h[-1])][jugada] += 1
        if len(h) >= 1:
            self.t1[h[-1]][jugada] += 1
        self.t0[jugada] += 1
        h.append(jugada)

    @property
    def precision(self):
        return self.aciertos / self.intentos if self.intentos else 0.0

    @property
    def patrones(self):
        return sum(len(c) for c in self.t2.values()) + sum(len(c) for c in self.t1.values())


def dibujar_jugada(surf, jugada, cx, cy, escala, color):
    """Iconos hechos con bloques, no con emojis ni curvas.

    Se dibujan sobre una reticula de celdas para que se vean como sprites de
    una maquina real, y de paso no dependen de que la compu tenga una fuente
    con emojis a color.
    """
    celda = max(core.PIXEL, core.snap(11 * escala))

    MAPAS = {
        PIEDRA: [
            "  ####  ",
            " ###### ",
            "########",
            "########",
            "########",
            " ###### ",
            "  ####  ",
        ],
        PAPEL: [
            "########",
            "#......#",
            "#.####.#",
            "#......#",
            "#.####.#",
            "#......#",
            "########",
        ],
        TIJERA: [
            "##....##",
            "###..###",
            " ###### ",
            "  ####  ",
            " ##  ## ",
            "###  ###",
            "##....##",
        ],
    }

    mapa = MAPAS[jugada]
    ancho = len(mapa[0]) * celda
    alto = len(mapa) * celda
    x0 = core.snap(cx - ancho // 2)
    y0 = core.snap(cy - alto // 2)

    for fila, linea in enumerate(mapa):
        for col, ch in enumerate(linea):
            if ch == " ":
                continue
            tono = color if ch == "#" else core.C_BG
            pygame.draw.rect(surf, tono, (x0 + col * celda, y0 + fila * celda, celda, celda))


class Duelo:
    def __init__(self):
        self.screen, self.clock, self.fonts = core.boot("GEIIA - MENTE vs MAQUINA")
        self.synth = core.Synth()

        self.snd_tick = self.synth.tone(440, 0.08, 16, "square", 0.25)
        self.snd_ya = self.synth.tone(880, 0.16, 9, "square", 0.32)
        self.snd_ganas = self.synth.chord([523, 659, 784], 0.6, 0.4)
        self.snd_pierdes = self.synth.sweep(420, 120, 0.45, 0.35)
        self.snd_empate = self.synth.tone(330, 0.22, 7, "sine", 0.28)
        self.snd_final = self.synth.chord([523, 659, 784, 1047], 1.1, 0.45)

        self.camera = core.VisionWorker("gestures", max_items=1)
        self.camera.start()

        self.fx = core.FxLayer()
        self.buffer = deque(maxlen=LOCK_WINDOW)
        self.state = "MENU"
        self.grid_offset = 0.0
        self.reset_partida()

    def reset_partida(self):
        self.ia = PredictorMarkov()
        self.score_jugador = 0
        self.score_ia = 0
        self.ronda = 0
        self.historial = []  # ("GANAS"/"PIERDES"/"EMPATE")
        self.jugada_jugador = None
        self.jugada_ia = None
        self.prediccion = None
        self.dist = [1 / 3] * 3
        self.fuente = "sin datos"
        self.res = None
        self.fase_inicio = 0
        self.count = 3

    # ---------- lectura de gestos ----------
    def gesto_actual(self):
        """Jugada mas frecuente en la ventana reciente + que tan estable es."""
        manos = self.camera.latest()
        actual = None
        if manos and manos[0].gesture in GESTO_A_JUGADA:
            if manos[0].gesture_score >= 0.55:
                actual = GESTO_A_JUGADA[manos[0].gesture]
        self.buffer.append(actual)

        validos = [g for g in self.buffer if g is not None]
        if not validos:
            return None, 0.0
        comunes = Counter(validos).most_common(1)[0]
        return comunes[0], comunes[1] / self.buffer.maxlen

    def on_key(self, e):
        if e.key == pygame.K_ESCAPE:
            if self.state == "MENU":
                core.exit_game(self.camera)
            self.state = "MENU"
        elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.state in ("MENU", "FINAL"):
                self.reset_partida()
                self.iniciar_ronda()
        elif self.state == "MENU" and e.key in (pygame.K_1, pygame.K_2, pygame.K_3):
            pass  # reservado

    def iniciar_ronda(self):
        self.ronda += 1
        self.jugada_jugador = None
        self.jugada_ia = None
        self.res = None
        self.buffer.clear()
        # La IA decide AHORA, antes de ver nada. Se revela hasta el final.
        self.prediccion, self.dist, self.fuente = self.ia.predecir()
        self.jugada_ia = gana_a(self.prediccion)
        self.state = "CUENTA"
        self.count = 3
        self.fase_inicio = pygame.time.get_ticks()

    def cerrar_ronda(self):
        jugada, estabilidad = self.gesto_actual()
        if jugada is None:
            self.res = "NO_LEIDO"
            self.state = "REVELAR"
            self.fase_inicio = pygame.time.get_ticks()
            return

        self.jugada_jugador = jugada
        self.res = resultado(jugada, self.jugada_ia)
        self.ia.registrar(jugada, self.prediccion)
        self.historial.append(self.res)

        if self.res == "GANAS":
            self.score_jugador += 1
            self.synth.play(self.snd_ganas)
            self.fx.burst(WIDTH // 4, HEIGHT // 2, C_P1, 26, 8)
        elif self.res == "PIERDES":
            self.score_ia += 1
            self.synth.play(self.snd_pierdes)
            self.fx.burst(WIDTH * 3 // 4, HEIGHT // 2, C_BAD, 26, 8)
        else:
            self.synth.play(self.snd_empate)

        self.state = "REVELAR"
        self.fase_inicio = pygame.time.get_ticks()

    # ---------- dibujo ----------
    def draw_fondo(self, surf):
        surf.fill(C_BG)
        core.draw_grid(surf, step=48)

    def draw_marcador(self, surf):
        top = core.snap(46)
        franja = pygame.Rect(0, top, WIDTH, core.snap(76))
        core.block(surf, core.C_PANEL, franja)
        core.block(surf, core.C_GRID, (0, franja.bottom, WIDTH, core.PIXEL))
        cy = franja.centery

        core.text_at(surf, self.fonts["lg"], str(self.score_jugador), C_P1, 52, cy, "midleft")
        core.text_at(surf, self.fonts["xs"], "TU", C_DIM, 52, franja.y + 14, "midleft")
        core.text_at(surf, self.fonts["lg"], str(self.score_ia), C_P2, WIDTH - 52, cy, "midright")
        core.text_at(surf, self.fonts["xs"], "IA", C_DIM, WIDTH - 52, franja.y + 14, "midright")

        core.text_at(surf, self.fonts["xs"], f"RONDA {self.ronda} / PRIMERO A {ROUNDS_TO_WIN}",
                     C_DIM, WIDTH // 2, franja.y + 16)

        # Racha de resultados como cuadritos, uno por ronda
        recientes = self.historial[-12:]
        lado = core.PIXEL * 4
        x = WIDTH // 2 - (len(recientes) * (lado + 6)) // 2
        for r in recientes:
            col = C_P1 if r == "GANAS" else (C_BAD if r == "PIERDES" else core.C_GRID)
            pygame.draw.rect(surf, col, (x, cy + 4, lado, lado))
            x += lado + 6

    def draw_cerebro(self, surf, revelar):
        """Panel que muestra lo que la IA cree que vas a hacer. Es el corazon
        de la demo: la gente ve que NO es azar."""
        pw, ph = core.snap(470), core.snap(182)
        px, py = core.snap(WIDTH // 2 - pw // 2), core.snap(HEIGHT - ph - 52)

        core.block(surf, core.C_PANEL, (px, py, pw, ph))
        core.draw_frame(surf, (px, py, pw, ph), core.C_GRID,
                        "MODELO DE LA IA", self.fonts["xs"], C_ACCENT)

        core.text_at(surf, self.fonts["xs"], f"FUENTE: {self.fuente.upper()}",
                     C_DIM, px + pw - 20, py + 24, "midright")

        y = py + 48
        for i in range(3):
            marca = revelar and i == self.prediccion
            core.text_at(surf, self.fonts["xs"], NOMBRES[i],
                         COLORES[i] if marca else C_DIM, px + 26, y + 8, "midleft")
            core.draw_bar(surf, px + 128, y, 240, 16, self.dist[i], COLORES[i])
            core.text_at(surf, self.fonts["xs"], f"{self.dist[i]*100:3.0f}%",
                         C_TEXT if marca else C_DIM, px + pw - 24, y + 8, "midright")
            if marca:
                core.block(surf, C_GOLD, (px + 108, y + 4, core.PIXEL * 3, core.PIXEL * 3))
            y += 32

        acc = self.ia.precision
        col = C_BAD if acc > 0.45 else C_DIM
        core.text_at(
            surf, self.fonts["xs"],
            f"ACIERTO IA {acc*100:.0f}%   AZAR 33%   PATRONES {self.ia.patrones}",
            col, px + pw // 2, py + ph - 18,
        )

    def draw_lectura(self, surf):
        """Feedback en vivo de lo que la camara te ve hacer."""
        jugada, estabilidad = self.gesto_actual()
        cx, cy = WIDTH // 2, 228
        if jugada is None:
            core.text_at(surf, self.fonts["sm"], "NO VEO TU MANO", C_BAD, cx, cy)
            core.text_at(surf, self.fonts["xs"], "MUESTRALA COMPLETA Y DE FRENTE", C_DIM, cx, cy + 28)
        else:
            core.text_at(surf, self.fonts["xs"], "TE VEO HACER", C_DIM, cx, cy - 26)
            core.text_at(surf, self.fonts["sm"], NOMBRES[jugada], COLORES[jugada], cx, cy)
            core.draw_bar(surf, cx - 90, cy + 24, 180, 10, estabilidad, COLORES[jugada])

    def draw_duelo(self, surf, mostrar_jugador):
        izq_x, der_x, cy = WIDTH // 4, WIDTH * 3 // 4, 352
        core.text_at(surf, self.fonts["xs"], "TU", C_P1, izq_x, cy - 74)
        core.text_at(surf, self.fonts["xs"], "IA", C_P2, der_x, cy - 74)

        if mostrar_jugador and self.jugada_jugador is not None:
            dibujar_jugada(surf, self.jugada_jugador, izq_x, cy, 1.0, COLORES[self.jugada_jugador])
            core.text_at(surf, self.fonts["sm"], NOMBRES[self.jugada_jugador], C_TEXT, izq_x, cy + 64)
        else:
            core.text_at(surf, self.fonts["xl"], "?", core.C_GRID, izq_x, cy)

        if self.state == "REVELAR":
            dibujar_jugada(surf, self.jugada_ia, der_x, cy, 1.0, COLORES[self.jugada_ia])
            core.text_at(surf, self.fonts["sm"], NOMBRES[self.jugada_ia], C_TEXT, der_x, cy + 64)
        else:
            core.text_at(surf, self.fonts["xl"], "?", core.C_GRID, der_x, cy)

    def draw_menu(self, surf):
        core.draw_overlay(surf, 228)
        cx = WIDTH // 2
        core.text_at(surf, self.fonts["xl"], "MENTE VS MAQUINA", C_TEXT, cx, 132)
        core.block(surf, C_ACCENT, (cx - 190, 172, 380, core.PIXEL))
        core.text_at(surf, self.fonts["sm"], "¿PUEDES SER IMPREDECIBLE?", C_ACCENT, cx, 202)

        panel = pygame.Rect(cx - 310, 254, 620, 172)
        core.draw_frame(surf, panel, core.C_GRID, "COMO SE JUEGA", self.fonts["xs"], C_DIM)
        y = panel.y + 44
        for num, txt in [
            ("01", "MUESTRA TU MANO A LA CAMARA"),
            ("02", "AL GRITO DE ¡YA! HAZ TU JUGADA Y SOSTENLA"),
            ("03", "LA IA ESTUDIA TUS PATRONES. SUERTE."),
        ]:
            core.text_at(surf, self.fonts["xs"], num, C_ACCENT, panel.x + 28, y, "midleft")
            core.text_at(surf, self.fonts["xs"], txt, C_TEXT, panel.x + 74, y, "midleft")
            y += 40

        for i, jugada in enumerate((PIEDRA, PAPEL, TIJERA)):
            x = cx - 210 + i * 210
            dibujar_jugada(surf, jugada, x, 494, 0.6, COLORES[jugada])
            core.text_at(surf, self.fonts["xs"], NOMBRES[jugada], COLORES[jugada], x, 546)
            gesto = ("PUÑO", "PALMA", "VICTORIA")[i]
            core.text_at(surf, self.fonts["xs"], gesto, C_DIM, x, 570)

        if (pygame.time.get_ticks() // 450) % 2 == 0:
            core.text_at(surf, self.fonts["md"], "> ESPACIO PARA EMPEZAR <", C_ACCENT, cx, 628)
        estado, col = core.camera_status(self.camera)
        core.text_at(surf, self.fonts["xs"], estado, col, cx, 678)

    def draw_final(self, surf):
        core.draw_overlay(surf, 228)
        cx = WIDTH // 2
        gano = self.score_jugador > self.score_ia
        core.text_at(surf, self.fonts["xl"], "LE GANASTE" if gano else "GANA LA IA",
                     C_P1 if gano else C_BAD, cx, 170)

        marcador = pygame.Rect(cx - 150, 224, 300, 84)
        core.block(surf, core.C_PANEL, marcador, borde=core.C_GRID)
        core.text_at(surf, self.fonts["lg"], str(self.score_jugador), C_P1, cx - 84, marcador.centery)
        core.text_at(surf, self.fonts["md"], "-", C_DIM, cx, marcador.centery)
        core.text_at(surf, self.fonts["lg"], str(self.score_ia), C_P2, cx + 84, marcador.centery)

        acc = self.ia.precision
        panel = pygame.Rect(cx - 300, 348, 600, 148)
        core.draw_frame(surf, panel, core.C_GRID, "LO QUE APRENDIO", self.fonts["xs"], C_ACCENT)
        core.text_at(surf, self.fonts["sm"], f"TE ADIVINO EL {acc*100:.0f}% DE LAS JUGADAS",
                     C_GOLD, cx, panel.y + 46)
        core.draw_bar(surf, cx - 200, panel.y + 70, 400, 14, acc, C_GOLD)
        core.text_at(surf, self.fonts["xs"], "AL AZAR HABRIA ACERTADO 33%", C_DIM, cx, panel.y + 100)

        veredicto = (
            "ERES BASTANTE IMPREDECIBLE" if acc < 0.36 else
            "LA IA TE LEYO LOS PATRONES" if acc < 0.5 else
            "LA IA TE TENIA DESCIFRADO"
        )
        core.text_at(surf, self.fonts["sm"], veredicto, C_ACCENT, cx, panel.y + 126)

        if (pygame.time.get_ticks() // 450) % 2 == 0:
            core.text_at(surf, self.fonts["md"], "> ESPACIO OTRA VEZ <", C_TEXT, cx, 552)

    # ---------- bucle ----------
    def run(self):
        while True:
            core.handle_window_events(self.camera, self.on_key)
            now = pygame.time.get_ticks()

            canvas = pygame.Surface((WIDTH, HEIGHT))
            self.draw_fondo(canvas)

            if self.state == "CUENTA":
                paso = (now - self.fase_inicio) // 700
                nuevo = 3 - paso
                if nuevo != self.count and nuevo >= 0:
                    self.count = nuevo
                    self.synth.play(self.snd_ya if self.count == 0 else self.snd_tick)
                if paso >= 4:
                    self.cerrar_ronda()

            elif self.state == "REVELAR":
                if now - self.fase_inicio > 2600:
                    if self.score_jugador >= ROUNDS_TO_WIN or self.score_ia >= ROUNDS_TO_WIN:
                        self.state = "FINAL"
                        self.synth.play(self.snd_final)
                    else:
                        self.iniciar_ronda()

            if self.state in ("CUENTA", "REVELAR"):
                self.draw_marcador(canvas)
                self.draw_duelo(canvas, mostrar_jugador=(self.state == "REVELAR"))
                self.draw_cerebro(canvas, revelar=(self.state == "REVELAR"))

                if self.state == "CUENTA":
                    self.draw_lectura(canvas)
                    etiquetas = {3: "PIEDRA", 2: "PAPEL", 1: "TIJERA", 0: "¡YA!"}
                    txt = etiquetas.get(self.count, "")
                    fuente = self.fonts["xl"] if self.count == 0 else self.fonts["lg"]
                    col = C_GOLD if self.count == 0 else C_TEXT
                    core.text_at(canvas, fuente, txt, col, WIDTH // 2, 166)
                else:
                    if self.res == "NO_LEIDO":
                        core.text_at(canvas, self.fonts["lg"], "NO TE VI LA MANO", C_BAD, WIDTH // 2, 160)
                        core.text_at(canvas, self.fonts["xs"], "ESTA RONDA NO CUENTA", C_DIM, WIDTH // 2, 202)
                    else:
                        col = {"GANAS": C_P1, "PIERDES": C_BAD, "EMPATE": C_DIM}[self.res]
                        core.text_at(canvas, self.fonts["lg"], self.res, col, WIDTH // 2, 160)
                        ok = self.prediccion == self.jugada_jugador
                        core.text_at(
                            canvas, self.fonts["xs"],
                            f"LA IA PREDIJO {NOMBRES[self.prediccion]} - {'ACERTO' if ok else 'FALLO'}",
                            C_GOLD if ok else C_DIM, WIDTH // 2, 202,
                        )

            self.fx.update_and_draw(canvas)

            if self.state == "MENU":
                self.draw_menu(canvas)
            elif self.state == "FINAL":
                self.draw_final(canvas)

            core.draw_camera_pip(canvas, self.camera, self.fonts, x=16, y=HEIGHT - 194)
            core.draw_chrome(canvas, self.fonts, "MENTE VS MAQUINA")

            self.screen.blit(canvas, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == "__main__":
    Duelo().run()
