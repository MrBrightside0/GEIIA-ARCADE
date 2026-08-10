"""
GEIIA ARCADE - Nucleo compartido de los juegos con camara.

Contiene lo que los tres juegos nuevos necesitan por igual:
  - Arranque de pygame + ventana con pantalla completa (F11).
  - Un hilo que captura la camara Y corre MediaPipe, para que el bucle de
    juego nunca se bloquee esperando a la vision por computadora.
  - Sintesis de sonidos (sin archivos .wav que cargar).
  - Utilidades visuales del estilo neon: particulas, texto flotante, glow.

Por que el hilo: la inferencia de MediaPipe tarda 15-30 ms. Si la corres
dentro del bucle principal el juego cae a ~30 FPS y se siente lento. Aqui el
hilo publica el ultimo resultado disponible y el juego dibuja a 60 FPS,
leyendo siempre lo mas reciente.
"""

import math
import os
import random
import sys
import threading
import time

import numpy as np

os.environ.setdefault("GLOG_minloglevel", "2")  # calla el ruido de MediaPipe

import pygame

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")

WIDTH, HEIGHT = 1120, 760

# ==================== PALETA ====================
# Arcade de verdad: pocos colores, planos, sin degradados ni brillos.
# Cinco tintas sobre un fondo casi negro. Si necesitas un color nuevo,
# reusa uno de estos en vez de inventar otro: la disciplina de paleta es
# justo lo que hace que se vea escogido y no generado.
C_BG = (14, 14, 20)
C_PANEL = (26, 26, 36)
C_GRID = (34, 34, 46)

C_INK = (238, 236, 224)  # hueso, el "blanco"
C_DIM = (112, 112, 132)  # gris de apoyo

C_AMBAR = (255, 193, 26)
C_ROJO = (228, 71, 76)
C_VERDE = (74, 208, 130)
C_AZUL = (78, 150, 246)
C_MORA = (176, 116, 232)

# Alias por rol (los juegos usan estos, no los nombres de color)
C_TEXT = C_INK
C_ACCENT = C_AMBAR
C_GOLD = C_AMBAR
C_BAD = C_ROJO
C_P1 = C_AZUL
C_P2 = C_ROJO
C_P3 = C_VERDE
C_P4 = C_MORA

PLAYER_COLORS = [C_P1, C_P2, C_P3, C_P4]

# Escala del pixelado: el texto se dibuja a 1/PIXEL del tamano y se amplia
# con vecino mas cercano, que es lo que le da el borde duro de 8 bits.
PIXEL = 3


# ==================== ARRANQUE ====================
def boot(caption):
    """Inicializa pygame con audio decente y devuelve (screen, clock, fonts)."""
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512, allowedchanges=0)
    except TypeError:
        pygame.mixer.pre_init(44100, -16, 2, 512)

    pygame.init()
    pygame.font.init()

    screen = abrir_pantalla(caption)

    return screen, pygame.time.Clock(), build_fonts()


def abrir_pantalla(caption):
    """Crea la ventana del juego.

    SCALED da escalado limpio en pantalla completa Y es lo que hace que
    pygame.display.toggle_fullscreen() funcione bien; sin esa bandera, F11
    puede no hacer nada. Pero SCALED necesita que SDL consiga un renderer
    acelerado, y en equipos con drivers viejos o por escritorio remoto eso
    falla: sin el respaldo, el juego ni siquiera abriria.
    """
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
    except pygame.error:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(caption)
    return screen


def alternar_pantalla_completa():
    """F11. No recrea la ventana, asi que la superficie que ya tenga el juego
    guardada sigue siendo valida."""
    try:
        pygame.display.toggle_fullscreen()
    except pygame.error:
        pass


def build_fonts():
    """Escala tipografica del arcade.

    Regla aprendida a golpes: solo se amplia el texto GRANDE. Renderear a
    8 px y multiplicar por 2 no da un pixel art bonito, da una mancha
    ilegible, porque a ese tamano la letra ya perdio los trazos finos.

    Los titulos si se amplian (a 30 px la letra aguanta y el bloque se ve
    intencional). El texto de lectura va a tamano real con el antialias
    apagado: bordes duros, cero difuminado, y perfectamente legible.
    """
    return {
        "xl": PixelFont(_font(32, bold=True), 2),   # 64 px, titulazos
        "lg": PixelFont(_font(23, bold=True), 2),   # 46 px, encabezados
        "md": PixelFont(_font(28, bold=True), 1),   # 28 px, marcadores
        "sm": PixelFont(_font(21, bold=True), 1),   # 21 px, texto normal
        "xs": PixelFont(_font(17, bold=True), 1),   # 17 px, apoyo
    }


