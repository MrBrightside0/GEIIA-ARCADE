"""
GEIIA ARCADE - Diagnostico

Corre esto cuando montes el stand en una computadora nueva o cuando algo
no jale. Revisa dependencias, modelos, camara y deteccion en vivo, y te
dice exactamente que arreglar.

    python DIAGNOSTICO.py
"""

import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

OK = "  [OK]  "
MAL = "  [MAL] "
AVISO = "  [!]   "

problemas = []


def titulo(t):
    print(f"\n{t}\n" + "-" * 58)


# ==================== 1. PYTHON ====================
titulo("1. Python")
v = sys.version_info
if v >= (3, 10):
    print(f"{OK}Python {v.major}.{v.minor}.{v.micro}")
else:
    print(f"{MAL}Python {v.major}.{v.minor} — se necesita 3.10 o superior")
    problemas.append("Instala Python 3.10+")

en_venv = sys.prefix != sys.base_prefix
print(f"{OK if en_venv else AVISO}{'usando el entorno .venv' if en_venv else 'NO estas en el .venv (usa INICIAR.bat)'}")

# ==================== 2. LIBRERIAS ====================
titulo("2. Librerias")
for modulo, paquete in [
    ("pygame", "pygame"),
    ("cv2", "opencv-python"),
    ("mediapipe", "mediapipe"),
    ("numpy", "numpy"),
    ("customtkinter", "customtkinter"),
]:
    try:
        m = __import__(modulo)
        ver = getattr(m, "__version__", getattr(getattr(m, "version", None), "ver", "?"))
        print(f"{OK}{paquete:<16} {ver}")
    except ImportError:
        print(f"{MAL}{paquete:<16} NO instalado")
        problemas.append(f"pip install {paquete}")

try:
    import mediapipe as mp

    if int(str(mp.__version__).split(".")[0]) >= 1:
        print(f"{OK}mediapipe 1.x usa la Tasks API (correcto para estos juegos)")
except Exception:
    pass

# ==================== 3. MODELOS ====================
titulo("3. Modelos de IA")
for nombre, uso in [
    ("hand_landmarker.task", "Air Pong"),
    ("gesture_recognizer.task", "Mente vs Maquina"),
    ("face_landmarker.task", "Face Battle"),
]:
    ruta = os.path.join(BASE, "models", nombre)
    if os.path.exists(ruta) and os.path.getsize(ruta) > 100000:
        print(f"{OK}{nombre:<26} ({os.path.getsize(ruta)//1024} KB) — {uso}")
    else:
        print(f"{MAL}{nombre:<26} FALTA — {uso} no va a funcionar")
        problemas.append(f"Falta models/{nombre}")

# ==================== 4. JUEGOS ====================
titulo("4. Archivos de los juegos")
for f in ["main_menu.py", "geiia_core.py", "game_snake.py", "game_pong.py",
          "game_duelo.py", "game_faces.py"]:
    existe = os.path.exists(os.path.join(BASE, f))
    print(f"{OK if existe else MAL}{f}")
    if not existe:
        problemas.append(f"Falta {f}")

# ==================== 5. CAMARA ====================
titulo("5. Camara")
mejor_fps = 0
try:
    import cv2
    import numpy as np

    backends = [("Media Foundation", cv2.CAP_MSMF), ("DirectShow", cv2.CAP_DSHOW)]
    for nombre, backend in backends:
        cap = cv2.VideoCapture(0, backend)
        if not cap.isOpened():
            print(f"{AVISO}{nombre:<18} no disponible")
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        for _ in range(8):
            cap.read()

        t0 = time.perf_counter()
        n = 0
        brillo = 0.0
        for _ in range(40):
            ok, f = cap.read()
            if ok:
                n += 1
                brillo += float(np.mean(f))
        dt = time.perf_counter() - t0
        fps = n / dt if dt else 0
        brillo = brillo / n if n else 0
        mejor_fps = max(mejor_fps, fps)
        cap.release()
        print(f"{OK}{nombre:<18} {fps:5.1f} FPS   brillo {brillo:5.1f}/255")

    if mejor_fps == 0:
        print(f"{MAL}Ninguna camara respondio")
        problemas.append("Conecta una webcam y cierra Zoom/Teams/Meet")
    elif mejor_fps < 20:
        print(f"{AVISO}Menos de 20 FPS: el tracking se va a sentir lento")
        problemas.append("Camara lenta: prueba otra webcam o mas luz")
