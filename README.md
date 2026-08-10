# GEIIA ARCADE

Colección de juegos arcade controlados con **visión por computadora**: aquí el
control es tu cuerpo. Hecho por el Grupo Estudiantil de Ingeniería en
Inteligencia Artificial para la Feria Estudiantil 2026.

---

## LOS JUEGOS

| Juego | Jugadores | Control | Qué demuestra |
|---|---|---|---|
| 🐍 **Neural Snake** | 1 vs IA | Teclado (flechas) | Búsqueda voraz con evasión |
| 🏓 **Air Pong** | 2 (1v1) | Manos, cámara | Hand landmarks en tiempo real |
| ✊ **Mente vs Máquina** | 1 vs IA | Gestos, cámara | Clasificación de gestos + cadena de Markov |
| 😱 **Face Battle** | 2 a 4 | Cara, cámara | 52 blendshapes faciales |

### 🏓 Air Pong
Pong donde tu mano *es* la paleta. Se asigna por **posición**: quien tenga la
mano del lado izquierdo del cuadro controla la paleta izquierda. Si un lado no
tiene mano, lo juega la CPU — así una persona puede jugar sola y cuando llega
un amigo **solo levanta la mano y entra**, sin tocar nada.

Power-ups: `GRANDE` (paleta más larga), `DOBLE` (bola extra), `TURBO`.

### ✊ Mente vs Máquina
Piedra, papel o tijera contra una IA que **aprende tus patrones**. Usa una
cadena de Markov de orden 2 (mira tus últimas 2 jugadas) con respaldo a
orden 1 y a frecuencias simples.

Lo que engancha es el marcador: la IA muestra **qué porcentaje de tus jugadas
adivinó**. Contra alguien con patrones llega a 70-90%; el azar puro daría 33%.
La IA fija su predicción *antes* de que juegues y la revela *después* — si la
enseñara antes, la contrarrestarías y no probaría nada.

> Verificado en pruebas: contra un patrón cíclico acierta **92%**; contra
> entradas verdaderamente aleatorias baja a **34%**, o sea no hace trampa.

### 😱 Face Battle
Hasta 4 personas frente a la misma cámara. Sale una emoción y todos la imitan;
la IA califica quién la clavó. La cámara va de fondo a pantalla completa con
un aro de color por jugador.

Las 8 emociones (sonrisa, sorpresa, enojo, beso, tristeza, guiño, cachetes,
boca abierta) se puntúan con **blendshapes**: coeficientes 0..1 de músculos
faciales que devuelve el modelo. No son reglas geométricas hechas a mano.

**Afinar las recetas:** dentro del juego presiona `F3` para ver en vivo qué
blendshapes se están activando más. Con eso puedes ajustar los pesos en la
lista `EMOCIONES` de `game_faces.py`.

---

## INSTALACIÓN