# Fuentes de bloque/monoespaciadas: al pixelarlas aguantan mucho mejor que
# una tipografia con curvas finas.
_FAMILIAS = ["Consolas", "Lucida Console", "Courier New", "DejaVu Sans Mono"]


def _font(size, bold=False):
    for nombre in _FAMILIAS:
        try:
            f = pygame.font.SysFont(nombre, size, bold=bold)
            if f:
                return f
        except Exception:
            continue
    return pygame.font.Font(None, size)


class PixelFont:
    """Envuelve una fuente normal y la vuelve pixelada.

    Renderea sin antialias al tamano chico y amplia con pygame.transform.scale,
    que es vecino mas cercano: cada pixel de la fuente se vuelve un bloque de
    scale x scale. Se comporta igual que una pygame.Font, asi que los juegos
    no tienen que saber que es distinta.
    """

    __slots__ = ("f", "scale")

    def __init__(self, base, scale):
        self.f = base
        self.scale = scale

    def render(self, text, antialias=False, color=(255, 255, 255)):
        img = self.f.render(text, False, color)  # sin antialias: bordes duros
        if self.scale == 1:
            return img
        w, h = img.get_size()
        if w == 0 or h == 0:
            return img
        return pygame.transform.scale(img, (w * self.scale, h * self.scale))

    def size(self, text):
        w, h = self.f.size(text)
        return w * self.scale, h * self.scale

    def get_height(self):
        return self.f.get_height() * self.scale


def exit_game(camera=None):
    """Sale del juego. Si NO venimos del menu, lo relanza (modo suelto)."""
    if camera is not None:
        camera.stop()
    pygame.quit()
    if not os.environ.get("GEIIA_FROM_MENU"):
        try:
            import subprocess

            subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "main_menu.py")])
        except Exception:
            pass
    sys.exit()


# ==================== AUDIO SINTETIZADO ====================
class Synth:
    """Genera efectos de sonido en memoria. Cero archivos que puedan faltar."""

    def __init__(self):
        try:
            self.freq, _, self.channels = pygame.mixer.get_init()
        except Exception:
            self.freq, self.channels = 44100, 2
        self._cache = {}

    def _make(self, samples):
        peak = np.max(np.abs(samples)) or 1.0
        data = (samples * 32767 / peak).astype(np.int16)
        if self.channels == 2:
            data = np.column_stack((data, data))
        return pygame.sndarray.make_sound(np.ascontiguousarray(data))

    def tone(self, freq, dur=0.15, decay=6.0, kind="sine", vol=0.35):
        key = ("tone", freq, dur, decay, kind)
        if key not in self._cache:
            t = np.linspace(0, dur, int(self.freq * dur), False)
            if kind == "sine":
                w = np.sin(2 * np.pi * freq * t)
            elif kind == "square":
                w = np.sign(np.sin(2 * np.pi * freq * t))
            elif kind == "saw":
                w = 2 * (t * freq - np.floor(t * freq + 0.5))
            else:  # noise
                w = np.random.uniform(-1, 1, len(t))
            snd = self._make(w * np.exp(-decay * t))
            snd.set_volume(vol)
            self._cache[key] = snd
        return self._cache[key]

    def sweep(self, f0, f1, dur=0.35, vol=0.35):
        key = ("sweep", f0, f1, dur)
        if key not in self._cache:
            t = np.linspace(0, dur, int(self.freq * dur), False)
            freq = np.linspace(f0, f1, len(t))
            phase = 2 * np.pi * np.cumsum(freq) / self.freq
            snd = self._make(np.sin(phase) * np.exp(-3 * t))
            snd.set_volume(vol)
            self._cache[key] = snd
        return self._cache[key]

    def chord(self, freqs, dur=0.7, vol=0.4):
        key = ("chord", tuple(freqs), dur)
        if key not in self._cache:
            t = np.linspace(0, dur, int(self.freq * dur), False)
            w = sum(np.sin(2 * np.pi * f * t) for f in freqs)
            snd = self._make(w * np.exp(-2.5 * t))
            snd.set_volume(vol)
            self._cache[key] = snd
        return self._cache[key]

    def play(self, snd):
        try:
            snd.play()
        except Exception:
            pass