except ImportError:
    print(f"{MAL}Sin opencv no se puede probar la camara")

# ==================== 6. DETECCION EN VIVO ====================
if mejor_fps > 0 and not problemas:
    titulo("6. Deteccion en vivo")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import geiia_core as core

    def probar(modo, n, etiqueta, instruccion, medir, umbral, segundos=9):
        """medir/umbral sirven para comprobar el filtro de cercania: el que
        descarta a la gente que pasa por detras. Si tu propio gesto queda por
        debajo del umbral, el filtro esta demasiado estricto para tu montaje."""
        print(f"\n  >>> {etiqueta}")
        print(f"      {instruccion}")
        w = core.VisionWorker(modo, max_items=n)
        w.start()
        t0 = time.time()
        while not w.available and w.error is None and time.time() - t0 < 30:
            time.sleep(0.2)
        if w.error:
            print(f"{MAL}{w.error}")
            problemas.append(str(w.error))
            w.stop()
            return

        vistos = total = maximo = 0
        tamanos = []
        t0 = time.time()
        while time.time() - t0 < segundos:
            r = w.latest()
            total += 1
            if r:
                vistos += 1
                maximo = max(maximo, len(r))
                tamanos.append(max(medir(o) for o in r))
            restante = segundos - (time.time() - t0)
            actual = max((medir(o) for o in r), default=0.0)
            print(f"\r      detectados: {len(r)}  tamano: {actual:.3f}  "
                  f"quedan {restante:3.0f}s   ", end="")
            time.sleep(0.1)
        w.stop()

        pct = 100 * vistos / max(1, total)
        print(f"\r      deteccion {pct:3.0f}% del tiempo | maximo {maximo} a la vez "
              f"| {w.fps:.0f} FPS                    ")

        if pct <= 40:
            print(f"{MAL}Casi no te vi. Revisa luz y distancia.")
            problemas.append(f"{etiqueta}: poca deteccion, revisa luz y distancia")
        elif tamanos:
            tamanos.sort()
            p10 = tamanos[int(len(tamanos) * 0.10)]
            mediana = tamanos[len(tamanos) // 2]
            pasan = sum(1 for t in tamanos if t >= umbral) / len(tamanos) * 100
            print(f"      tamano en cuadro: p10 {p10:.3f} | mediana {mediana:.3f} "
                  f"| umbral {umbral:.3f} -> pasa {pasan:.0f}%")
            if pasan < 85:
                print(f"{MAL}El filtro de cercania te esta descartando a TI.")
                print(f"        Bajalo a {p10*0.8:.2f} o acercate mas a la camara.")
                problemas.append(f"{etiqueta}: filtro de cercania demasiado estricto")
            else:
                print(f"{OK}El filtro te deja pasar y descartaria a quien pase atras.")
        time.sleep(0.4)

    import game_pong
    import game_faces

    probar("hands", 4, "MANOS (Air Pong)",
           "LEVANTA UNA O DOS MANOS ABIERTAS, como si jugaras",
           lambda h: h.span, game_pong.SPAN_MINIMO)
    probar("gestures", 3, "GESTOS (Mente vs Maquina)",
           "haz PUNO, luego PALMA, luego VICTORIA",
           lambda h: h.span, game_pong.SPAN_MINIMO)
    probar("faces", 6, "CARAS (Face Battle)",
           "mira de frente a la camara",
           lambda f: f.size, game_faces.TAMANO_MIN_CARA)

# ==================== RESUMEN ====================
titulo("RESUMEN")
if problemas:
    print("  Hay que arreglar esto:\n")
    for p in dict.fromkeys(problemas):
        print(f"    - {p}")
else:
    print("  Todo en orden. Abre INICIAR.bat y a jugar.")
print()
