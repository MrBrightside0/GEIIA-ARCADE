"""
GEIIA ARCADE - Menu principal

Estilo: arcade de verdad. Paleta corta, bloques planos, tipografia de
bloque, bordes duros. Nada de degradados, brillos ni emojis de adorno.

Navegacion pensada para que un visitante lo use SIN que nadie le explique:
  - Flechas para moverse, ENTER para jugar, ESC para salir.
  - El mouse tambien funciona (hover selecciona, click juega).
  - Cada tarjeta dice cuantos jugadores son y con que se controla.

El menu lanza el juego, se esconde, y reaparece cuando el juego termina.
"""

import os
import subprocess
import sys
import threading

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import customtkinter as ctk

ctk.set_appearance_mode("Dark")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSICA = os.path.join(BASE_DIR, "musica.mp3")


class Musica:
    """Musica de fondo del menu.

    Tk no tiene audio propio, asi que usamos el mixer de pygame sin abrir
    ninguna ventana. Se pausa sola mientras corre un juego: cada juego trae
    su propio audio y encimarlos suena horrible.

    Todo va dentro de try: que falte el mp3 o que la compu no tenga salida
    de audio no puede tumbar el menu.
    """

    def __init__(self, ruta, volumen=0.30):
        self.disponible = False
        self.silenciada = False
        self._mixer = None
        try:
            import pygame

            pygame.mixer.init()
            if not os.path.exists(ruta):
                print(f"Sin música de fondo: no encontré {os.path.basename(ruta)}")
                return
            pygame.mixer.music.load(ruta)
            pygame.mixer.music.set_volume(volumen)
            pygame.mixer.music.play(-1, fade_ms=1500)
            self._mixer = pygame.mixer
            self.disponible = True
        except Exception as exc:  # noqa: BLE001 - el menu manda, no la musica
            print(f"Sin música de fondo: {exc}")

    def pausar(self):
        if self.disponible and not self.silenciada:
            self._mixer.music.pause()

    def reanudar(self):
        if self.disponible and not self.silenciada:
            self._mixer.music.unpause()

    def alternar(self):
        """Devuelve True si quedo silenciada."""
        if not self.disponible:
            return None
        self.silenciada = not self.silenciada
        if self.silenciada:
            self._mixer.music.pause()
        else:
            self._mixer.music.unpause()
        return self.silenciada

    def cerrar(self):
        if self.disponible:
            try:
                self._mixer.music.stop()
                self._mixer.quit()
            except Exception:
                pass

# ==================== PALETA ====================
# Las mismas cinco tintas que usan los juegos (ver geiia_core.py).
C_BG = "#0E0E14"
C_PANEL = "#1A1A24"
C_LINE = "#22222E"
C_INK = "#EEECE0"
C_DIM = "#707084"

C_AMBAR = "#FFC11A"
C_ROJO = "#E4474C"
C_VERDE = "#4AD082"
C_AZUL = "#4E96F6"
C_MORA = "#B074E8"

FUENTE = "Consolas"

# ==================== CATALOGO ====================
GAMES = [
    {
        "num": "01",
        "name": "NEURAL SNAKE",
        "hook": "Duelo contra una serpiente con IA.\nCombos, escudos y warps.",
        "players": "1 JUGADOR / VS IA",
        "control": "TECLADO",
        "script": "game_snake.py",
        "accent": C_VERDE,
    },
    {
        "num": "02",
        "name": "AIR PONG",
        "hook": "Pong en el aire: tu mano es la paleta.\nRétate con quien sea.",
        "players": "2 JUGADORES / 1v1",
        "control": "MANOS / CAMARA",
        "script": "game_pong.py",
        "accent": C_AZUL,
    },
    {
        "num": "03",
        "name": "MENTE VS MAQUINA",
        "hook": "Piedra, papel o tijera contra una IA\nque aprende tus patrones.",
        "players": "1 JUGADOR / VS IA",
        "control": "GESTOS / CAMARA",
        "script": "game_duelo.py",
        "accent": C_AMBAR,
    },
    {
        "num": "04",
        "name": "FACE BATTLE",
        "hook": "Imita la emoción en pantalla.\nGana quien la clave primero.",
        "players": "2 A 4 JUGADORES",
        "control": "CARA / CAMARA",
        "script": "game_faces.py",
        "accent": C_MORA,
    },
]


def check_camera():
    """Revisa si hay webcam. Corre en un hilo para no congelar la ventana."""
    try:
        import cv2
    except ImportError:
        return False
    cap = None
    for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
        intento = cv2.VideoCapture(0, backend)
        if intento.isOpened() and intento.read()[0]:
            cap = intento
            break
        intento.release()
    if cap is None:
        return False
    cap.release()
    return True