# ==================== VISION POR COMPUTADORA ====================
class Hand:
    __slots__ = ("side", "points", "gesture", "gesture_score")

    def __init__(self, side, points, gesture=None, gesture_score=0.0):
        self.side = side  # "Left" / "Right" desde el punto de vista del jugador
        self.points = points  # lista de (x, y) normalizados 0..1
        self.gesture = gesture
        self.gesture_score = gesture_score

    @property
    def palm(self):
        """Centro de la palma: promedio de muneca y nudillos."""
        idx = (0, 5, 9, 13, 17)
        xs = sum(self.points[i][0] for i in idx) / len(idx)
        ys = sum(self.points[i][1] for i in idx) / len(idx)
        return xs, ys

    @property
    def index_tip(self):
        return self.points[8]

    @property
    def span(self):
        """Que tan grande se ve la mano en el cuadro (0..1).

        Es el mejor proxy barato de distancia a la camara: la mano de quien
        esta jugando ocupa mucho mas que la de alguien que va pasando tres
        metros atras. Con esto se filtra al publico que camina detras.
        """
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return max(max(xs) - min(xs), max(ys) - min(ys))


class Face:
    __slots__ = ("points", "blend", "center", "size")

    def __init__(self, points, blend):
        self.points = points
        self.blend = blend  # dict nombre -> score 0..1
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.center = (sum(xs) / len(xs), sum(ys) / len(ys))
        self.size = max(xs) - min(xs)

    def bs(self, *names):
        """Promedio de varios blendshapes (p. ej. izquierda + derecha)."""
        vals = [self.blend.get(n, 0.0) for n in names]
        return sum(vals) / len(vals) if vals else 0.0


