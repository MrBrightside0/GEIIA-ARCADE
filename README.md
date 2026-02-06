# GEIIA Arcade: Next-Gen Python Gaming

Bienvenido a GEIIA Arcade, una colección de videojuegos arcade clásicos reinventados con Inteligencia Artificial y Visión por Computadora. Olvida el teclado: aquí tu cuerpo es el control.

---

## JUEGOS INCLUIDOS

1. Neon Racer: Overdrive (Carreras Cyberpunk)
   - Control: Mueve tu cabeza de lado a lado para conducir (Head Tracking).
   - Disparo: ¡Parpadea (o cierra los ojos fuerte) para disparar láseres!
   - Mecánica: Esquiva muros, destruye drones enemigos y recoge power-ups.

2. Human Piano: Neon Arcade (Ritmo)
   - Control: Usa tus manos frente a la cámara (Hand Tracking).
   - Mecánica: Toca las notas musicales virtuales que caen en la pantalla antes de que desaparezcan.
   - Bonus: Gana el "Pase VIP GEIIA" si obtienes una puntuación alta.

3. Neural Snake (Clásico)
   - Control: Gestos de mano o cabeza (según configuración).
   - IA: Posibilidad de ver a una red neuronal jugar sola.

4. Flappy Scream (Voz)
   - Control: El volumen de tu voz controla la altura del personaje.
   - Mecánica: ¡Grita para volar, calla para caer!

---

## INSTALACION RAPIDA

Sigue estos pasos para ejecutar el arcade en cualquier computadora (Windows/Mac/Linux).

Requisitos Previos:
- Python 3.10 o superior.
- Webcam funcional.
- Micrófono.

PASOS:

1. Clonar el repositorio:
   git clone https://github.com/TU_USUARIO/GEIIA-Arcade.git
   cd GEIIA-Arcade

2. Instalar dependencias:
   pip install -r requirements.txt

3. Ejecutar el Menú Principal:
   python main_menu.py

---

## SOLUCION DE PROBLEMAS

1. El juego se cierra al abrir la cámara:
   - Asegúrate de que ninguna otra app (Zoom, Teams, Meet) esté usando la cámara.
   - Verifica que tienes instalada la versión correcta de MediaPipe.

2. No se escucha el audio:
   - El sistema ajusta automáticamente entre Mono y Estéreo. Si falla, revisa la configuración de altavoces de Windows.

3. Error "Module not found":
   - Ejecuta "pip install -r requirements.txt" nuevamente.

---

## ESTRUCTURA DEL PROYECTO

GEIIA-Arcade/
│
├── main_menu.py       # Lanzador principal
├── game_kombat.py     # Neon Racer (Facial Control)
├── game_piano.py      # Human Piano (Hand Tracking)
├── game_snake.py      # Snake IA
├── game_flappy.py     # Flappy Voice
│
├── musica.mp3         # Música de fondo (opcional)
├── requirements.txt   # Lista de librerías necesarias
└── README.md          # Este archivo

---

CREDITOS
Desarrollado por el equipo de GEIIA (Grupo Estudiantil de Inteligencia Artificial).
Tecnologías: Python, Pygame, OpenCV, Google MediaPipe.