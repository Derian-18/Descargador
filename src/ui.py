import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from src.downloader import VideoDownloaderSinDuplicados

# --- PALETA DE COLORES ---
BG = "#0f1117"
CARD = "#181b24"
BORDER = "#262b38"
INPUT_BG = "#222633"
TEXT = "#e6e8ef"
MUTED = "#8b92a5"
ACCENT = "#6c5ce7"
ACCENT_HOVER = "#8174f0"
WARN = "#e0a030"
WARN_HOVER = "#f0b84a"
DISABLED = "#3a3f50"
OK = "#2ecc71"
ERR = "#ff6b6b"
INFO = "#74b9ff"

FONT = "Segoe UI"

# Aquí se guarda la carpeta elegida para que se pregunte solo una vez
CONFIG_FILE = Path.home() / ".descargador_config.json"


class BotonModerno(tk.Label):
  """Botón plano con efecto hover (funciona igual en Windows, Linux y macOS)."""

  def __init__(self, parent, text, command, bg, hover, fg="white",
               font=(FONT, 11, "bold"), pady=10):
    super().__init__(parent, text=text, bg=bg, fg=fg, font=font,
                     cursor="hand2", pady=pady)
    self._bg = bg
    self._hover = hover
    self._command = command
    self._activo = True
    self.bind("<Enter>", lambda e: self._activo and self.config(bg=self._hover))
    self.bind("<Leave>", lambda e: self._activo and self.config(bg=self._bg))
    self.bind("<Button-1>", self._click)

  def _click(self, _event):
    if self._activo:
      self._command()

  def set_activo(self, activo):
    self._activo = activo
    if activo:
      self.config(bg=self._bg, cursor="hand2")
    else:
      self.config(bg=DISABLED, cursor="arrow")


class DownloaderApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Descargador de Videos y MP3")
    self.root.geometry("600x740")
    self.root.resizable(False, False)
    self.root.configure(bg=BG)

    ruta_guardada = self.cargar_ruta_guardada()
    self.downloader = VideoDownloaderSinDuplicados(
        download_path=ruta_guardada or "downloads",
        log=self.log, raise_errors=True)

    self.configurar_estilos()
    self.crear_widgets()

    # Primera vez: no hay carpeta guardada, se le pide al usuario
    if ruta_guardada is None:
      self.root.after(300, self.pedir_ruta_inicial)

  # ------------------------------------------------------------------
  # ESTILOS
  # ------------------------------------------------------------------
  def configurar_estilos(self):
    self.style = ttk.Style()
    self.style.theme_use("clam")

    self.style.configure(
        "Dark.TCombobox",
        fieldbackground=INPUT_BG,
        background=INPUT_BG,
        foreground=TEXT,
        arrowcolor=MUTED,
        bordercolor=BORDER,
        lightcolor=INPUT_BG,
        darkcolor=INPUT_BG,
        selectbackground=INPUT_BG,
        selectforeground=TEXT,
        padding=6,
    )
    self.style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", INPUT_BG)],
        foreground=[("readonly", TEXT)],
        bordercolor=[("focus", ACCENT)],
        arrowcolor=[("hover", TEXT)],
    )
    # Lista desplegable del combobox
    self.root.option_add("*TCombobox*Listbox.background", INPUT_BG)
    self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
    self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    self.root.option_add("*TCombobox*Listbox.selectForeground", "white")
    self.root.option_add("*TCombobox*Listbox.font", (FONT, 10))

    self.style.configure(
        "Accent.Horizontal.TProgressbar",
        troughcolor=CARD,
        background=ACCENT,
        bordercolor=CARD,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=6,
    )

    self.style.configure(
        "Dark.Vertical.TScrollbar",
        background=BORDER,
        troughcolor="#12141b",
        bordercolor="#12141b",
        arrowcolor=MUTED,
    )

  # ------------------------------------------------------------------
  # HELPERS DE UI
  # ------------------------------------------------------------------
  def crear_tarjeta(self, titulo):
    """Crea una tarjeta con título y devuelve el frame interior."""
    contenedor = tk.Frame(self.root, bg=BG)
    contenedor.pack(fill="x", padx=24, pady=(0, 14))

    tk.Label(contenedor, text=titulo.upper(), bg=BG, fg=MUTED,
             font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))

    borde = tk.Frame(contenedor, bg=BORDER)
    borde.pack(fill="x")
    interior = tk.Frame(borde, bg=CARD)
    interior.pack(fill="x", padx=1, pady=1)
    return interior

  def crear_entry(self, parent):
    borde = tk.Frame(parent, bg=BORDER)
    entry = tk.Entry(
        borde, font=(FONT, 11), bg=INPUT_BG, fg=TEXT,
        insertbackground=TEXT, relief="flat", bd=0,
        highlightthickness=0,
    )
    entry.pack(fill="x", padx=1, pady=1, ipady=7, ipadx=6)
    entry.bind("<FocusIn>", lambda e: borde.config(bg=ACCENT))
    entry.bind("<FocusOut>", lambda e: borde.config(bg=BORDER))
    return borde, entry

  # ------------------------------------------------------------------
  # COMPONENTES
  # ------------------------------------------------------------------
  def crear_widgets(self):
    # --- Encabezado ---
    header = tk.Frame(self.root, bg=BG)
    header.pack(fill="x", padx=24, pady=(22, 18))

    tk.Label(header, text="🎬  Descargador", bg=BG, fg=TEXT,
             font=(FONT, 20, "bold")).pack(anchor="w")
    tk.Label(header, text="Videos y MP3 de YouTube · sin duplicados",
             bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor="w")

    # --- Tarjeta: URL ---
    card_url = self.crear_tarjeta("Enlace del video")
    fila_url = tk.Frame(card_url, bg=CARD)
    fila_url.pack(fill="x", padx=14, pady=14)

    borde_url, self.url_entry = self.crear_entry(fila_url)
    borde_url.pack(side="left", fill="x", expand=True)

    btn_pegar = BotonModerno(fila_url, "📋 Pegar", self.pegar_url,
                             bg=INPUT_BG, hover=BORDER,
                             font=(FONT, 9, "bold"), pady=8)
    btn_pegar.pack(side="left", padx=(8, 0), ipadx=8)

    # --- Tarjeta: Carpeta de descarga ---
    card_ruta = self.crear_tarjeta("Carpeta de descarga")
    cont_ruta = tk.Frame(card_ruta, bg=CARD)
    cont_ruta.pack(fill="x", padx=14, pady=14)

    self.ruta_label = tk.Label(
        cont_ruta, text=self.ruta_corta(self.downloader.download_path),
        bg=CARD, fg=TEXT, font=(FONT, 10), anchor="w")
    self.ruta_label.pack(fill="x", pady=(0, 10))

    fila_ruta = tk.Frame(cont_ruta, bg=CARD)
    fila_ruta.pack(fill="x")
    fila_ruta.columnconfigure((0, 1), weight=1, uniform="r")

    BotonModerno(
        fila_ruta, "📂 Cambiar carpeta", self.elegir_carpeta,
        bg=INPUT_BG, hover=BORDER, font=(FONT, 9, "bold"), pady=8
    ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

    BotonModerno(
        fila_ruta, "🗂 Abrir carpeta", self.abrir_carpeta,
        bg=INPUT_BG, hover=BORDER, font=(FONT, 9, "bold"), pady=8
    ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    # --- Tarjeta: Configuración ---
    card_cfg = self.crear_tarjeta("Configuración de descarga")
    grid = tk.Frame(card_cfg, bg=CARD)
    grid.pack(fill="x", padx=14, pady=14)
    grid.columnconfigure(1, weight=1)

    # Modo
    tk.Label(grid, text="Modo", bg=CARD, fg=TEXT,
             font=(FONT, 10)).grid(row=0, column=0, sticky="w", pady=7)
    self.modo_combobox = ttk.Combobox(
        grid,
        values=[
            "Video Individual",
            "Audio MP3",
            "Audio MP3 con Portada",
        ],
        state="readonly",
        style="Dark.TCombobox",
        font=(FONT, 10),
    )
    self.modo_combobox.grid(row=0, column=1, sticky="ew", padx=(16, 0), pady=7)
    self.modo_combobox.current(0)
    self.modo_combobox.bind("<<ComboboxSelected>>", self.actualizar_opciones)

    # Calidad
    self.calidad_label = tk.Label(grid, text="Calidad", bg=CARD, fg=TEXT,
                                  font=(FONT, 10))
    self.calidad_label.grid(row=1, column=0, sticky="w", pady=7)
    self.calidad_combobox = ttk.Combobox(
        grid,
        values=["best", "1080p", "720p", "480p", "360p"],
        state="readonly",
        style="Dark.TCombobox",
        font=(FONT, 10),
    )
    self.calidad_combobox.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=7)
    self.calidad_combobox.current(0)


    # --- Botones ---
    frame_botones = tk.Frame(self.root, bg=BG)
    frame_botones.pack(fill="x", padx=24, pady=(0, 10))

    self.btn_descargar = BotonModerno(
        frame_botones, "📥  Iniciar descarga", self.iniciar_hilo_descarga,
        bg=ACCENT, hover=ACCENT_HOVER, font=(FONT, 12, "bold"), pady=12)
    self.btn_descargar.pack(fill="x")

    self.progreso = ttk.Progressbar(
        frame_botones, mode="indeterminate",
        style="Accent.Horizontal.TProgressbar")
    self.progreso.pack(fill="x", pady=(8, 0))

    fila_sec = tk.Frame(frame_botones, bg=BG)
    fila_sec.pack(fill="x", pady=(10, 0))
    fila_sec.columnconfigure((0, 1), weight=1, uniform="a")

    btn_limpiar = BotonModerno(
        fila_sec, "🧹 Limpiar temporales", self.limpiar_temporales,
        bg=WARN, hover=WARN_HOVER, font=(FONT, 9, "bold"), pady=8)
    btn_limpiar.grid(row=0, column=0, sticky="ew", padx=(0, 5))

    btn_borrar_log = BotonModerno(
        fila_sec, "🗑 Borrar consola", self.borrar_consola,
        bg=INPUT_BG, hover=BORDER, font=(FONT, 9, "bold"), pady=8)
    btn_borrar_log.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    # --- Consola ---
    contenedor = tk.Frame(self.root, bg=BG)
    contenedor.pack(fill="both", expand=True, padx=24, pady=(6, 22))

    tk.Label(contenedor, text="ESTADO DEL PROCESO", bg=BG, fg=MUTED,
             font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 4))

    borde = tk.Frame(contenedor, bg=BORDER)
    borde.pack(fill="both", expand=True)
    interior = tk.Frame(borde, bg="#12141b")
    interior.pack(fill="both", expand=True, padx=1, pady=1)

    scroll = ttk.Scrollbar(interior, style="Dark.Vertical.TScrollbar")
    scroll.pack(side="right", fill="y")

    self.consola_text = tk.Text(
        interior, font=("Consolas", 9), bg="#12141b", fg=TEXT,
        relief="flat", bd=0, padx=10, pady=8, wrap="word",
        state="disabled", yscrollcommand=scroll.set,
        highlightthickness=0,
    )
    self.consola_text.pack(side="left", fill="both", expand=True)
    scroll.config(command=self.consola_text.yview)

    self.consola_text.tag_config("hora", foreground=MUTED)
    self.consola_text.tag_config("info", foreground=INFO)
    self.consola_text.tag_config("ok", foreground=OK)
    self.consola_text.tag_config("err", foreground=ERR)
    self.consola_text.tag_config("warn", foreground=WARN_HOVER)

    self.log("Listo. Pega un enlace y elige el modo de descarga.", "info")

  # ------------------------------------------------------------------
  # LÓGICA DE UI
  # ------------------------------------------------------------------
  # ------------------------------------------------------------------
  # CARPETA DE DESCARGA
  # ------------------------------------------------------------------
  def cargar_ruta_guardada(self):
    try:
      datos = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
      ruta = datos.get("ruta_descarga")
      if ruta:
        return Path(ruta)
    except (OSError, ValueError):
      pass
    return None

  def guardar_ruta(self, ruta):
    try:
      CONFIG_FILE.write_text(
          json.dumps({"ruta_descarga": str(ruta)}, ensure_ascii=False),
          encoding="utf-8")
    except OSError as e:
      self.log(f"⚠️ No se pudo guardar la configuración: {e}", "warn")

  def ruta_corta(self, ruta, maximo=52):
    texto = str(Path(ruta).resolve())
    if len(texto) > maximo:
      texto = "…" + texto[-(maximo - 1):]
    return texto

  def aplicar_ruta(self, ruta):
    try:
      self.downloader.set_download_path(ruta)
    except OSError as e:
      messagebox.showerror("Error", f"No se pudo usar esa carpeta: {e}")
      return
    self.guardar_ruta(self.downloader.download_path.resolve())
    self.ruta_label.config(text=self.ruta_corta(self.downloader.download_path))
    self.log(f"📁 Carpeta de descarga: {self.downloader.download_path.resolve()}", "ok")

  def pedir_ruta_inicial(self):
    messagebox.showinfo(
        "Carpeta de descarga",
        "Elige la carpeta donde se guardarán tus descargas.\n"
        "Podrás cambiarla cuando quieras con el botón «Cambiar carpeta».")
    self.elegir_carpeta(primera_vez=True)

  def elegir_carpeta(self, primera_vez=False):
    if not primera_vez and not self.btn_descargar._activo:
      messagebox.showinfo(
          "Descarga en curso",
          "Espera a que termine la descarga para cambiar la carpeta.")
      return

    ruta = filedialog.askdirectory(
        title="Elige la carpeta de descargas",
        initialdir=str(self.downloader.download_path.resolve()))

    if ruta:
      self.aplicar_ruta(Path(ruta))
    elif primera_vez:
      # Canceló: se usa la carpeta por defecto y no se vuelve a preguntar
      self.aplicar_ruta(self.downloader.download_path)

  def abrir_carpeta(self):
    ruta = self.downloader.download_path.resolve()
    try:
      ruta.mkdir(parents=True, exist_ok=True)
      if sys.platform.startswith("win"):
        os.startfile(ruta)
      elif sys.platform == "darwin":
        subprocess.Popen(["open", str(ruta)])
      else:
        subprocess.Popen(["xdg-open", str(ruta)])
    except (OSError, FileNotFoundError) as e:
      messagebox.showerror("Error", f"No se pudo abrir la carpeta: {e}")

  def pegar_url(self):
    try:
      texto = self.root.clipboard_get().strip()
    except tk.TclError:
      return
    self.url_entry.delete(0, tk.END)
    self.url_entry.insert(0, texto)

  def actualizar_opciones(self, event=None):
    """Cambia dinámicamente las opciones de calidad según lo que el usuario elija"""
    modo = self.modo_combobox.get()
    if "MP3" in modo:
      self.calidad_label.config(text="Bitrate (kbps)")
      self.calidad_combobox["values"] = ["320", "256", "192", "128"]
      self.calidad_combobox.current(2)  # 192 kbps por defecto
    else:
      self.calidad_label.config(text="Calidad")
      self.calidad_combobox["values"] = [
          "best", "1080p", "720p", "480p", "360p",
      ]
      self.calidad_combobox.current(0)

  def log(self, mensaje, nivel="info"):
    """Escribe en la consola. Es seguro llamarlo desde otros hilos."""
    self.root.after(0, self._log_ui, mensaje, nivel)

  def _log_ui(self, mensaje, nivel):
    hora = datetime.now().strftime("%H:%M:%S")
    self.consola_text.config(state="normal")
    self.consola_text.insert(tk.END, f"[{hora}] ", "hora")
    self.consola_text.insert(tk.END, mensaje + "\n", nivel)
    self.consola_text.see(tk.END)
    self.consola_text.config(state="disabled")

  def borrar_consola(self):
    self.consola_text.config(state="normal")
    self.consola_text.delete("1.0", tk.END)
    self.consola_text.config(state="disabled")

  def iniciar_hilo_descarga(self):
    """Ejecuta la descarga en un hilo separado para que no se congele la ventana"""
    url = self.url_entry.get().strip()
    if not url:
      messagebox.showerror("Error", "Por favor ingresa una URL válida.")
      return

    self.btn_descargar.set_activo(False)
    self.btn_descargar.config(text="⏳  Descargando...")
    self.progreso.start(12)

    hilo = threading.Thread(target=self.ejecutar_descarga, args=(url,))
    hilo.daemon = True
    hilo.start()

  def ejecutar_descarga(self, url):
    modo = self.modo_combobox.get()
    calidad = self.calidad_combobox.get()

    try:
      self.log(f"🚀 Iniciando proceso: {modo}", "info")

      if modo == "Video Individual":
        self.downloader.descargar_video(url, calidad)
      elif modo == "Audio MP3":
        self.downloader.descargar_audio_mp3(url, calidad)
      elif modo == "Audio MP3 con Portada":
        self.downloader.descargar_con_album_art(url, calidad)

      self.log("✨ ¡Proceso finalizado con éxito!", "ok")
      self.root.after(
          0, lambda: messagebox.showinfo("Completado", "¡La descarga ha finalizado!"))

    except Exception as e:
      self.log(f"❌ Error crítico: {e}", "err")
      self.root.after(
          0, lambda: messagebox.showerror("Error", f"Ocurrió un error: {e}"))

    finally:
      self.root.after(0, self._restaurar_boton)

  def _restaurar_boton(self):
    self.progreso.stop()
    self.btn_descargar.config(text="📥  Iniciar descarga")
    self.btn_descargar.set_activo(True)

  def limpiar_temporales(self):
    self.downloader.limpiar_temporales()
    self.log("🧹 Archivos temporales limpiados.", "ok")
    messagebox.showinfo("Limpieza", "Se han limpiado los archivos temporales.")


def ejecutar_interfaz():
  root = tk.Tk()
  app = DownloaderApp(root)
  root.mainloop()