### Rápida (Windows)
1. Instala Python 3.10 o superior desde [python.org](https://www.python.org/downloads/)
   — **marca la casilla "Add Python to PATH"**.
2. Doble clic en **`INSTALAR.bat`** (tarda unos minutos).
3. Doble clic en **`INICIAR.bat`** para jugar.

### Manual
```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main_menu.py
```

Los modelos de IA ya vienen en `models/` (~20 MB), así que **no necesitas
internet el día de la feria**.

### ¿Algo no jala?
```bash
python DIAGNOSTICO.py
```
Revisa dependencias, modelos, cámara y detección en vivo, y te dice qué falta.

---

## MONTAJE DEL STAND

- **Luz de frente.** Es lo que más afecta la detección. Que la luz les dé en
  la cara, no a contraluz de una ventana.
- **Distancia:** 1 a 1.5 m de la cámara. Para Face Battle con 4 personas hay
  que echarse para atrás para que quepan todos.
- **Sepárense un poco** entre jugadores: si dos caras se enciman, la IA las
  confunde.
- **Cierra Zoom, Teams y Meet** antes de abrir el arcade, o se pelean por la
  cámara. Si pasa, el juego ahora te lo dice en pantalla en vez de quedarse
  mudo sin ver nada.
- La cámara tarda **unos 6 segundos** en calentar al abrir cada juego. El menú
  del juego dice *"cámara lista"* en verde cuando ya se puede jugar.
- `F11` pone cualquier juego en pantalla completa.

### Gente pasando por detrás

En una feria hay público caminando atrás todo el tiempo, y sin cuidado eso
rompe los juegos: la mano de un curioso le arrebata la paleta al que está
jugando, o una cara extra recorre a todos los jugadores de Face Battle y les
cruza los puntajes a media ronda.

Los tres juegos de cámara lo manejan así:

1. **Filtro de cercanía.** Se mide qué tan grande se ve la mano o la cara en
   el cuadro, que es un buen proxy de distancia. Lo que se ve muy chico es
   alguien del fondo y se descarta.
2. **Continuidad.** Air Pong recuerda dónde estaba la mano que controlaba cada
   paleta y prefiere la que siga cerca, en vez de saltar a otra persona.
3. **Identidad por posición.** Face Battle empareja a cada jugador con la cara
   más cercana a donde estaba, no reordenando por posición X.

**Verifica los umbrales en tu montaje** corriendo `python DIAGNOSTICO.py`: te
mide tu propia mano y tu propia cara y te dice si el filtro te está dejando
pasar. Si te descarta a ti, baja `SPAN_MINIMO` en `game_pong.py` o
`TAMANO_MIN_CARA` en `game_faces.py` — el diagnóstico te sugiere el valor.

---

## ESTRUCTURA

```
GEIIA-ARCADE/
├── INICIAR.bat          <- doble clic para jugar
├── INSTALAR.bat         <- doble clic la primera vez
├── DIAGNOSTICO.py       <- revisa qué está fallando
│
├── main_menu.py         Menú principal (flechas + Enter, o mouse)
├── geiia_core.py        Núcleo compartido: cámara, visión, audio, efectos
│
├── game_snake.py        🐍 Neural Snake
├── game_pong.py         🏓 Air Pong
├── game_duelo.py        ✊ Mente vs Máquina
├── game_faces.py        😱 Face Battle
│
├── models/              Modelos de MediaPipe (necesarios, no borrar)
├── sounds/snake/        Efectos del Snake
└── requirements.txt
```

Los tres juegos de cámara comparten `geiia_core.py`, que se encarga de la
captura, la inferencia en hilos aparte, la síntesis de sonido y los efectos
visuales. Si quieres agregar un juego nuevo, ahí está toda la plomería.

---

## NOTAS TÉCNICAS

Cosas que costó trabajo descubrir y conviene no volver a romper:

**MediaPipe 1.x eliminó la API `mp.solutions.*`.** Los juegos usan la Tasks
API nueva (`mediapipe.tasks.python.vision`) con los modelos `.task` de
`models/`. Si copias código viejo de internet que use `mp.solutions.hands`,
no va a funcionar con esta versión.

**El backend de la cámara importa muchísimo.** Medido en una laptop de
prueba, con la misma webcam:

| Backend | FPS reales |
|---|---|
| `cv2.CAP_DSHOW` (DirectShow) | 16.7 |
| `cv2.CAP_MSMF` (Media Foundation) | **30.5** |

El tracking no puede ir más rápido que la captura, así que `geiia_core.py`
prueba **MSMF primero** y deja DirectShow de respaldo. Esto duplicó los FPS
de tracking (17 → 35). El costo es que MSMF tarda ~6 s en inicializar, pero
eso queda escondido detrás de la pantalla de menú.

**La inferencia no es el cuello de botella.** Medido: manos 20.6 ms/cuadro
(48 FPS), caras con blendshapes 3.1 ms/cuadro (326 FPS). Si el tracking se
siente lento, el problema es la cámara, no la IA.

**Captura e inferencia van en hilos separados.** Si corren en serie, el ciclo
tarda lectura + inferencia y se pierde uno de cada dos cuadros de la cámara.

**`VideoCapture` miente cuando otra app tiene la cámara.** `isOpened()`
devuelve `True` y luego cada `read()` falla en silencio. Sin vigilar eso, el
juego mostraría "cámara lista" en verde sin ver absolutamente nada. El hilo de
captura cuenta lecturas fallidas y a la segunda de fracasos avisa en pantalla.

**El texto grande se amplía; el chico no.** La tipografía es pixelada
renderizando sin antialias y escalando con vecino más cercano. Pero ampliar
texto pequeño no da pixel art, da una mancha ilegible: a 8 px la letra ya
perdió los trazos. Solo `xl` y `lg` se multiplican (×2); de `md` para abajo va
a tamaño real con el antialias apagado, que se ve duro y se lee bien.

---

## CRÉDITOS

Desarrollado por el **Grupo Estudiantil de Ingeniería en Inteligencia
Artificial (GEIIA)**.

Tecnologías: Python · Pygame · OpenCV · Google MediaPipe Tasks · CustomTkinter