class VisionWorker(threading.Thread):
    """Captura de camara + inferencia MediaPipe en su propio hilo.

    mode: "hands" | "gestures" | "faces"
    """

    def __init__(self, mode, max_items=2):
        super().__init__(daemon=True)
        self.mode = mode
        self.max_items = max_items

        self._lock = threading.Lock()
        self._results = []
        self._preview = None  # ultimo frame RGB, a resolucion completa
        self._preview_seq = 0
        self._cache_surf = None
        self._cache_key = None
        self._running = True

        # La captura vive en su propio hilo y solo guarda el cuadro MAS
        # reciente. Si capturaramos e inferieramos en serie, el ciclo tardaria
        # lectura + inferencia (~60 ms) y perderiamos uno de cada dos cuadros
        # de la camara. Separados, la inferencia corre a su propio ritmo sobre
        # el cuadro mas fresco y el tracking va casi al doble de rapido.
        self._frame_lock = threading.Lock()
        self._frame = None
        self._seq = 0

        self.available = False
        self.error = None
        self.fps = 0.0

        self._cap = None
        self._detector = None

    # ---------- ciclo de vida ----------
    def run(self):
        try:
            self._setup()
        except Exception as exc:  # noqa: BLE001 - queremos degradar, no morir
            self.error = str(exc)
            self.available = False
            return

        capturador = threading.Thread(target=self._capture_loop, daemon=True)
        capturador.start()
        self._infer_loop()
        self._teardown()

    def _capture_loop(self):
        """Solo lee la camara. Siempre conserva el cuadro mas reciente.

        Vigila ademas que las lecturas realmente funcionen: si otra app
        (Zoom, Teams, o un juego que quedo abierto) tiene tomada la camara,
        VideoCapture igual reporta isOpened() == True y luego falla cada
        read() en silencio. Sin esta vigilancia el juego diria "camara lista"
        en verde mientras no ve absolutamente nada.
        """
        fallos = 0
        while self._running:
            ok, frame = self._cap.read()
            if not ok:
                fallos += 1
                if fallos == 150:  # ~1.5 s seguidos sin poder leer
                    self.error = ("otra aplicación está usando la cámara "
                                  "(cierra Zoom/Teams o el juego anterior)")
                    self.available = False
                time.sleep(0.01)
                continue

            if fallos:
                fallos = 0
                if self.error:  # se recupero sola
                    self.error = None
                    self.available = True

            # espejo horizontal + BGR->RGB de un solo golpe
            rgb = np.ascontiguousarray(frame[:, ::-1, ::-1])

            with self._frame_lock:
                self._frame = rgb
                self._seq += 1
            with self._lock:
                # Guardamos el cuadro completo, no una version reducida: el
                # hilo de captura acaba de crear este arreglo y no lo vuelve a
                # tocar, asi que quedarnos con la referencia no cuesta ninguna
                # copia y nos deja la camara a resolucion completa para el
                # fondo de Face Battle.
                self._preview = rgb
                self._preview_seq += 1

    def _infer_loop(self):
        """Corre MediaPipe sobre el ultimo cuadro disponible, sin esperar
        a la camara y sin procesar dos veces el mismo cuadro."""
        visto = -1
        t_prev = time.time()

        while self._running:
            with self._frame_lock:
                if self._frame is None or self._seq == visto:
                    frame = None
                else:
                    # el hilo de captura reemplaza el arreglo, no lo modifica,
                    # asi que quedarnos con la referencia es seguro
                    frame = self._frame
                    visto = self._seq

            if frame is None:
                time.sleep(0.002)
                continue

            try:
                results = self._infer(frame)
            except Exception:
                results = []

            now = time.time()
            dt = now - t_prev
            t_prev = now

            with self._lock:
                self._results = results
                if dt > 0:
                    self.fps = 0.85 * self.fps + 0.15 * (1.0 / dt)

    def _setup(self):
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        self._vision = vision

        # El backend importa MUCHO: medido en esta maquina, DirectShow topa
        # en 16.7 FPS y Media Foundation da 30.5 con la misma camara. Como el
        # tracking no puede ir mas rapido que la captura, probamos MSMF
        # primero y dejamos DSHOW como respaldo para camaras que no lo
        # soporten.
        cap = None
        for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
            intento = cv2.VideoCapture(0, backend)
            if intento.isOpened():
                intento.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                intento.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                intento.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, _ = intento.read()
                if ok:
                    cap = intento
                    break
            intento.release()

        if cap is None:
            raise RuntimeError("No se encontro ninguna camara")
        self._cap = cap

        def model(name):
            path = os.path.join(MODELS_DIR, name)
            if not os.path.exists(path):
                raise RuntimeError(f"Falta el modelo {name} en la carpeta models/")
            return mp_python.BaseOptions(model_asset_path=path)

        if self.mode == "hands":
            opts = vision.HandLandmarkerOptions(
                base_options=model("hand_landmarker.task"),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=self.max_items,
                min_hand_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._detector = vision.HandLandmarker.create_from_options(opts)
        elif self.mode == "gestures":
            opts = vision.GestureRecognizerOptions(
                base_options=model("gesture_recognizer.task"),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=self.max_items,
            )
            self._detector = vision.GestureRecognizer.create_from_options(opts)
        elif self.mode == "faces":
            opts = vision.FaceLandmarkerOptions(
                base_options=model("face_landmarker.task"),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=self.max_items,
                output_face_blendshapes=True,
            )
            self._detector = vision.FaceLandmarker.create_from_options(opts)
        else:
            raise ValueError(f"modo desconocido: {self.mode}")

        self._t0 = time.time()
        self.available = True

    def _timestamp_ms(self):
        # MediaPipe exige timestamps estrictamente crecientes en modo VIDEO.
        return int((time.time() - self._t0) * 1000)

    def _infer(self, rgb):
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        ts = self._timestamp_ms()

        if self.mode == "faces":
            res = self._detector.detect_for_video(image, ts)
            out = []
            for i, lms in enumerate(res.face_landmarks or []):
                blend = {}
                if res.face_blendshapes and i < len(res.face_blendshapes):
                    blend = {c.category_name: c.score for c in res.face_blendshapes[i]}
                out.append(Face([(p.x, p.y) for p in lms], blend))
            return out

        if self.mode == "gestures":
            res = self._detector.recognize_for_video(image, ts)
        else:
            res = self._detector.detect_for_video(image, ts)

        out = []
        for i, lms in enumerate(res.hand_landmarks or []):
            side = "Right"
            if res.handedness and i < len(res.handedness) and res.handedness[i]:
                # Ya volteamos el frame, asi que la etiqueta de MediaPipe
                # coincide con la mano real del jugador tal cual la ve.
                side = res.handedness[i][0].category_name
            gesture, score = None, 0.0
            gestures = getattr(res, "gestures", None)
            if gestures and i < len(gestures) and gestures[i]:
                gesture = gestures[i][0].category_name
                score = gestures[i][0].score
            out.append(Hand(side, [(p.x, p.y) for p in lms], gesture, score))
        return out

    def _teardown(self):
        try:
            if self._detector:
                self._detector.close()
        except Exception:
            pass
        try:
            if self._cap:
                self._cap.release()
        except Exception:
            pass

    def stop(self):
        self._running = False

    # ---------- lectura desde el juego ----------
    def latest(self):
        with self._lock:
            return list(self._results)

    def preview_surface(self, width, height, pixel=0):
        """Imagen de la camara lista para dibujar, a resolucion completa.

        Se deja NITIDA a proposito. Pixelarla para que combinara con los
        graficos de 8 bits sonaba coherente, pero mata lo mejor del stand:
        verte a ti mismo jugando. Los bloques son para los graficos; la
        camara es la ventana al mundo real.

        (pixel>1 sigue disponible por si algun juego lo quiere, pero ninguno
        lo usa.)

        El resultado se guarda en cache porque la camara entrega ~30 cuadros
        por segundo y el juego dibuja a 60: sin cache reescalariamos el mismo
        cuadro dos veces de gratis, y a pantalla completa eso si se siente.
        """
        with self._lock:
            arr = self._preview
            seq = self._preview_seq
            clave = (seq, width, height, pixel)
            if self._cache_key == clave:
                return self._cache_surf

        if arr is None:
            return None

        surf = pygame.surfarray.make_surface(np.transpose(arr, (1, 0, 2)))
        if pixel > 1:
            chico = pygame.transform.smoothscale(
                surf, (max(1, width // pixel), max(1, height // pixel))
            )
            salida = pygame.transform.scale(chico, (width, height))
        else:
            salida = pygame.transform.smoothscale(surf, (width, height))

        with self._lock:
            self._cache_key = clave
            self._cache_surf = salida
        return salida


# ==================== UTILIDADES VISUALES ====================
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "size", "color", "gravity")

    def __init__(self, x, y, color, speed=6.0, size=None, gravity=0.0):
        ang = random.uniform(0, math.tau)
        mag = random.uniform(0.2, 1.0) * speed
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * mag, math.sin(ang) * mag
        self.life = 255
        self.size = size or random.uniform(3, 8)
        self.color = color
        self.gravity = gravity

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= 0.96
        self.vy *= 0.96
        self.life -= 9
        self.size *= 0.95

    def draw(self, surf):
        # Cuadros solidos, no circulos con transparencia: las particulas
        # difuminadas eran otro de los tics del look generico.
        if self.life <= 0 or self.size < 1:
            return
        lado = max(PIXEL, snap(self.size))
        pygame.draw.rect(surf, self.color, (snap(self.x), snap(self.y), lado, lado))


class FloatingText:
    __slots__ = ("text", "x", "y", "color", "font", "life", "dy")

    def __init__(self, text, x, y, color, font, life=70):
        self.text, self.x, self.y = text, x, y
        self.color, self.font = color, font
        self.life = life
        self.dy = 0.0

    def update(self):
        self.life -= 1
        self.dy -= 1.4

    def draw(self, surf):
        # Parpadea al final en vez de desvanecerse: es como lo resolvian las
        # maquinas de la epoca, que no tenian canal alfa.
        if self.life <= 0:
            return
        if self.life < 18 and (self.life // 3) % 2 == 0:
            return
        img = self.font.render(self.text, False, self.color)
        surf.blit(img, (snap(self.x - img.get_width() // 2), snap(self.y + self.dy)))


class FxLayer:
    """Junta particulas y textos flotantes para no repetir listas en cada juego."""

    def __init__(self):
        self.particles = []
        self.texts = []

    def burst(self, x, y, color, count=14, speed=6.0, gravity=0.0):
        for _ in range(count):
            self.particles.append(Particle(x, y, color, speed, gravity=gravity))

    def say(self, text, x, y, color, font, life=70):
        self.texts.append(FloatingText(text, x, y, color, font, life))

    def update_and_draw(self, surf):
        for p in self.particles:
            p.update()
            p.draw(surf)
        self.particles = [p for p in self.particles if p.life > 0 and p.size >= 1]
        for t in self.texts:
            t.update()
            t.draw(surf)
        self.texts = [t for t in self.texts if t.life > 0]


def snap(v, grid=PIXEL):
    """Alinea a la retícula de pixeles. Que todo caiga en múltiplos del mismo
    bloque es lo que evita el look de 'vector con filtro retro'."""
    return int(v // grid) * grid


def block(surf, color, rect, borde=None, grosor=PIXEL):
    """Bloque plano con contorno duro. Sin degradados, sin esquinas redondas."""
    x, y, w, h = (snap(v) for v in rect)
    pygame.draw.rect(surf, color, (x, y, w, h))
    if borde:
        pygame.draw.rect(surf, borde, (x, y, w, h), grosor)


# Nombres heredados de la version con glow. Ahora dibujan bloques planos:
# se conservan para no tocar los tres juegos.
def draw_glow_rect(surf, color, rect, glow=0, radius=0, alpha=0):
    x, y, w, h = (snap(v) for v in rect)
    pygame.draw.rect(surf, color, (x, y, w, h))
    pygame.draw.rect(surf, C_BG, (x, y, w, h), PIXEL)


def draw_glow_circle(surf, color, center, radius, glow=0, alpha=0):
    cx, cy = snap(center[0]), snap(center[1])
    r = max(PIXEL, snap(radius))
    pygame.draw.circle(surf, color, (cx, cy), r)
    pygame.draw.circle(surf, C_BG, (cx, cy), r, PIXEL)


def text_at(surf, font, text, color, x, y, anchor="center"):
    img = font.render(text, False, color)
    rect = img.get_rect()
    setattr(rect, anchor, (int(x), int(y)))
    rect.x, rect.y = snap(rect.x), snap(rect.y)
    surf.blit(img, rect)
    return rect


def draw_bar(surf, x, y, w, h, pct, color, bg=C_PANEL):
    """Barra segmentada en bloques, como medidor de arcade."""
    x, y, w, h = snap(x), snap(y), snap(w), snap(h)
    pygame.draw.rect(surf, bg, (x, y, w, h))
    seg = PIXEL * 3
    total = max(1, w // seg)
    llenos = int(total * max(0.0, min(1.0, pct)))
    for i in range(llenos):
        pygame.draw.rect(surf, color, (x + i * seg, y, seg - PIXEL, h))
    pygame.draw.rect(surf, C_GRID, (x, y, w, h), PIXEL)


def draw_grid(surf, color=C_GRID, step=40, offset=0):
    """Retícula de puntos, no de líneas: pesa menos visualmente y se lee
    como fondo de arcade en vez de como papel milimétrico."""
    step = snap(step) or PIXEL
    desfase = int(offset) % step
    for y in range(-step, HEIGHT + step, step):
        for x in range(0, WIDTH, step):
            pygame.draw.rect(surf, color, (x, y + desfase, PIXEL, PIXEL))


def draw_scanlines(surf, alpha=0, step=3):
    """Ya no hace nada.

    Las scanlines encima de todo eran uno de los tics que hacian que esto
    pareciera plantilla. Se deja la funcion para no romper las llamadas.
    """
    return


def draw_frame(surf, rect, color=C_GRID, titulo=None, font=None, col_titulo=None):
    """Marco de panel con el titulo incrustado en el borde superior."""
    x, y, w, h = (snap(v) for v in rect)
    pygame.draw.rect(surf, color, (x, y, w, h), PIXEL)
    if titulo and font:
        img = font.render(titulo, False, col_titulo or color)
        pad = PIXEL * 2
        pygame.draw.rect(surf, C_BG, (x + pad * 2 - pad, y - img.get_height() // 2,
                                      img.get_width() + pad * 2, img.get_height()))
        surf.blit(img, (x + pad * 2, y - img.get_height() // 2))


def draw_chrome(surf, fonts, titulo, ayuda="ESC VOLVER    F11 PANTALLA"):
    """Cabecera y pie compartidos por los cuatro juegos. Es lo que hace que
    se sientan del mismo arcade y no cuatro proyectos sueltos."""
    alto = snap(46)
    pygame.draw.rect(surf, C_PANEL, (0, 0, WIDTH, alto))
    pygame.draw.rect(surf, C_GRID, (0, alto - PIXEL, WIDTH, PIXEL))

    pygame.draw.rect(surf, C_AMBAR, (snap(18), snap(14), PIXEL * 4, PIXEL * 6))
    text_at(surf, fonts["sm"], "GEIIA ARCADE", C_INK, snap(42), alto // 2, "midleft")
    text_at(surf, fonts["sm"], titulo, C_AMBAR, WIDTH - snap(18), alto // 2, "midright")

    pie = snap(30)
    pygame.draw.rect(surf, C_PANEL, (0, HEIGHT - pie, WIDTH, pie))
    pygame.draw.rect(surf, C_GRID, (0, HEIGHT - pie, WIDTH, PIXEL))
    text_at(surf, fonts["xs"], ayuda, C_DIM, WIDTH // 2, HEIGHT - pie // 2)
    return alto, HEIGHT - pie


def draw_camera_pip(surf, camera, fonts, x=None, y=None, w=200, h=150):
    """Recuadro con lo que ve la camara. Ayuda muchisimo a que la gente
    se encuadre sola sin que nadie le diga nada."""
    x = WIDTH - w - 16 if x is None else x
    y = HEIGHT - h - 44 if y is None else y  # 44 deja libre el pie compartido

    x, y, w, h = snap(x), snap(y), snap(w), snap(h)
    frame = camera.preview_surface(w, h) if camera else None
    if frame:
        surf.blit(frame, (x, y))
        pygame.draw.rect(surf, C_GRID, (x, y, w, h), PIXEL)
        etiqueta = f"{camera.fps:.0f}FPS"
        img = fonts["xs"].render(etiqueta, False, C_AMBAR)
        pygame.draw.rect(surf, C_BG, (x, y + h - img.get_height(), img.get_width() + PIXEL * 2, img.get_height()))
        surf.blit(img, (x + PIXEL, y + h - img.get_height()))
    else:
        pygame.draw.rect(surf, C_PANEL, (x, y, w, h))
        pygame.draw.rect(surf, C_GRID, (x, y, w, h), PIXEL)
        msg = "SIN CAMARA" if camera and camera.error else "INICIANDO"
        text_at(surf, fonts["xs"], msg, C_DIM, x + w // 2, y + h // 2)


def camera_status(camera):
    """(texto, color) del estado de la camara, para los menus.

    Media Foundation tarda ~6 s en arrancar, asi que hay que decirle a la
    gente que espere en vez de dejar la pantalla muda.
    """
    if camera is None:
        return "sin cámara", C_BAD
    if camera.error:
        return f"sin cámara: {camera.error}", C_BAD
    if not camera.available:
        return "PREPARANDO CAMARA, AGUANTA", C_AMBAR
    return f"CAMARA LISTA - {camera.fps:.0f} FPS", C_VERDE


def draw_overlay(surf, alpha=170, color=C_BG):
    s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    s.fill((*color, alpha))
    surf.blit(s, (0, 0))


def handle_window_events(camera=None, on_key=None):
    """Eventos comunes: cerrar, ESC, F11. Devuelve la lista por si el juego
    quiere procesar mas teclas."""
    events = pygame.event.get()
    for e in events:
        if e.type == pygame.QUIT:
            exit_game(camera)
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F11:
                alternar_pantalla_completa()
            elif on_key:
                on_key(e)
    return events


def smooth(current, target, factor=0.25):
    return current + (target - current) * factor