class GameCard(ctk.CTkFrame):
    def __init__(self, master, game, index, on_select, on_launch):
        super().__init__(
            master,
            fg_color=C_PANEL,
            corner_radius=0,
            border_width=3,
            border_color=C_LINE,
        )
        self.game = game
        self.index = index
        self.on_select = on_select
        self.on_launch = on_launch
        self.selected = False
        self.available = os.path.exists(os.path.join(BASE_DIR, game["script"]))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=24, pady=22)

        fila = ctk.CTkFrame(cuerpo, fg_color="transparent")
        fila.pack(fill="x")

        self.num_lbl = ctk.CTkLabel(
            fila, text=game["num"], font=(FUENTE, 40, "bold"), text_color=C_LINE
        )
        self.num_lbl.pack(side="left", padx=(0, 16))

        titulos = ctk.CTkFrame(fila, fg_color="transparent")
        titulos.pack(side="left", fill="x", expand=True)

        self.title_lbl = ctk.CTkLabel(
            titulos, text=game["name"], font=(FUENTE, 24, "bold"),
            text_color=game["accent"], anchor="w",
        )
        self.title_lbl.pack(fill="x")

        ctk.CTkLabel(
            titulos, text=game["players"], font=(FUENTE, 13),
            text_color=C_DIM, anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            cuerpo, text=game["hook"], font=(FUENTE, 14),
            text_color=C_INK, justify="left", anchor="w",
        ).pack(fill="x", pady=(16, 0))

        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.pack(fill="x", side="bottom")

        ctk.CTkLabel(
            pie, text=game["control"], font=(FUENTE, 12, "bold"),
            text_color=C_DIM, anchor="w",
        ).pack(side="left")

        self.play_lbl = ctk.CTkLabel(
            pie,
            text="ENTER >" if self.available else "FALTA ARCHIVO",
            font=(FUENTE, 13, "bold"),
            text_color=C_LINE if self.available else C_ROJO,
        )
        self.play_lbl.pack(side="right")

        for w in [self] + self._descendants():
            w.bind("<Enter>", lambda e: self.on_select(self.index))
            w.bind("<Button-1>", lambda e: self.on_launch(self.index))

    def _descendants(self):
        out, pila = [], list(self.winfo_children())
        while pila:
            w = pila.pop()
            out.append(w)
            pila.extend(w.winfo_children())
        return out

    def set_selected(self, value):
        if value == self.selected:
            return
        self.selected = value
        acento = self.game["accent"]
        self.configure(border_color=acento if value else C_LINE)
        self.num_lbl.configure(text_color=acento if value else C_LINE)
        if self.available:
            self.play_lbl.configure(text_color=acento if value else C_LINE)


