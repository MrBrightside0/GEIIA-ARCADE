import customtkinter as ctk
import subprocess
import sys
import os
import math
import threading

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

COLOR_BG = "#050510"
COLOR_CARD = "#13131F"
COLOR_ACCENT = "#00F0FF"
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_DIM = "#888899"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class GameCard(ctk.CTkFrame):
    def __init__(self, master, game_data, launch_callback, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=15, border_width=1, border_color="#2A2A35", **kwargs)
        
        self.script_path = game_data["script"]
        self.game_name = game_data["name"]
        self.callback = launch_callback
        
        full_path = os.path.join(BASE_DIR, self.script_path)
        is_available = os.path.exists(full_path)
        
        self.grid_columnconfigure(0, weight=1)
        
        status_color = "#00FF66" if is_available else "#FF3333"
        self.status_indicator = ctk.CTkFrame(self, width=10, height=10, corner_radius=5, fg_color=status_color)
        self.status_indicator.place(relx=0.92, rely=0.08, anchor="center")

        icon = game_data["name"].split()[0] if " " in game_data["name"] else "🎮"
        title_text = " ".join(game_data["name"].split()[1:]) if " " in game_data["name"] else game_data["name"]

        self.icon_label = ctk.CTkLabel(self, text=icon, font=("Arial", 40))
        self.icon_label.pack(pady=(20, 5))

        self.title_label = ctk.CTkLabel(self, text=title_text, font=("Roboto", 18, "bold"), text_color=COLOR_TEXT)
        self.title_label.pack(pady=0)

        self.desc_label = ctk.CTkLabel(self, text=game_data["desc"], font=("Roboto", 12), text_color=COLOR_TEXT_DIM, wraplength=180)
        self.desc_label.pack(pady=(5, 15), padx=10)

        btn_color = game_data["color"]
        btn_hover = game_data["hover"]
        
        state = "normal" if is_available else "disabled"
        btn_text = "JUGAR AHORA" if is_available else "NO INSTALADO"
        if not is_available: 
            btn_color = "#333333"
            btn_hover = "#333333"

        self.play_btn = ctk.CTkButton(
            self, 
            text=btn_text, 
            font=("Arial", 12, "bold"),
            height=35,
            corner_radius=20,
            fg_color=btn_color,
            hover_color=btn_hover,
            state=state,
            command=self.launch
        )
        self.play_btn.pack(pady=(0, 20), padx=20, fill="x")

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        for widget in self.winfo_children():
            if widget != self.play_btn:
                widget.bind("<Enter>", self.on_enter)
                widget.bind("<Leave>", self.on_leave)

    def launch(self):
        self.callback(self.script_path)

    def on_enter(self, event):
        self.configure(border_color=COLOR_ACCENT, fg_color="#1A1A2F")

    def on_leave(self, event):
        self.configure(border_color="#2A2A35", fg_color=COLOR_CARD)


class ArcadeMenu(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GEIIA ARCADE HUB 2026")
        self.geometry("1000x800")
        self.minsize(900, 700)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) 

        self.header = ctk.CTkFrame(self, fg_color="#0F0F15", height=100, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)

        self.title_label = ctk.CTkLabel(
            self.header, 
            text="⚡ GEIIA STUDENT FAIR ⚡", 
            font=("Impact", 36), 
            text_color=COLOR_ACCENT
        )
        self.title_label.place(relx=0.5, rely=0.4, anchor="center")
        
        self.subtitle = ctk.CTkLabel(
            self.header, 
            text="AI ENGINEERING CHALLENGE 2026", 
            font=("Roboto", 14, "bold"), 
            text_color=COLOR_TEXT_DIM
        )
        self.subtitle.place(relx=0.5, rely=0.75, anchor="center")

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        self.scroll_frame.grid_columnconfigure(1, weight=1)

        self.load_games()

        self.footer = ctk.CTkFrame(self, fg_color="#0F0F15", height=50, corner_radius=0)
        self.footer.grid(row=2, column=0, sticky="ew")
        
        ctk.CTkLabel(self.footer, text="Desarrollado por Grupo Estudiantil de IA", text_color="#555566", font=("Arial", 11)).pack(side="left", padx=20, pady=15)
        ctk.CTkButton(self.footer, text="SALIR", width=80, height=25, fg_color="#330000", hover_color="#550000", command=self.destroy).pack(side="right", padx=20)

        self.pulse_val = 0
        self.animate_header()

    def load_games(self):
        games = [
            {
                "name": "🎤 FLAPPY SCREAM",
                "desc": "Usa el volumen de tu voz para controlar la nave. ¡Grita para volar!",
                "script": "game_flappy.py",
                "color": "#E53935", 
                "hover": "#FF5252"
            },
            {
                "name": "🐍 NEURAL SNAKE",
                "desc": "El clásico Snake con superpoderes, combos y una IA rival.",
                "script": "game_snake.py",
                "color": "#43A047",
                "hover": "#66BB6A"
            },
            {
                "name": "😠 FACIAL KOMBAT",
                "desc": "Derrota enemigos imitando las expresiones faciales en pantalla.",
                "script": "game_kombat.py",
                "color": "#FB8C00",
                "hover": "#FFA726"
            },
            {
                "name": "🎹 HUMAN PIANO",
                "desc": "Crea música moviendo tus manos frente a la cámara con visión artificial.",
                "script": "game_piano.py",
                "color": "#8E24AA",
                "hover": "#AB47BC"
            }
        ]

        for i, game in enumerate(games):
            card = GameCard(self.scroll_frame, game, self.launch_game)
            card.grid(row=i//2, column=i%2, padx=15, pady=15, sticky="ew")

    def animate_header(self):
        self.pulse_val += 0.15
        colors = ["#00F0FF", "#50F5FF", "#AAFAFF", "#FFFFFF", "#AAFAFF", "#50F5FF"]
        idx = int(self.pulse_val) % len(colors)
        
        try:
            self.title_label.configure(text_color=colors[idx])
            self.after(100, self.animate_header)
        except:
            pass

    def launch_game(self, script_name):
        full_path = os.path.join(BASE_DIR, script_name)
        if os.path.exists(full_path):
            print(f"Iniciando {script_name}...")
            subprocess.Popen([sys.executable, full_path])
        else:
            print(f"Error: {script_name} no encontrado")

if __name__ == "__main__":
    app = ArcadeMenu()
    app.mainloop()