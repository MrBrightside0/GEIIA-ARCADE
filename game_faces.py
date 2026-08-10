"""
GEIIA ARCADE - FACE BATTLE
Hasta 4 personas frente a la misma camara. Sale una emocion y todos la
imitan; la IA califica quien la clava mejor.

Como se califica: MediaPipe FaceLandmarker devuelve 52 "blendshapes", que son
coeficientes 0..1 de musculos faciales (sonrisa izquierda, ceja abajo,
mandibula abierta, etc). Cada emocion es una receta ponderada sobre esos
coeficientes, asi que la puntuacion sale de un modelo real y no de reglas
geometricas hechas a mano.

La camara va de fondo a pantalla completa con un aro de color sobre cada
jugador: asi la gente se ve a si misma y entiende el juego sin explicacion.
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
    C_TEXT,
    HEIGHT,
    PLAYER_COLORS,
    WIDTH,
)

MAX_JUGADORES = 4
RONDAS = 6
DURACION_RONDA = 4200  # ms para imitar
DURACION_RESULTADO = 2600
UMBRAL_BUENO = 0.50  # a partir de aqui consideramos que si la hizo

# ---- Robustez con publico alrededor ----
# En una feria hay gente caminando detras todo el tiempo. Pedimos mas caras
# de las que jugamos para poder descartar a los que pasan, y emparejamos
# cada jugador con la cara mas cercana a donde estaba en vez de reordenar
# por X: si no, una sola cara extra recorre a todos y cruza los puntajes.
CARAS_A_BUSCAR = 6
TAMANO_MIN_CARA = 0.085   # ancho normalizado; mas chica = demasiado lejos
RADIO_CARA = 0.14         # cuanto puede moverse una cara entre cuadros
PACIENCIA_CARA = 45       # cuadros sin verte antes de soltar tu lugar

# La camara es 4:3; la dibujamos con su proporcion real y mapeamos las
# coordenadas dentro de ese rectangulo para que los aros caigan en su lugar.
CAM_H = HEIGHT
CAM_W = int(HEIGHT * 4 / 3)
CAM_X = (WIDTH - CAM_W) // 2
CAM_Y = 0


class Emocion:
    """Receta sobre blendshapes.

    El puntaje NO es un promedio de todos los componentes. Antes lo era, y
    por eso ENOJO y CACHETES casi no se lograban: blendshapes secundarios
    que en la practica apenas se activan (noseSneer llega como a 0.1 aunque
    frunzas con todo) arrastraban el promedio hacia abajo aunque hicieras
    el gesto principal perfecto.

    Ahora manda el gesto PRINCIPAL: hacerlo bien ya vale 0.8, suficiente para
    ganar la ronda. Los apoyos solo suman hasta 0.2 extra, nunca restan.

    'gain' compensa el rango real de cada coeficiente. cheekPuff, por
    ejemplo, rara vez pasa de 0.3 por mucho que infles los cachetes, asi
    que necesita una ganancia alta.
    """

    def __init__(self, nombre, instruccion, principal, apoyos, color):
        self.nombre = nombre
        self.instruccion = instruccion
        self.principal = principal  # (gain, (blendshapes...))
        self.apoyos = apoyos        # [(peso, gain, (blendshapes...))]
        self.color = color

    def _base(self, face):
        gain, nombres = self.principal
        return min(1.0, face.bs(*nombres) * gain)

    def puntuar(self, face):
        base = self._base(face)
        bonus = 0.0
        for peso, gain, nombres in self.apoyos:
            bonus += peso * min(1.0, face.bs(*nombres) * gain)
        return max(0.0, min(1.0, base * 0.8 + min(1.0, bonus) * 0.2))


class EmocionGuino(Emocion):
    """El guino no es 'ojo cerrado' sino UN ojo cerrado y el otro abierto,
    o sea la DIFERENCIA entre los dos."""

    def _base(self, face):
        izq = face.bs("eyeBlinkLeft")
        der = face.bs("eyeBlinkRight")
        return min(1.0, abs(izq - der) * 1.4)


EMOCIONES = [
    Emocion("SONRISA", "sonríe lo más grande que puedas",
            (1.3, ("mouthSmileLeft", "mouthSmileRight")),
            [(1.0, 1.8, ("cheekSquintLeft", "cheekSquintRight"))],
            core.C_VERDE),
    Emocion("SORPRESA", "abre la boca y sube las cejas",
            (1.3, ("jawOpen",)),
            [(1.0, 1.5, ("browOuterUpLeft", "browOuterUpRight")),
             (0.6, 1.4, ("eyeWideLeft", "eyeWideRight"))],
            core.C_AMBAR),
    # browDown pico real ~0.4-0.6 aunque frunzas fuerte -> ganancia alta
    Emocion("ENOJO", "frunce el ceño con todo",
            (2.2, ("browDownLeft", "browDownRight")),
            [(0.7, 2.5, ("noseSneerLeft", "noseSneerRight")),
             (0.5, 2.0, ("mouthPressLeft", "mouthPressRight"))],
            core.C_ROJO),
    Emocion("BESO", "haz trompita",
            (1.4, ("mouthPucker",)),
            [(1.0, 1.6, ("mouthFunnel",))],
            core.C_MORA),
    Emocion("TRISTEZA", "boca hacia abajo y cejas de perrito",
            (2.5, ("mouthFrownLeft", "mouthFrownRight")),
            [(1.0, 1.5, ("browInnerUp",))],
            core.C_AZUL),
    EmocionGuino("GUIÑO", "cierra UN solo ojo", (1.0, ()), [], core.C_MORA),
    # cheekPuff es de los coeficientes mas apagados del modelo: pico ~0.25
    Emocion("CACHETES", "infla los cachetes como globo",
            (4.0, ("cheekPuff",)),
            [(0.5, 2.0, ("mouthClose",))],
            core.C_AMBAR),
    Emocion("BOCA ABIERTA", "abre la boca lo más que puedas",
            (1.35, ("jawOpen",)),
            [],
            core.C_VERDE),
]


class Jugador:
    def __init__(self, slot, pos_norm=None):
        self.slot = slot
        self.color = PLAYER_COLORS[slot]
        self.puntos = 0
        self.score_actual = 0.0
        self.mejor_ronda = 0.0
        self.pos = None        # (x, y) en pantalla, para dibujar
        self.pos_norm = pos_norm  # (x, y) 0..1, para reencontrarlo
        self.sin_cara = 0
        self.radio = 60

    @property
    def nombre(self):
        return f"P{self.slot + 1}"


def cam_a_pantalla(nx, ny):
    return CAM_X + nx * CAM_W, CAM_Y + ny * CAM_H


class FaceBattle:
    def __init__(self):
        self.screen, self.clock, self.fonts = core.boot("GEIIA FACE BATTLE")
        self.synth = core.Synth()

        self.snd_tick = self.synth.tone(660, 0.08, 16, "square", 0.22)
        self.snd_ya = self.synth.tone(990, 0.18, 8, "square", 0.3)
        self.snd_ronda = self.synth.chord([523, 659, 784], 0.55, 0.4)
        self.snd_nadie = self.synth.sweep(400, 140, 0.4, 0.3)
        self.snd_final = self.synth.chord([523, 659, 784, 1047], 1.2, 0.45)
        self.snd_join = self.synth.tone(760, 0.12, 12, "sine", 0.28)

        self.camera = core.VisionWorker("faces", max_items=CARAS_A_BUSCAR)
        self.camera.start()

        self.fx = core.FxLayer()
        self.state = "MENU"
        self.n_jugadores = 0
        self.ultimo_conteo = 0
        self.debug_bs = False
        self.reset_partida()

    def reset_partida(self):
        self.jugadores = []
        self.ronda = 0
        self.emocion = None
        self.emociones_usadas = []
        self.fase_inicio = 0
        self.count = 3
        self.ganador_ronda = None

    # ---------- deteccion ----------
    def caras_visibles(self):
        """Caras lo bastante grandes para ser de alguien parado al frente.
        Las de la gente que va pasando por detras se ven mucho mas chicas."""
        return [f for f in self.camera.latest() if f.size >= TAMANO_MIN_CARA]

    def caras_ordenadas(self):
        """De izquierda a derecha. Solo para el lobby, donde todavia no hay
        jugadores a quienes darles seguimiento."""
        return sorted(self.caras_visibles(), key=lambda f: f.center[0])

    def asignar_caras(self):
        """Empareja cada jugador con la cara mas cercana a donde estaba.

        Antes esto se resolvia ordenando por X en cada cuadro, y funcionaba
        solo si nadie mas aparecia. Con publico caminando detras, una cara
        extra a la izquierda recorria a todos los jugadores un lugar y los
        puntajes se cruzaban a media ronda.
        """
        libres = self.caras_visibles()
        asignacion = {}

        # 1) Emparejar por cercania, del par mas cercano al mas lejano
        pares = []
        for j in self.jugadores:
            if j.pos_norm is None:
                continue
            for idx, f in enumerate(libres):
                d = math.dist(j.pos_norm, f.center)
                if d <= RADIO_CARA:
                    pares.append((d, j.slot, idx))
        pares.sort()

        slots_usados, caras_usadas = set(), set()
        for _, slot, idx in pares:
            if slot in slots_usados or idx in caras_usadas:
                continue
            asignacion[slot] = libres[idx]
            slots_usados.add(slot)
            caras_usadas.add(idx)

        # 2) A quien nunca hemos visto (o lleva mucho perdido) le damos una
        #    cara libre, de izquierda a derecha
        huerfanos = [j for j in self.jugadores
                     if j.slot not in slots_usados and j.pos_norm is None]
        sobrantes = sorted(
            (f for i, f in enumerate(libres) if i not in caras_usadas),
            key=lambda f: f.center[0],
        )
        for j, f in zip(sorted(huerfanos, key=lambda j: j.slot), sobrantes):
            asignacion[j.slot] = f

        return asignacion

    def on_key(self, e):
        if e.key == pygame.K_ESCAPE:
            if self.state == "MENU":
                core.exit_game(self.camera)
            self.state = "MENU"
        elif e.key == pygame.K_F3:
            self.debug_bs = not self.debug_bs  # inspector de blendshapes
        elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
            if self.state == "MENU":
                self.reset_partida()
                self.state = "LOBBY"
            elif self.state == "LOBBY":
                caras = self.caras_ordenadas()
                if caras:
                    self.n_jugadores = min(len(caras), MAX_JUGADORES)
                    # Guardamos donde estaba cada quien al arrancar: es el
                    # ancla con la que los volvemos a encontrar cada cuadro.
                    self.jugadores = [
                        Jugador(i, pos_norm=caras[i].center)
                        for i in range(self.n_jugadores)
                    ]
                    self.iniciar_ronda()
            elif self.state == "FINAL":
                self.reset_partida()
                self.state = "LOBBY"

    def iniciar_ronda(self):
        self.ronda += 1
        # No repetir emociones mientras queden sin usar
        disponibles = [e for e in EMOCIONES if e not in self.emociones_usadas] or EMOCIONES[:]
        self.emocion = random.choice(disponibles)
        self.emociones_usadas.append(self.emocion)
        for j in self.jugadores:
            j.score_actual = 0.0
            j.mejor_ronda = 0.0
        self.ganador_ronda = None
        self.count = 3
        self.state = "CUENTA"
        self.fase_inicio = pygame.time.get_ticks()

    def actualizar_scores(self):
        asignacion = self.asignar_caras()
        for j in self.jugadores:
            cara = asignacion.get(j.slot)
            if cara is None:
                j.score_actual = 0.0
                j.sin_cara += 1
                # Si de plano se fue, suelta su lugar para que alguien mas
                # pueda ocuparlo en vez de quedarse trabado para siempre.
                if j.sin_cara > PACIENCIA_CARA:
                    j.pos_norm = None
                continue
            j.sin_cara = 0
            j.pos_norm = cara.center
            j.pos = cam_a_pantalla(*cara.center)
            j.radio = max(45, int(cara.size * CAM_W * 0.85))
            j.score_actual = self.emocion.puntuar(cara)
            j.mejor_ronda = max(j.mejor_ronda, j.score_actual)

    def cerrar_ronda(self):
        mejores = sorted(self.jugadores, key=lambda j: j.mejor_ronda, reverse=True)
        if mejores and mejores[0].mejor_ronda >= UMBRAL_BUENO:
            self.ganador_ronda = mejores[0]
            self.ganador_ronda.puntos += 1
            self.synth.play(self.snd_ronda)
            if self.ganador_ronda.pos:
                self.fx.burst(*self.ganador_ronda.pos, self.ganador_ronda.color, 34, 9)
        else:
            self.ganador_ronda = None
            self.synth.play(self.snd_nadie)
        self.state = "RESULTADO"
        self.fase_inicio = pygame.time.get_ticks()

    # ---------- dibujo ----------
    def draw_camara(self, surf, oscurecer=150):
        surf.fill(C_BG)
        # pixel=5 baja el video y lo vuelve a subir en bloques: asi la camara
        # se ve del mismo material que el resto del arcade en vez de ser una
        # foto realista pegada sobre graficos de 8 bits.
        frame = self.camera.preview_surface(CAM_W, CAM_H, pixel=5)
        if frame:
            surf.blit(frame, (CAM_X, CAM_Y))
            if oscurecer:
                velo = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                velo.fill((*C_BG, oscurecer))
                surf.blit(velo, (0, 0))
        else:
            core.draw_grid(surf)

    def draw_aros(self, surf, mostrar_score=True):
        """Marco de esquinas tipo visor, no un aro. Se lee mejor en bloques y
        no tapa la cara de quien esta jugando."""
        p = core.PIXEL
        for j in self.jugadores:
            # sin_cara pequeño tolera parpadeos del detector sin que el marco
            # se prenda y apague todo el tiempo
            if j.pos is None or j.sin_cara > 4:
                continue
            x, y, r = core.snap(j.pos[0]), core.snap(j.pos[1]), core.snap(j.radio)
            grosor = p if j.score_actual < UMBRAL_BUENO else p * 2
            brazo = max(p * 4, r // 2)

            for sx in (-1, 1):
                for sy in (-1, 1):
                    ex, ey = x + sx * r, y + sy * r
                    # cada esquina son dos barras que entran hacia el centro
                    hx = ex if sx < 0 else ex - brazo
                    hy = ey if sy < 0 else ey - grosor
                    pygame.draw.rect(surf, j.color, (hx, hy, brazo, grosor))
                    vx = ex if sx < 0 else ex - grosor
                    vy = ey if sy < 0 else ey - brazo
                    pygame.draw.rect(surf, j.color, (vx, vy, grosor, brazo))

            etiqueta = pygame.Rect(x - r, y - r - core.snap(28), core.snap(46), core.snap(24))
            core.block(surf, j.color, etiqueta)
            core.text_at(surf, self.fonts["xs"], j.nombre, C_BG, etiqueta.centerx, etiqueta.centery)

            if mostrar_score:
                barra_y = y + r + p * 2
                core.draw_bar(surf, x - r, barra_y, r * 2, core.snap(14), j.score_actual,
                              C_GOLD if j.score_actual >= UMBRAL_BUENO else j.color)
                core.text_at(surf, self.fonts["sm"], f"{j.score_actual*100:.0f}",
                             C_GOLD if j.score_actual >= UMBRAL_BUENO else C_TEXT,
                             x, barra_y + core.snap(32))

    def draw_marcador(self, surf):
        alto = core.snap(76)
        y = HEIGHT - core.snap(30) - alto  # encima del pie compartido
        core.block(surf, core.C_PANEL, (0, y, WIDTH, alto))
        core.block(surf, core.C_GRID, (0, y, WIDTH, core.PIXEL))
        if not self.jugadores:
            return
        ancho = WIDTH // len(self.jugadores)
        for i, j in enumerate(self.jugadores):
            cx = ancho * i + ancho // 2
            core.block(surf, j.color, (cx - core.snap(22), y + core.snap(12), core.snap(44), core.PIXEL * 2))
            core.text_at(surf, self.fonts["xs"], j.nombre, j.color, cx, y + core.snap(30))
            core.text_at(surf, self.fonts["md"], str(j.puntos), C_TEXT, cx, y + core.snap(56))
            if i:
                core.block(surf, core.C_GRID, (ancho * i, y + core.PIXEL, core.PIXEL, alto))

    def draw_objetivo(self, surf, tiempo_restante=None):
        top = core.snap(46)
        alto = core.snap(128)
        core.block(surf, core.C_PANEL, (0, top, WIDTH, alto))
        core.block(surf, core.C_GRID, (0, top + alto, WIDTH, core.PIXEL))

        core.text_at(surf, self.fonts["xs"], f"RONDA {self.ronda} DE {RONDAS} - IMITA ESTO",
                     C_DIM, WIDTH // 2, top + 18)
        core.text_at(surf, self.fonts["lg"], self.emocion.nombre, self.emocion.color,
                     WIDTH // 2, top + 56)
        core.text_at(surf, self.fonts["xs"], self.emocion.instruccion.upper(),
                     C_TEXT, WIDTH // 2, top + 100)
        if tiempo_restante is not None:
            core.draw_bar(surf, WIDTH // 2 - 260, top + alto - 14, 520, 10,
                          tiempo_restante, self.emocion.color)

    def draw_menu(self, surf):
        core.draw_overlay(surf, 232)
        cx = WIDTH // 2
        core.text_at(surf, self.fonts["xl"], "FACE BATTLE", C_TEXT, cx, 138)
        core.block(surf, C_ACCENT, (cx - 200, 178, 400, core.PIXEL))
        core.text_at(surf, self.fonts["sm"], "HASTA 4 JUGADORES A LA VEZ", C_ACCENT, cx, 208)

        panel = pygame.Rect(cx - 330, 260, 660, 214)
        core.draw_frame(surf, panel, core.C_GRID, "COMO SE JUEGA", self.fonts["xs"], C_DIM)
        y = panel.y + 46
        for num, txt in [
            ("01", "JUNTENSE FRENTE A LA CAMARA, HOMBRO CON HOMBRO"),
            ("02", "SALE UNA EMOCION Y TODOS LA IMITAN A LA VEZ"),
            ("03", "LA IA MIDE 52 MUSCULOS DE TU CARA Y TE CALIFICA"),
            ("04", f"GANA QUIEN SE LLEVE MAS DE LAS {RONDAS} RONDAS"),
        ]:
            core.text_at(surf, self.fonts["xs"], num, C_ACCENT, panel.x + 28, y, "midleft")
            core.text_at(surf, self.fonts["xs"], txt, C_TEXT, panel.x + 74, y, "midleft")
            y += 40

        if (pygame.time.get_ticks() // 450) % 2 == 0:
            core.text_at(surf, self.fonts["md"], "> ESPACIO PARA EMPEZAR <", C_ACCENT, cx, 530)
        estado, col = core.camera_status(self.camera)
        core.text_at(surf, self.fonts["xs"], estado, col, cx, 584)

    def draw_lobby(self, surf):
        caras = self.caras_ordenadas()
        n = min(len(caras), MAX_JUGADORES)

        if n != self.ultimo_conteo:
            if n > self.ultimo_conteo:
                self.synth.play(self.snd_join)
            self.ultimo_conteo = n

        p = core.PIXEL
        for i, cara in enumerate(caras[:MAX_JUGADORES]):
            x, y = (core.snap(v) for v in cam_a_pantalla(*cara.center))
            r = core.snap(max(45, int(cara.size * CAM_W * 0.85)))
            col = PLAYER_COLORS[i]
            pygame.draw.rect(surf, col, (x - r, y - r, r * 2, r * 2), p)
            etiqueta = pygame.Rect(x - core.snap(26), y - r - core.snap(28), core.snap(52), core.snap(26))
            core.block(surf, col, etiqueta)
            core.text_at(surf, self.fonts["sm"], f"P{i+1}", C_BG, etiqueta.centerx, etiqueta.centery)

        top = core.snap(46)
        alto = core.snap(120)
        core.block(surf, core.C_PANEL, (0, top, WIDTH, alto))
        core.block(surf, core.C_GRID, (0, top + alto, WIDTH, p))

        core.text_at(surf, self.fonts["lg"],
                     f"{n} JUGADOR{'ES' if n != 1 else ''} DETECTADO{'S' if n != 1 else ''}",
                     C_ACCENT if n else C_BAD, WIDTH // 2, top + 40)
        if n:
            if (pygame.time.get_ticks() // 450) % 2 == 0:
                core.text_at(surf, self.fonts["sm"], "> ESPACIO CUANDO YA ESTEN TODOS <",
                             C_GOLD, WIDTH // 2, top + 88)
        else:
            core.text_at(surf, self.fonts["xs"], "ACERQUENSE Y MIREN DE FRENTE A LA CAMARA",
                         C_DIM, WIDTH // 2, top + 88)

        core.text_at(surf, self.fonts["xs"],
                     "TIP: SEPARENSE UN POCO PARA QUE LA IA LOS DISTINGA",
                     C_DIM, WIDTH // 2, HEIGHT - core.snap(56))

    def draw_resultado(self, surf):
        alto = core.snap(196)
        y = core.snap(HEIGHT // 2 - alto // 2)
        core.block(surf, core.C_PANEL, (0, y, WIDTH, alto))
        core.block(surf, core.C_GRID, (0, y, WIDTH, core.PIXEL))
        core.block(surf, core.C_GRID, (0, y + alto, WIDTH, core.PIXEL))
        cx = WIDTH // 2

        if self.ganador_ronda:
            core.text_at(surf, self.fonts["lg"], f"{self.ganador_ronda.nombre} GANA LA RONDA",
                         self.ganador_ronda.color, cx, y + 48)
            core.text_at(surf, self.fonts["xs"],
                         f"{self.emocion.nombre} AL {self.ganador_ronda.mejor_ronda*100:.0f}%",
                         C_GOLD, cx, y + 96)
        else:
            core.text_at(surf, self.fonts["lg"], "NADIE LA HIZO", C_BAD, cx, y + 48)
            core.text_at(surf, self.fonts["xs"], "HAY QUE EXAGERAR MAS LA CARA", C_DIM, cx, y + 96)

        ancho = WIDTH // max(1, len(self.jugadores))
        for i, j in enumerate(self.jugadores):
            jx = ancho * i + ancho // 2
            core.text_at(surf, self.fonts["xs"], f"{j.nombre} {j.mejor_ronda*100:.0f}%",
                         j.color, jx, y + alto - 40)
            core.draw_bar(surf, jx - 60, y + alto - 26, 120, 10, j.mejor_ronda, j.color)

    def draw_final(self, surf):
        core.draw_overlay(surf, 235)
        cx = WIDTH // 2
        core.text_at(surf, self.fonts["sm"], "RESULTADO FINAL", C_DIM, cx, 96)

        tabla = sorted(self.jugadores, key=lambda j: j.puntos, reverse=True)
        top = tabla[0].puntos if tabla else 0
        campeones = [j for j in tabla if j.puntos == top]

        if len(campeones) == 1:
            core.text_at(surf, self.fonts["xl"], f"GANA {campeones[0].nombre}",
                         campeones[0].color, cx, 158)
        else:
            core.text_at(surf, self.fonts["xl"], "EMPATE", C_GOLD, cx, 158)
        core.block(surf, C_ACCENT, (cx - 170, 200, 340, core.PIXEL))

        # Podio de bloques macizos
        alturas = [210, 156, 112, 78]
        base_y = core.snap(560)
        ancho = core.snap(144)
        hueco = core.snap(20)
        inicio = core.snap(cx - (len(tabla) * (ancho + hueco) - hueco) // 2)

        for i, j in enumerate(tabla):
            h = core.snap(alturas[min(i, 3)])
            x = inicio + i * (ancho + hueco)
            core.block(surf, j.color, (x, base_y - h, ancho, h))
            core.text_at(surf, self.fonts["lg"], str(j.puntos), C_TEXT, x + ancho // 2, base_y - h - 34)
            core.text_at(surf, self.fonts["md"], j.nombre, C_BG, x + ancho // 2, base_y - h + 32)
            core.text_at(surf, self.fonts["xs"], f"{i+1}o", C_BG, x + ancho // 2, base_y - 26)

        core.block(surf, core.C_GRID, (inicio - hueco, base_y, len(tabla) * (ancho + hueco) + hueco, core.PIXEL))

        if (pygame.time.get_ticks() // 450) % 2 == 0:
            core.text_at(surf, self.fonts["md"], "> ESPACIO OTRA RONDA <", C_TEXT, cx, 630)

    def draw_debug(self, surf):
        """F3: lista los blendshapes mas activos. Sirve para afinar recetas."""
        caras = self.caras_ordenadas()
        if not caras:
            return
        top = sorted(caras[0].blend.items(), key=lambda kv: kv[1], reverse=True)[:12]
        y = 100
        for nombre, val in top:
            core.text_at(surf, self.fonts["xs"], f"{nombre:<24}{val:.2f}", C_ACCENT, 16, y, "midleft")
            y += 20

    # ---------- bucle ----------
    def run(self):
        while True:
            core.handle_window_events(self.camera, self.on_key)
            now = pygame.time.get_ticks()

            canvas = pygame.Surface((WIDTH, HEIGHT))

            if self.state == "MENU":
                self.draw_camara(canvas, 200)
                self.draw_menu(canvas)

            elif self.state == "LOBBY":
                self.draw_camara(canvas, 90)
                self.draw_lobby(canvas)

            elif self.state == "CUENTA":
                self.draw_camara(canvas, 110)
                paso = (now - self.fase_inicio) // 750
                nuevo = 3 - paso
                if nuevo != self.count and nuevo >= 0:
                    self.count = nuevo
                    self.synth.play(self.snd_ya if self.count == 0 else self.snd_tick)
                if paso >= 4:
                    self.state = "RONDA"
                    self.fase_inicio = now

                self.actualizar_scores()
                self.draw_aros(canvas, mostrar_score=False)
                self.draw_objetivo(canvas)
                self.draw_marcador(canvas)
                txt = str(self.count) if self.count > 0 else "¡YA!"
                core.text_at(canvas, self.fonts["xl"], txt, C_GOLD, WIDTH // 2, HEIGHT // 2)

            elif self.state == "RONDA":
                self.draw_camara(canvas, 95)
                transcurrido = now - self.fase_inicio
                if transcurrido >= DURACION_RONDA:
                    self.cerrar_ronda()
                else:
                    self.actualizar_scores()
                    self.draw_aros(canvas)
                    self.draw_objetivo(canvas, 1.0 - transcurrido / DURACION_RONDA)
                    self.draw_marcador(canvas)

            elif self.state == "RESULTADO":
                self.draw_camara(canvas, 130)
                self.draw_aros(canvas, mostrar_score=False)
                self.draw_objetivo(canvas)
                self.draw_marcador(canvas)
                self.draw_resultado(canvas)
                if now - self.fase_inicio >= DURACION_RESULTADO:
                    if self.ronda >= RONDAS:
                        self.state = "FINAL"
                        self.synth.play(self.snd_final)
                    else:
                        self.iniciar_ronda()

            elif self.state == "FINAL":
                self.draw_camara(canvas, 200)
                self.draw_final(canvas)

            self.fx.update_and_draw(canvas)
            if self.debug_bs:
                self.draw_debug(canvas)
            core.draw_chrome(canvas, self.fonts, "FACE BATTLE",
                             "ESC VOLVER    F11 PANTALLA    F3 BLENDSHAPES")

            self.screen.blit(canvas, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)


if __name__ == "__main__":
    FaceBattle().run()
