"""Desktop camera controls and independent visibility of reference marks."""

import tkinter as tk
from math import isfinite
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from .app import PreviewSession
from .ring_catalog import load_catalog
from .samples import SampleBuffer
from .session_store import save_session
from .features import FINGER_WIDTH_ENABLED

FINGER_LABELS = {"Pulgar": "thumb", "Índice": "index", "Medio": "middle",
                 "Anular": "ring", "Meñique": "little"}


class TryOnWindow:
    """Keep all widget updates on Tk's event loop; never run a blocking video loop."""

    def __init__(self, root, config):
        self.root = root
        self.session = PreviewSession(config)
        self._scheduled_frame = None
        self._photo = None
        self._catalog = None
        self._displayed_widths = []
        self._view_index = 0
        self.samples = SampleBuffer()
        self._displayed_snapshot = None
        self._automatic_label = (
            "Sin anillo" if config.geometry_only else
            "Imagen única" if config.ring else "Automático front/back"
        )
        root.title("Virtual Jewelry Try-On — Pruebas")
        root.geometry("1160x820")
        root.minsize(800, 600)
        root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(root)
        style.configure("TButton", padding=(8, 5), font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Capture.TButton", font=("Segoe UI", 10, "bold"))
        root.configure(background="#eef1f5")

        header = ttk.Frame(root, padding=(12, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Probador de anillos", font=("Segoe UI", 15, "bold")).pack(side="left")
        ttk.Button(header, text="Salir", command=self.close).pack(side="right")

        self.control_bar = ttk.Frame(root, padding=(8, 0, 8, 8))
        self.control_bar.pack(fill="x")
        camera = ttk.LabelFrame(self.control_bar, text="Cámara y visualización", padding=10)
        views = ttk.LabelFrame(self.control_bar, text="Vista del anillo", padding=10)
        trial = ttk.LabelFrame(self.control_bar, text="Prueba y captura", padding=10)
        self._control_groups = (camera, views, trial)
        self._control_columns = None

        self.camera_indicator = tk.StringVar(value="● Cámara desactivada")
        ttk.Label(camera, textvariable=self.camera_indicator).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.start_button = ttk.Button(camera, text="Activar", command=self.start)
        self.start_button.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self.stop_button = ttk.Button(camera, text="Desactivar", command=self.stop, state="disabled")
        self.stop_button.grid(row=1, column=1, sticky="ew")
        self.references_button = ttk.Button(camera, text="Ocultar referencias", command=self.toggle_references)
        self.references_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Label(camera, text="Las coordenadas siguen visibles.").grid(row=3, column=0, columnspan=2, sticky="w")
        camera.columnconfigure((0, 1), weight=1)
        self.ring_visible = tk.BooleanVar(value=self.session.show_ring)
        self.ring_toggle = ttk.Checkbutton(camera, text="Mostrar anillo", variable=self.ring_visible,
                                           command=self.toggle_ring)
        self.ring_toggle.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.known_width_mm = tk.StringVar()
        # Retain the experiment without showing controls or running it by default.
        if FINGER_WIDTH_ENABLED:
            ttk.Label(camera, text="Ancho real del dedo (mm):").grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
            ttk.Entry(camera, textvariable=self.known_width_mm, width=8).grid(row=6, column=0, sticky="ew")
            ttk.Button(camera, text="Calibrar mm", command=self.calibrate_width).grid(row=6, column=1, sticky="ew")
            ttk.Button(camera, text="Quitar calibración", command=self.clear_calibration).grid(row=7, column=0, columnspan=2, sticky="ew")
            ttk.Label(camera, text="Mantén distancia y postura al calibrar.", wraplength=240).grid(row=8, column=0, columnspan=2, sticky="w")
        self.manual_width_visible = tk.BooleanVar(value=False)
        self.manual_width_toggle = ttk.Checkbutton(camera, text="Mostrar referencia de ancho",
            variable=self.manual_width_visible, command=self.change_manual_width)
        self.manual_width_toggle.grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.manual_width_value = tk.DoubleVar(value=60)
        self.manual_width_slider = ttk.Scale(camera, from_=10, to=200, variable=self.manual_width_value,
            command=self.change_manual_width)
        self.manual_width_slider.grid(row=10, column=0, columnspan=2, sticky="ew")
        self.manual_width_description = tk.StringVar(value="Ancho manual: 60 % del segmento")
        ttk.Label(camera, textvariable=self.manual_width_description, wraplength=240).grid(
            row=11, column=0, columnspan=2, sticky="w")
        self.mode = tk.StringVar(value=self._automatic_label)
        self.mode_selector = ttk.Combobox(views, textvariable=self.mode, state="readonly", width=24,
                                         values=(self._automatic_label, "Manual — 36 vistas"))
        self.mode_selector.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.mode_selector.bind("<<ComboboxSelected>>", self.change_mode)
        self.previous_button = ttk.Button(views, text="‹ Anterior", state="disabled", command=lambda: self.change_view(-1))
        self.previous_button.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self.next_button = ttk.Button(views, text="Siguiente ›", state="disabled", command=lambda: self.change_view(1))
        self.next_button.grid(row=1, column=1, sticky="ew")
        self.view_description = tk.StringVar(value=f"Modo actual: {self._automatic_label}")
        ttk.Label(views, textvariable=self.view_description, wraplength=285).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        views.columnconfigure((0, 1), weight=1)
        self.finger_name = tk.StringVar(value="Anular")
        self.finger_selector = ttk.Combobox(views, textvariable=self.finger_name,
                                            values=tuple(FINGER_LABELS), state="readonly", width=12)
        self.finger_selector.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        self.finger_selector.bind("<<ComboboxSelected>>", self.change_placement)
        self.reset_position_button = ttk.Button(views, text="Restablecer 50 %", command=self.reset_position)
        self.reset_position_button.grid(row=3, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))
        self.position_value = tk.DoubleVar(value=50)
        self.position_slider = ttk.Scale(views, from_=0, to=100, variable=self.position_value,
                                         command=self.change_placement)
        self.position_slider.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        self.position_description = tk.StringVar(value="Base 13 → articulación 14 · 50 %")
        ttk.Label(views, textvariable=self.position_description).grid(row=5, column=0, columnspan=2, sticky="w")

        self.session_name = tk.StringVar(value="prueba_1")
        ttk.Entry(trial, textvariable=self.session_name, width=20).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.save_button = ttk.Button(trial, text="Guardar JSON", command=self.save_samples)
        self.save_button.grid(row=0, column=1, sticky="ew")
        self.new_session_button = ttk.Button(trial, text="Nueva prueba", command=self.new_sample_session)
        self.new_session_button.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Label(trial, text="Mano a validar").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.capture_hand = tk.StringVar()
        self.hand_selector = ttk.Combobox(trial, textvariable=self.capture_hand, width=12, state="readonly")
        self.hand_selector.grid(row=2, column=0, sticky="ew", padx=(0, 6))
        self.hand_selector.bind("<<ComboboxSelected>>", lambda event: self._refresh_capture())
        self.capture_button = ttk.Button(trial, text="Capturar (adecuada)", style="Capture.TButton", state="disabled", command=self.capture_sample)
        self.capture_button.grid(row=2, column=1, sticky="ew")
        self.discard_button = ttk.Button(trial, text="Descartar última", state="disabled", command=self.discard_sample)
        self.discard_button.grid(row=2, column=2, sticky="ew", padx=(6, 0))
        trial.columnconfigure(0, weight=1)
        self.occlusion_enabled = tk.BooleanVar(value=False)
        self.occlusion_toggle = ttk.Checkbutton(
            trial, text="Aplicar oclusión (experimental)", variable=self.occlusion_enabled,
            command=self.toggle_occlusion)
        self.occlusion_toggle.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Label(trial, text="Oculta parte del aro; no detecta profundidad.", wraplength=380).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.size_value = tk.DoubleVar(value=100)
        self.size_description = tk.StringVar(value="Tamaño del anillo: 100 %")
        ttk.Label(trial, textvariable=self.size_description).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.reset_size_button = ttk.Button(trial, text="Restablecer 100 %", command=self.reset_size)
        self.reset_size_button.grid(row=5, column=2, sticky="ew", padx=(6, 0), pady=(8, 0))
        self.size_slider = ttk.Scale(trial, from_=50, to=200, variable=self.size_value,
                                     command=self.change_size)
        self.size_slider.grid(row=6, column=0, columnspan=3, sticky="ew", pady=4)
        self._session_number = 1
        self.control_bar.bind("<Configure>", self._layout_controls)

        footer = ttk.Frame(root, padding=(12, 6))
        footer.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="Cámara desactivada. Pulsa Activar para empezar.")
        self.sample_status = tk.StringVar(value="0 muestras · Guarda la prueba en JSON. Sin fotos.")
        self._status_label = ttk.Label(footer, textvariable=self.status)
        self._status_label.pack(anchor="w", fill="x")
        self._sample_label = ttk.Label(footer, textvariable=self.sample_status)
        self._sample_label.pack(anchor="w", fill="x", pady=(4, 0))
        footer.bind("<Configure>", lambda event: [label.configure(wraplength=max(200, event.width - 24))
                                                  for label in (self._status_label, self._sample_label)])
        self.preview = tk.Label(root, bg="#181818", fg="#dddddd", text="Cámara desactivada",
                                font=("Segoe UI", 18))
        self.preview.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        root.bind("<KeyPress-d>", self.print_debug)

    def _layout_controls(self, event):
        # Reflow whole groups, not individual buttons; keep the preview expandable.
        required = sum(group.winfo_reqwidth() + 8 for group in self._control_groups) + 16
        columns = 3 if event.width >= required else 2
        if columns == self._control_columns:
            return
        self._control_columns = columns
        for column in range(3):
            self.control_bar.columnconfigure(column, weight=1 if column < columns else 0)
        for index, group in enumerate(self._control_groups):
            group.grid_forget()
            group.grid(row=index // columns, column=index % columns,
                       columnspan=2 if columns == 2 and index == 2 else 1,
                       sticky="nsew", padx=4, pady=4)

    def change_placement(self, event=None):
        self._displayed_widths = []
        self.session.calibration = None
        from .geometry import FINGER_INDICES

        self.session.finger = FINGER_LABELS[self.finger_name.get()]
        self.session.position = self.position_value.get() / 100
        indices = FINGER_INDICES[self.session.finger]
        self.position_description.set(
            f"Base {indices[0]} → articulación {indices[1]} · {self.position_value.get():.0f} %")
        self._displayed_snapshot = None
        self._refresh_capture()

    def calibrate_width(self):
        try:
            mm = float(self.known_width_mm.get().replace(',', '.'))
            if not isfinite(mm) or mm <= 0:
                raise ValueError('Introduce un ancho real positivo en mm.')
            if not self.session.active or len(self._displayed_widths) != 1:
                raise ValueError('Muestra una sola mano con bordes de dedo detectables.')
            sample = self._displayed_widths[0]
            self.session.calibration = {
                'context': sample['context'], 'reference_width_mm': mm,
                'reference_width_px': sample['measurement']['width_px'],
                'mm_per_pixel': mm / sample['measurement']['width_px'],
            }
            self._displayed_snapshot = None
            self._refresh_capture()
            self._sample_feedback('mm aproximados: recalibra si cambia la distancia o postura')
        except ValueError as error:
            self._sample_feedback(str(error))

    def clear_calibration(self):
        self.session.calibration = None
        self._displayed_snapshot = None
        self._refresh_capture()
        self._sample_feedback('Milímetros sin calibrar')

    def reset_position(self):
        self.position_value.set(50)
        self.change_placement()

    def change_mode(self, event=None):
        if self.mode.get() != self._automatic_label:
            try:
                if self._catalog is None:
                    self._catalog = load_catalog()
            except (OSError, ValueError, KeyError, TypeError, cv2.error) as error:
                self.mode.set(self._automatic_label)
                self.session.manual_view = None
                self._refresh_view_controls()
                self.status.set(f"No se pudo cargar el catálogo: {error}")
                return
            self.session.manual_view = self._catalog[self._view_index]
        else:
            self.session.manual_view = None
        self._refresh_view_controls()

    def change_view(self, step):
        if self.session.manual_view is None:
            return
        self._view_index = (self._view_index + step) % len(self._catalog)
        self.session.manual_view = self._catalog[self._view_index]
        self._refresh_view_controls()

    def _refresh_view_controls(self):
        self._displayed_snapshot = None
        self._refresh_capture()
        view = self.session.manual_view
        state = "normal" if view is not None else "disabled"
        self.previous_button.configure(state=state)
        self.next_button.configure(state=state)
        if view is None:
            self.view_description.set(f"Modo actual: {self._automatic_label}")
        else:
            self.view_description.set(
                f"{self._view_index + 1} de {len(self._catalog)} · {view.filename}\n"
                f"Giro {view.azimuth:03d}° · Inclinación {view.elevation:+d}° (aproximados)"
            )

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

    def _refresh_capture(self):
        snapshot = self._displayed_snapshot if self.session.active and self.session.show_ring else None
        names = {"Right": "Derecha", "Left": "Izquierda"}
        available = [names[h['handedness']] for h in snapshot['hands'] if h['eligible']] if snapshot else []
        self.hand_selector.configure(values=available)
        if self.capture_hand.get() not in available:
            self.capture_hand.set(available[0] if len(available) == 1 else "")
        self.capture_button.configure(state="normal" if self.capture_hand.get() in available else "disabled")

    def capture_sample(self):
        if not self.session.active:
            return
        if not self.session.show_ring:
            self._sample_feedback("Muestra el anillo para validar su ajuste")
            return
        try:
            hand = {"Derecha": "Right", "Izquierda": "Left"}.get(self.capture_hand.get())
            sample = self.samples.capture(self._displayed_snapshot, hand)
            self._sample_feedback(f"Capturada: {sample['image']['filename']} ({self.capture_hand.get()})")
        except ValueError as error:
            self._sample_feedback(str(error))

    def discard_sample(self):
        try:
            self.samples.discard_last()
            self._sample_feedback("Última muestra marcada como descartada")
        except ValueError as error:
            self._sample_feedback(str(error))

    def _sample_feedback(self, message):
        pending = self.samples.dirty or (bool(self.samples.samples) and self.samples.saved_name != self.session_name.get().strip())
        state = "Cambios pendientes de guardar" if pending else "Sin cambios pendientes"
        self.sample_status.set(f"{self.samples.valid_count} válidas · {message}\n{state}. Sin fotos.")
        self.discard_button.configure(state="normal" if self.samples.valid_count else "disabled")

    def save_samples(self):
        try:
            path = save_session(self.samples, self.session_name.get())
        except (OSError, ValueError, TypeError) as error:
            self._sample_feedback(f"No se pudo guardar: {error}")
            return False
        self._sample_feedback(f"Guardada en data/sessions/{path.name}")
        return True

    def _save_pending(self):
        pending = self.samples.dirty or (bool(self.samples.samples) and self.samples.saved_name != self.session_name.get().strip())
        return not pending or self.save_samples()

    def new_sample_session(self):
        # Preserve evidence before replacing the buffer; a failed save cancels reset.
        if not self._save_pending():
            return
        self.samples = SampleBuffer()
        self._session_number += 1
        self.session_name.set(f"prueba_{self._session_number}")
        self._displayed_snapshot = None
        self._refresh_capture()
        self._sample_feedback("Nueva prueba iniciada")

    def _update_status(self):
        camera_state = "activa" if self.session.active else "desactivada"
        self.camera_indicator.set(f"● Cámara {camera_state}")
        references = "visibles" if self.session.show_references else "ocultas"
        ring = "habilitado" if self.session.show_ring else "oculto · Captura deshabilitada"
        self.status.set(f"Cámara {camera_state} · Anillo {ring} · Referencias {references} · d: datos en la terminal")

    def change_manual_width(self, event=None):
        self.session.show_manual_width = self.manual_width_visible.get()
        self.session.manual_width_ratio = self.manual_width_value.get() / 100
        self.manual_width_description.set(f"Ancho manual: {self.manual_width_value.get():.0f} % del segmento")
        self._displayed_snapshot = None
        self._refresh_capture()

    def change_size(self, event=None):
        self.session.size_factor = self.size_value.get() / 100
        self.size_description.set(f"Tamaño del anillo: {self.size_value.get():.0f} %")
        self._displayed_snapshot = None
        self._refresh_capture()

    def reset_size(self):
        self.size_value.set(100)
        self.change_size()

    def toggle_occlusion(self):
        self.session.occlusion = self.occlusion_enabled.get()
        self._displayed_snapshot = None
        self._refresh_capture()
        self._sample_feedback("Oclusión experimental activada" if self.session.occlusion else "Oclusión desactivada")

    def toggle_ring(self):
        self.session.show_ring = self.ring_visible.get()
        # A visibility change needs a new displayed frame before validation.
        self._displayed_snapshot = None
        self._refresh_capture()
        self._update_status()

    def toggle_references(self):
        self._displayed_snapshot = None
        self._refresh_capture()
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
            # Only promote data after successfully presenting its corresponding frame.
            self._displayed_snapshot = self.session.last_snapshot
            self._displayed_widths = getattr(self.session, 'last_widths', [])
            self._refresh_capture()
        except (OSError, ValueError, RuntimeError, cv2.error) as error:
            self.stop()
            self.status.set(f"Cámara detenida: {error}")
            return
        # Return control between frames so buttons and window-close events work.
        self._scheduled_frame = self.root.after(15, self._update_frame)

    def stop(self):
        self._displayed_widths = []
        if self._scheduled_frame is not None:
            self.root.after_cancel(self._scheduled_frame)
            self._scheduled_frame = None
        try:
            self.session.stop()
        finally:
            self._displayed_snapshot = None
            self._refresh_capture()
            self.preview.configure(image="", text="Cámara desactivada")
            self._photo = None  # Remove the last frame as soon as the camera stops.
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self._update_status()

    def print_debug(self, event=None):
        if self.session.active:
            self.session.processor.print_debug()

    def close(self):
        if not self._save_pending():
            return
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
