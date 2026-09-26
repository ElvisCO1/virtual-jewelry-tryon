"""Desktop camera controls and independent visibility of reference marks."""

import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from .app import PreviewSession


class TryOnWindow:
    """Keep all widget updates on Tk's event loop; never run a blocking video loop."""

    def __init__(self, root, config):
        self.root = root
        self.session = PreviewSession(config)
        self._scheduled_frame = None
        self._photo = None
        root.title("Virtual Jewelry Try-On — Pruebas")
        root.geometry("1160x820")
        root.minsize(800, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)

        toolbar = ttk.Frame(root, padding=12)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Probador de anillos", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.start_button = ttk.Button(toolbar, text="Activar cámara", command=self.start)
        self.start_button.pack(side="left", padx=(24, 8))
        self.stop_button = ttk.Button(toolbar, text="Desactivar cámara", command=self.stop, state="disabled")
        self.stop_button.pack(side="left")
        ttk.Button(toolbar, text="Salir", command=self.close).pack(side="right")

        reference_controls = ttk.Frame(root, padding=(12, 0, 12, 8))
        reference_controls.pack(fill="x")
        self.references_button = ttk.Button(
            reference_controls, text="Ocultar referencias", command=self.toggle_references
        )
        self.references_button.pack(side="left")
        ttk.Label(reference_controls, text="Los datos y coordenadas permanecen visibles.").pack(side="left", padx=12)

        self.status = tk.StringVar(value="Cámara desactivada. Pulsa Activar cámara para empezar.")
        ttk.Label(root, textvariable=self.status, padding=(12, 8)).pack(side="bottom", fill="x")
        self.preview = tk.Label(root, bg="#181818", fg="#dddddd", text="Cámara desactivada",
                                font=("Segoe UI", 18))
        self.preview.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        root.bind("<KeyPress-d>", self.print_debug)

    def start(self):
        if self.session.active:
            return
        self.start_button.configure(state="disabled")
        self.status.set("Iniciando cámara y detector…")
        self.root.update_idletasks()
        try:
            self.session.start()
        except (OSError, ValueError, RuntimeError, cv2.error) as error:
            self.stop()
            self.status.set(f"No se pudo iniciar: {error}")
            return
        self.stop_button.configure(state="normal")
        self._update_status()
        self._update_frame()

    def _update_status(self):
        camera_state = "activa" if self.session.active else "desactivada"
        references = "visibles" if self.session.show_references else "ocultas"
        self.status.set(f"Cámara {camera_state} · Referencias {references} · d: datos en la terminal")

    def toggle_references(self):
        self.session.show_references = not self.session.show_references
        self.references_button.configure(
            text="Ocultar referencias" if self.session.show_references else "Mostrar referencias"
        )
        self._update_status()

    def _update_frame(self):
        self._scheduled_frame = None
        if not self.session.active:
            return
        try:
            frame = self.session.read()
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            # Fit the complete camera + measurements panel, preserving aspect ratio.
            image.thumbnail((max(1, self.preview.winfo_width()), max(1, self.preview.winfo_height())))
            self._photo = ImageTk.PhotoImage(image, master=self.root)
            self.preview.configure(image=self._photo, text="")
        except (OSError, ValueError, RuntimeError, cv2.error) as error:
            self.stop()
            self.status.set(f"Cámara detenida: {error}")
            return
        # Return control between frames so buttons and window-close events work.
        self._scheduled_frame = self.root.after(15, self._update_frame)

    def stop(self):
        if self._scheduled_frame is not None:
            self.root.after_cancel(self._scheduled_frame)
            self._scheduled_frame = None
        try:
            self.session.stop()
        finally:
            self.preview.configure(image="", text="Cámara desactivada")
            self._photo = None  # Remove the last frame as soon as the camera stops.
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self._update_status()

    def print_debug(self, event=None):
        if self.session.active:
            self.session.processor.print_debug()

    def close(self):
        try:
            self.stop()
        finally:
            self.root.destroy()


def run_gui(config):
    root = tk.Tk()
    window = TryOnWindow(root, config)
    try:
        root.mainloop()
    finally:
        # Also release resources if mainloop exits through a terminal interrupt.
        window.session.stop()
    return 0