class ArcadeMenu(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GEIIA ARCADE")
        self.configure(fg_color=C_BG)
        self.geometry("1180x820")
        self.minsize(1040, 760)
        self.is_fullscreen = False

        self.selected = 0
        self.cards = []
        self.launching = False

        self._build_header()
        self._build_grid()
        self._build_footer()

        for tecla, delta in (("<Left>", -1), ("<Right>", 1), ("<Up>", -2), ("<Down>", 2)):
            self.bind(tecla, lambda e, d=delta: self._move(d))
        self.bind("<Return>", lambda e: self._launch(self.selected))
        self.bind("<space>", lambda e: self._launch(self.selected))
        self.bind("<Escape>", lambda e: self._on_escape())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<m>", lambda e: self._toggle_musica())
        self.bind("<M>", lambda e: self._toggle_musica())
        self.protocol("WM_DELETE_WINDOW", self._salir)

        self.musica = Musica(MUSICA)
        self._refresh_musica()

        self._refresh_selection()
        self.focus_force()
        threading.Thread(target=self._camera_probe, daemon=True).start()
        self._blink = 0
        self._animate()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0, height=104)
        header.pack(fill="x")
        header.pack_propagate(False)

        izq = ctk.CTkFrame(header, fg_color="transparent")
        izq.pack(side="left", padx=40, pady=22)

        marca = ctk.CTkFrame(izq, fg_color="transparent")
        marca.pack(anchor="w")
        ctk.CTkFrame(marca, fg_color=C_AMBAR, corner_radius=0, width=14, height=34).pack(
            side="left", padx=(0, 12)
        )
        ctk.CTkLabel(
            marca, text="GEIIA ARCADE", font=(FUENTE, 32, "bold"), text_color=C_INK
        ).pack(side="left")

        ctk.CTkLabel(
            izq,
            text="GRUPO ESTUDIANTIL DE INGENIERIA EN INTELIGENCIA ARTIFICIAL",
            font=(FUENTE, 11),
            text_color=C_DIM,
        ).pack(anchor="w", pady=(6, 0))

        ctk.CTkLabel(
            header, text="4 JUEGOS", font=(FUENTE, 18, "bold"), text_color=C_DIM
        ).pack(side="right", padx=40)

        ctk.CTkFrame(self, fg_color=C_LINE, corner_radius=0, height=3).pack(fill="x")

    def _build_grid(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=32)
        body.grid_columnconfigure((0, 1), weight=1, uniform="c")
        body.grid_rowconfigure((0, 1), weight=1, uniform="r")

        for i, game in enumerate(GAMES):
            card = GameCard(body, game, i, self._select, self._launch)
            card.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="nsew")
            self.cards.append(card)

    def _build_footer(self):
        ctk.CTkFrame(self, fg_color=C_LINE, corner_radius=0, height=3).pack(fill="x")
        footer = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0, height=56)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self.hint_lbl = ctk.CTkLabel(
            footer,
            text="FLECHAS MOVER   ENTER JUGAR   M MUSICA   F11 PANTALLA   ESC SALIR",
            font=(FUENTE, 13, "bold"),
            text_color=C_DIM,
        )
        self.hint_lbl.pack(side="left", padx=40)

        self.cam_lbl = ctk.CTkLabel(
            footer, text="CAMARA ...", font=(FUENTE, 13, "bold"), text_color=C_DIM
        )
        self.cam_lbl.pack(side="right", padx=40)

        self.mus_lbl = ctk.CTkLabel(
            footer, text="", font=(FUENTE, 13, "bold"), text_color=C_DIM
        )
        self.mus_lbl.pack(side="right", padx=(0, 24))

    def _move(self, delta):
        self._select((self.selected + delta) % len(self.cards))

    def _select(self, index):
        if index != self.selected:
            self.selected = index
            self._refresh_selection()

    def _refresh_selection(self):
        for i, card in enumerate(self.cards):
            card.set_selected(i == self.selected)

    def _on_escape(self):
        if self.is_fullscreen:
            self._toggle_fullscreen()
        else:
            self._salir()

    def _salir(self):
        self.musica.cerrar()
        self.destroy()

    def _toggle_musica(self):
        self.musica.alternar()
        self._refresh_musica()

    def _refresh_musica(self):
        if not self.musica.disponible:
            self.mus_lbl.configure(text="")
            return
        if self.musica.silenciada:
            self.mus_lbl.configure(text="MUSICA OFF", text_color=C_DIM)
        else:
            self.mus_lbl.configure(text="MUSICA ON", text_color=C_VERDE)

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def _launch(self, index):
        if self.launching:
            return
        game = GAMES[index]
        path = os.path.join(BASE_DIR, game["script"])
        if not os.path.exists(path):
            return

        self.launching = True
        self.withdraw()
        self.musica.pausar()  # el juego trae su propio audio

        def run():
            env = dict(os.environ)
            env["GEIIA_FROM_MENU"] = "1"  # el juego sabe que no debe relanzar el menu
            try:
                subprocess.run([sys.executable, path], cwd=BASE_DIR, env=env)
            except Exception as exc:  # noqa: BLE001 - el menu nunca debe morir
                print(f"Error ejecutando {game['script']}: {exc}")
            self.after(0, self._restore)

        threading.Thread(target=run, daemon=True).start()

    def _restore(self):
        self.launching = False
        self.deiconify()
        self.focus_force()
        self.musica.reanudar()

    def _camera_probe(self):
        ok = check_camera()
        self.after(0, lambda: self._set_camera_status(ok))

    def _set_camera_status(self, ok):
        if ok:
            self.cam_lbl.configure(text="CAMARA LISTA", text_color=C_VERDE)
        else:
            self.cam_lbl.configure(text="SIN CAMARA - 3 JUEGOS LA NECESITAN", text_color=C_ROJO)

    def _animate(self):
        """Parpadeo del indicador de la tarjeta activa. Un solo elemento se
        mueve; el resto queda quieto."""
        self._blink = (self._blink + 1) % 10
        card = self.cards[self.selected]
        if card.available:
            visible = self._blink < 6
            card.play_lbl.configure(text="ENTER >" if visible else "ENTER")
        try:
            self.after(90, self._animate)
        except Exception:
            pass


if __name__ == "__main__":
    ArcadeMenu().mainloop()
