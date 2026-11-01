"""
main.py - Aplicación Principal 'Editor y Procesador de Video Pro'.
Arquitectura profesional inspirada en CapCut con interfaz gráfica moderna en modo oscuro,
renderizado concurrente con MoviePy 2.x, Pillow, CustomTkinter, proglog y psutil.
"""

import os
import sys
import time
import queue
import threading
import subprocess
from tkinter import filedialog, messagebox
import psutil
import customtkinter as ctk
from PIL import Image

# Importaciones locales
from editor_core import MediaAsset, TimelineModel, CompositorEngine
from export_worker import ExportWorker
from ui_components import (
    THEME,
    PreviewMonitorWidget,
    TimelineView,
    ConcatDialog,
    ExportDialog,
    ConsoleWidget
)
import demo_generator

# Configuración inicial de CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


class VideoEditorProApp(ctk.CTk):
    """
    Ventana y controlador principal de la aplicación Video Editor Pro.
    Orquesta la interfaz gráfica, el modelo de datos, la previsualización a 60 FPS
    y el hilo secundario de renderizado con cancelación segura.
    """
    def __init__(self):
        super().__init__()

        self.title("🎬 Editor y Procesador de Video Pro - CapCut Dark Architecture")
        self.geometry("1440x920")
        self.minsize(1180, 780)
        self.configure(fg_color=THEME['bg_dark'])

        # Modelo y Estado
        self.model = TimelineModel()
        self.imported_assets: list[MediaAsset] = []
        self.current_time: float = 0.0
        self.is_playing: bool = False
        self.selected_aspect: str = "16:9"

        # Concurrencia de Exportación
        self.event_queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.active_export_worker: ExportWorker | None = None

        # Caché de Miniaturas Tkinter para evitar recolección de basura
        self._thumb_cache: dict = {}

        # Construcción de la Interfaz
        self._build_header()
        self._build_main_layout()

        # Iniciar bucles de eventos y refresco a 60 FPS
        self._poll_event_queue()
        self._update_system_stats()

        # Atajos de Teclado
        self.bind("<space>", lambda e: self._toggle_play_pause())
        self.bind("<Delete>", lambda e: self._on_timeline_delete())
        self.bind("<Left>", lambda e: self._on_monitor_step(-1.0))
        self.bind("<Right>", lambda e: self._on_monitor_step(1.0))
        self.bind("<Control-e>", lambda e: self._open_export_modal())
        self.bind("<Control-E>", lambda e: self._open_export_modal())

        # Mensaje de bienvenida en consola
        self.console.append_log("INFO", "Iniciando Editor y Procesador de Video Pro [v2.5 CapCut Architecture].")
        self.console.append_log("INFO", "Motor MoviePy 2.x, Pillow y FFmpeg listos para procesamiento concurrente.")
        self.console.append_log("INFO", "Presiona '⚡ Generar Clips Demo' para cargar medios de prueba de inmediato.")

    def _build_header(self):
        """Barra superior con identidad visual, monitor de recursos y botón de exportar."""
        header = ctk.CTkFrame(self, fg_color=THEME['panel_bg'], height=52, corner_radius=0)
        header.pack(fill="x", side="top", padx=0, pady=(0, 4))

        # Logo y Título
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=16, pady=8)

        lbl_logo = ctk.CTkLabel(
            brand_frame,
            text="🎬 CAPCUT PRO",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        lbl_logo.pack(side="left")

        lbl_tag = ctk.CTkLabel(
            brand_frame,
            text="STUDIO",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#000000",
            fg_color=THEME['accent_cyan'],
            corner_radius=4,
            width=50,
            height=18
        )
        lbl_tag.pack(side="left", padx=(8, 0))

        # Monitor de Recursos de Sistema en Vivo
        self.stats_pill = ctk.CTkLabel(
            header,
            text="⚡ CPU: --% | RAM: --%",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#9E9EA8",
            fg_color="#141418",
            corner_radius=6,
            padx=10,
            pady=3
        )
        self.stats_pill.pack(side="left", padx=20)

        # Acciones Rápidas
        actions_frame = ctk.CTkFrame(header, fg_color="transparent")
        actions_frame.pack(side="right", padx=16, pady=8)

        btn_demo = ctk.CTkButton(
            actions_frame,
            text="⚡ Generar Clips Demo",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E2E38",
            hover_color="#3C3C4A",
            height=32,
            command=self._generate_and_load_demo
        )
        btn_demo.pack(side="left", padx=6)

        btn_import = ctk.CTkButton(
            actions_frame,
            text="📥 Importar Medios",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E2E38",
            hover_color="#3C3C4A",
            height=32,
            command=self._import_media_files
        )
        btn_import.pack(side="left", padx=6)

        self.btn_export_main = ctk.CTkButton(
            actions_frame,
            text="🚀 Exportar Video",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=THEME['accent_cyan'],
            text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            height=32,
            command=self._open_export_modal
        )
        self.btn_export_main.pack(side="left", padx=6)

    def _build_main_layout(self):
        """Distribución de los 4 paneles principales."""
        # Contenedor Vertical Global
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=8, pady=4)

        # Zona Superior: Panel 1 (Medios e Insumos) y Panel 2 (Monitor de Previsualización)
        top_zone = ctk.CTkFrame(content, fg_color="transparent")
        top_zone.pack(fill="both", expand=True, pady=(0, 6))

        # Panel 1: Medios e Insumos (Izquierda, ancho fijo ~410px)
        self.panel1_tabs = self._build_panel_1_tabs(top_zone)
        self.panel1_tabs.pack(side="left", fill="both", padx=(0, 6))

        # Panel 2: Monitor de Previsualización (Derecha, flexible)
        self.monitor = PreviewMonitorWidget(
            top_zone,
            on_play_pause=self._toggle_play_pause,
            on_seek=self._on_monitor_seek,
            on_step=self._on_monitor_step,
            on_aspect_change=self._on_aspect_change
        )
        self.monitor.pack(side="left", fill="both", expand=True)

        # Zona Inferior: Panel 3 (Timeline) y Panel 4 (Consola y Exportación)
        # Panel 3: Línea de Tiempo / Timeline
        self.timeline = TimelineView(
            content,
            model=self.model,
            on_clip_selected=self._on_clip_selected,
            on_split=self._on_timeline_split,
            on_delete=self._on_timeline_delete,
            on_speed=self._on_timeline_speed,
            on_reorder=self._on_timeline_reorder,
            on_open_concat=self._on_open_concat_modal,
            on_clear=self._on_timeline_clear,
            height=200
        )
        self.timeline.pack(fill="x", pady=(0, 6))

        # Panel 4: Consola y Panel de Exportación (Zona inferior extrema)
        self._build_panel_4_export_console(content)

    def _build_panel_1_tabs(self, parent) -> ctk.CTkTabview:
        """Construye las pestañas de Medios, Texto y Filtros/Ajustes."""
        tabview = ctk.CTkTabview(
            parent,
            fg_color=THEME['panel_bg'],
            segmented_button_selected_color=THEME['accent_cyan'],
            segmented_button_selected_hover_color=THEME['accent_cyan_hover'],
            text_color="#FFFFFF",
            width=430
        )

        tabview.add("Mis Medios")
        tabview.add("Texto / Superposición")
        tabview.add("Filtros / Ajustes")

        # 1. Pestaña: Mis Medios
        self._setup_tab_media(tabview.tab("Mis Medios"))

        # 2. Pestaña: Texto / Superposición
        self._setup_tab_overlay(tabview.tab("Texto / Superposición"))

        # 3. Pestaña: Filtros / Ajustes
        self._setup_tab_filters(tabview.tab("Filtros / Ajustes"))

        return tabview

    def _setup_tab_media(self, tab):
        """Controles para importar y gestionar medios."""
        btn_bar = ctk.CTkFrame(tab, fg_color="transparent")
        btn_bar.pack(fill="x", pady=(4, 6))

        btn_add = ctk.CTkButton(
            btn_bar,
            text="➕ Importar Archivos",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME['accent_cyan'],
            text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            command=self._import_media_files
        )
        btn_add.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Filtro de tipo de medio
        self.media_filter_var = ctk.StringVar(value="Todos")
        filter_seg = ctk.CTkSegmentedButton(
            tab,
            values=["Todos", "Videos", "Audios", "Imágenes"],
            variable=self.media_filter_var,
            command=lambda v: self._refresh_media_list(),
            selected_color="#2E2E38",
            selected_hover_color="#3C3C4A",
            font=ctk.CTkFont(family="Segoe UI", size=10)
        )
        filter_seg.pack(fill="x", pady=(0, 6))

        # Lista deslizable de medios
        self.media_scroll = ctk.CTkScrollableFrame(
            tab,
            fg_color="#141418",
            corner_radius=6
        )
        self.media_scroll.pack(fill="both", expand=True, pady=4)

        self._refresh_media_list()

    def _setup_tab_overlay(self, tab):
        """Controles para generar títulos, subtítulos y marcas de agua."""
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self._add_label(scroll, "Texto Personalizado:")
        self.overlay_text_entry = ctk.CTkEntry(scroll, placeholder_text="Escribe tu título o subtítulo...")
        self.overlay_text_entry.insert(0, "Subtítulo CapCut Pro")
        self.overlay_text_entry.pack(fill="x", pady=(0, 8))

        self._add_label(scroll, "Tamaño de Fuente (px):")
        self.overlay_size_slider = ctk.CTkSlider(scroll, from_=16, to=72, number_of_steps=28)
        self.overlay_size_slider.set(36)
        self.overlay_size_slider.pack(fill="x", pady=(0, 8))

        self._add_label(scroll, "Color de Texto:")
        self.overlay_color_menu = ctk.CTkOptionMenu(
            scroll,
            values=["#FFFFFF (Blanco)", "#00D2C4 (Cian)", "#FFEB3B (Amarillo)", "#FF4D4D (Rojo)", "#00E676 (Verde)", "#000000 (Negro)"],
            fg_color="#2A2A34"
        )
        self.overlay_color_menu.set("#FFFFFF (Blanco)")
        self.overlay_color_menu.pack(fill="x", pady=(0, 8))

        self._add_label(scroll, "Posición en Pantalla:")
        self.overlay_pos_menu = ctk.CTkOptionMenu(
            scroll,
            values=[
                "Inferior (Subtítulo estándar)",
                "Centro de Pantalla",
                "Superior (Encabezado)",
                "Marca de Agua (Esquina Sup. Der)",
                "Marca de Agua (Esquina Inf. Der)"
            ],
            fg_color="#2A2A34"
        )
        self.overlay_pos_menu.set("Inferior (Subtítulo estándar)")
        self.overlay_pos_menu.pack(fill="x", pady=(0, 8))

        self._add_label(scroll, "Estilo de Fondo:")
        self.overlay_bg_seg = ctk.CTkSegmentedButton(
            scroll,
            values=["Caja Translúcida", "Sin Fondo"],
            selected_color=THEME['accent_purple']
        )
        self.overlay_bg_seg.set("Caja Translúcida")
        self.overlay_bg_seg.pack(fill="x", pady=(0, 8))

        self._add_label(scroll, "Opacidad (Transparencia):")
        self.overlay_opacity_slider = ctk.CTkSlider(scroll, from_=0.2, to=1.0)
        self.overlay_opacity_slider.set(0.95)
        self.overlay_opacity_slider.pack(fill="x", pady=(0, 8))

        time_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        time_frame.pack(fill="x", pady=(0, 10))

        sub_t1 = ctk.CTkFrame(time_frame, fg_color="transparent")
        sub_t1.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._add_label(sub_t1, "Inicio (s):")
        self.overlay_start_entry = ctk.CTkEntry(sub_t1)
        self.overlay_start_entry.insert(0, "0.0")
        self.overlay_start_entry.pack(fill="x")

        sub_t2 = ctk.CTkFrame(time_frame, fg_color="transparent")
        sub_t2.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self._add_label(sub_t2, "Duración (s):")
        self.overlay_dur_entry = ctk.CTkEntry(sub_t2)
        self.overlay_dur_entry.insert(0, "4.0")
        self.overlay_dur_entry.pack(fill="x")

        btn_add_overlay = ctk.CTkButton(
            scroll,
            text="➕ Añadir a Pista de Superposición",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=THEME['accent_purple'],
            hover_color=THEME['accent_purple_hover'],
            height=32,
            command=self._add_overlay_clip
        )
        btn_add_overlay.pack(fill="x", pady=(6, 10))

    def _setup_tab_filters(self, tab):
        """Controles para ajustar brillo, contraste, saturación, efectos y volumen del clip seleccionado."""
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        self.filter_clip_info_lbl = ctk.CTkLabel(
            scroll,
            text="Selecciona un clip en la línea de tiempo para ajustar",
            font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
            text_color=THEME['text_secondary']
        )
        self.filter_clip_info_lbl.pack(anchor="w", pady=(2, 8))

        # Brillo
        self._add_label(scroll, "Brillo (-50% a +50%):")
        self.slider_bright = ctk.CTkSlider(scroll, from_=-0.5, to=0.5, command=lambda v: self._apply_filters_to_selected(preview_only=True))
        self.slider_bright.set(0.0)
        self.slider_bright.pack(fill="x", pady=(0, 8))

        # Contraste
        self._add_label(scroll, "Contraste (0.5x a 2.0x):")
        self.slider_contrast = ctk.CTkSlider(scroll, from_=0.5, to=2.0, command=lambda v: self._apply_filters_to_selected(preview_only=True))
        self.slider_contrast.set(1.0)
        self.slider_contrast.pack(fill="x", pady=(0, 8))

        # Saturación
        self._add_label(scroll, "Saturación (0.0 a 2.0x):")
        self.slider_saturation = ctk.CTkSlider(scroll, from_=0.0, to=2.0, command=lambda v: self._apply_filters_to_selected(preview_only=True))
        self.slider_saturation.set(1.0)
        self.slider_saturation.pack(fill="x", pady=(0, 8))

        # Preset de Efecto
        self._add_label(scroll, "Filtro de Color / Estilo:")
        self.filter_preset_seg = ctk.CTkSegmentedButton(
            scroll,
            values=["Normal", "B&W", "Sepia", "Invertir"],
            command=lambda v: self._apply_filters_to_selected(preview_only=True),
            selected_color=THEME['accent_cyan'],
            selected_hover_color=THEME['accent_cyan_hover']
        )
        self.filter_preset_seg.set("Normal")
        self.filter_preset_seg.pack(fill="x", pady=(0, 8))

        # Transformaciones
        self._add_label(scroll, "Geometría:")
        geo_box = ctk.CTkFrame(scroll, fg_color="transparent")
        geo_box.pack(fill="x", pady=(0, 8))

        self.check_flip_h = ctk.CTkCheckBox(
            geo_box,
            text="Espejo Horizontal (Flip)",
            command=lambda: self._apply_filters_to_selected(preview_only=True)
        )
        self.check_flip_h.pack(side="left", padx=(0, 10))

        self.rot_menu = ctk.CTkOptionMenu(
            geo_box,
            values=["0° Rotación", "90° Rotación", "180° Rotación", "270° Rotación"],
            width=120,
            command=lambda v: self._apply_filters_to_selected(preview_only=True)
        )
        self.rot_menu.set("0° Rotación")
        self.rot_menu.pack(side="right")

        # Audio del Clip
        self._add_label(scroll, "Pista de Audio del Clip:")
        audio_box = ctk.CTkFrame(scroll, fg_color="transparent")
        audio_box.pack(fill="x", pady=(0, 8))

        self.check_mute = ctk.CTkCheckBox(
            audio_box,
            text="Silenciar Clip",
            command=lambda: self._apply_filters_to_selected(preview_only=True)
        )
        self.check_mute.pack(side="left")

        self.slider_volume = ctk.CTkSlider(scroll, from_=0.0, to=2.0)
        self.slider_volume.set(1.0)
        self.slider_volume.pack(fill="x", pady=(0, 10))

        # Botones Aplicar / Reset
        btn_action_box = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_action_box.pack(fill="x", pady=(6, 12))

        btn_save_filter = ctk.CTkButton(
            btn_action_box,
            text="💾 Guardar Cambios en Clip",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME['accent_cyan'],
            text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            command=lambda: self._apply_filters_to_selected(preview_only=False)
        )
        btn_save_filter.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_reset_filter = ctk.CTkButton(
            btn_action_box,
            text="🔄 Restablecer",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#2E2E38",
            hover_color="#3C3C4A",
            width=85,
            command=self._reset_filters_form
        )
        btn_reset_filter.pack(side="right")

    def _build_panel_4_export_console(self, parent):
        """Zona inferior extrema: Barra de progreso, porcentaje en vivo, consola y botón cancelar."""
        panel4 = ctk.CTkFrame(parent, fg_color=THEME['panel_bg'], corner_radius=10, border_width=1, border_color=THEME['panel_border'])
        panel4.pack(fill="x", side="bottom")

        # Barra de Estado y Progreso de Renderizado
        status_bar = ctk.CTkFrame(panel4, fg_color="transparent")
        status_bar.pack(fill="x", padx=12, pady=(8, 4))

        self.lbl_status = ctk.CTkLabel(
            status_bar,
            text="🟢 Estado: Listo para procesar y editar",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME['accent_green']
        )
        self.lbl_status.pack(side="left")

        self.lbl_progress_num = ctk.CTkLabel(
            status_bar,
            text="0.0% | Cuadro 0/0 | FPS: 0.0 | Restante: --:--",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=THEME['text_secondary']
        )
        self.lbl_progress_num.pack(side="left", padx=20)

        # Botón Cancelar Exportación (Destacado en rojo con threading.Event)
        self.btn_cancel_export = ctk.CTkButton(
            status_bar,
            text="🛑 Cancelar Exportación",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME['accent_red'],
            hover_color=THEME['accent_red_hover'],
            state="disabled",
            command=self._cancel_export_process
        )
        self.btn_cancel_export.pack(side="right")

        # Barra de progreso moderna
        self.progress_bar = ctk.CTkProgressBar(
            panel4,
            progress_color=THEME['accent_cyan'],
            height=10,
            corner_radius=4
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=12, pady=(2, 6))

        # Consola de Registros Monospace Integrada
        self.console = ConsoleWidget(panel4, height=110)
        self.console.pack(fill="x", padx=4, pady=(2, 6))

    def _add_label(self, parent, text: str):
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#B8B8C4"
        )
        lbl.pack(anchor="w", pady=(4, 2))

    # =========================================================================
    # GESTIÓN DE MEDIOS E INSUMOS
    # =========================================================================

    def _import_media_files(self):
        """Abre el diálogo para seleccionar archivos multimedia."""
        filetypes = [
            ("Archivos Multimedia", "*.mp4 *.mov *.avi *.mkv *.webm *.mp3 *.wav *.aac *.m4a *.png *.jpg *.jpeg *.webp"),
            ("Videos", "*.mp4 *.mov *.avi *.mkv *.webm"),
            ("Audios", "*.mp3 *.wav *.aac *.m4a"),
            ("Imágenes", "*.png *.jpg *.jpeg *.webp"),
            ("Todos los archivos", "*.*")
        ]
        paths = filedialog.askopenfilenames(title="Importar Medios a CapCut Pro", filetypes=filetypes)
        if not paths:
            return

        for p in paths:
            try:
                asset = MediaAsset(p)
                self.imported_assets.append(asset)
                self.console.append_log("INFO", f"Medio importado: {asset.filename} ({asset.media_type.upper()}) - Duración: {asset.duration:.2f}s")
            except Exception as e:
                self.console.append_log("ERROR", f"Error importando {p}: {e}")

        self._refresh_media_list()

    def _generate_and_load_demo(self):
        """Genera clips sintetizados y los carga automáticamente en la app."""
        self.console.append_log("INFO", "Sintetizando medios de demostración (videos neon, animaciones y música)...")
        self.lbl_status.configure(text="⚡ Sintetizando medios de demostración...", text_color=THEME['accent_cyan'])

        def _worker():
            try:
                demo_paths = demo_generator.ensure_demo_media("demo_assets")
                for key, p in demo_paths.items():
                    asset = MediaAsset(p)
                    self.imported_assets.append(asset)
                self.event_queue.put({'type': 'demo_ready'})
            except Exception as e:
                self.event_queue.put({'type': 'log', 'level': 'ERROR', 'message': f"Fallo al generar demo: {e}"})

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_media_list(self):
        """Actualiza la cuadrícula de medios en la pestaña 'Mis Medios'."""
        for w in self.media_scroll.winfo_children():
            w.destroy()

        filter_choice = self.media_filter_var.get()

        filtered = []
        for a in self.imported_assets:
            if filter_choice == "Todos":
                filtered.append(a)
            elif filter_choice == "Videos" and a.media_type == "video":
                filtered.append(a)
            elif filter_choice == "Audios" and a.media_type == "audio":
                filtered.append(a)
            elif filter_choice == "Imágenes" and a.media_type == "image":
                filtered.append(a)

        if not filtered:
            lbl = ctk.CTkLabel(
                self.media_scroll,
                text="No hay medios en esta categoría.\nHaz clic en 'Importar Archivos' o 'Generar Clips Demo'.",
                font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
                text_color="#707080"
            )
            lbl.pack(pady=30)
            return

        for asset in filtered:
            card = ctk.CTkFrame(self.media_scroll, fg_color="#1D1D24", corner_radius=6, border_width=1, border_color="#282834")
            card.pack(fill="x", pady=3, padx=2)

            # Miniatura
            if asset.thumbnail:
                ctk_img = ctk.CTkImage(light_image=asset.thumbnail, dark_image=asset.thumbnail, size=(75, 45))
                self._thumb_cache[asset.asset_id] = ctk_img
                thumb_lbl = ctk.CTkLabel(card, image=ctk_img, text="")
                thumb_lbl.pack(side="left", padx=6, pady=4)

            # Información
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="x", expand=True, padx=4)

            fname = asset.filename if len(asset.filename) <= 20 else asset.filename[:18] + ".."
            lbl_name = ctk.CTkLabel(info_frame, text=fname, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), anchor="w")
            lbl_name.pack(anchor="w")

            det = f"{asset.media_type.upper()} | {asset.duration:.1f}s"
            if asset.resolution != (0, 0):
                det += f" | {asset.resolution[0]}x{asset.resolution[1]}"
            lbl_det = ctk.CTkLabel(info_frame, text=det, font=ctk.CTkFont(family="Segoe UI", size=9), text_color="#8E8E9E", anchor="w")
            lbl_det.pack(anchor="w")

            # Botón añadir a Timeline
            btn_add = ctk.CTkButton(
                card,
                text="+ Timeline",
                width=72,
                height=26,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=THEME['accent_cyan'],
                text_color="#000000",
                hover_color=THEME['accent_cyan_hover'],
                command=lambda a=asset: self._add_asset_to_timeline(a)
            )
            btn_add.pack(side="right", padx=6)

    def _add_asset_to_timeline(self, asset: MediaAsset):
        """Añade un medio a la pista adecuada y refresca la UI."""
        clip = self.model.add_clip(asset)
        self.console.append_log("INFO", f"Clip añadido a línea de tiempo: '{clip.name}' (Inicio: {clip.start_time:.2f}s, Duración: {clip.duration:.2f}s)")
        self.timeline.render_tracks()
        self._sync_preview_at(self.current_time)

    def _add_overlay_clip(self):
        """Añade un título / superposición a la pista de overlay."""
        txt = self.overlay_text_entry.get().strip()
        if not txt:
            messagebox.showwarning("Texto requerido", "Por favor introduce un texto para la superposición.")
            return

        font_size = int(self.overlay_size_slider.get())
        color_str = self.overlay_color_menu.get().split()[0]
        pos_raw = self.overlay_pos_menu.get()
        pos_preset = "bottom"
        if "Centro" in pos_raw:
            pos_preset = "center"
        elif "Superior" in pos_raw:
            pos_preset = "top"
        elif "Sup. Der" in pos_raw:
            pos_preset = "watermark_tr"
        elif "Inf. Der" in pos_raw:
            pos_preset = "watermark_br"

        bg_style = "box" if "Caja" in self.overlay_bg_seg.get() else "none"
        opacity = float(self.overlay_opacity_slider.get())

        try:
            start_t = float(self.overlay_start_entry.get())
            dur = float(self.overlay_dur_entry.get())
        except ValueError:
            start_t, dur = 0.0, 4.0

        clip = self.model.add_text_overlay(
            text=txt,
            font_size=font_size,
            text_color=color_str,
            pos_preset=pos_preset,
            bg_style=bg_style,
            opacity=opacity,
            start_time=start_t,
            duration=dur
        )
        self.console.append_log("INFO", f"Superposición añadida: '{clip.name}' en {start_t:.2f}s por {dur:.2f}s")
        self.timeline.render_tracks()
        self._sync_preview_at(self.current_time)

    # =========================================================================
    # REPRODUCCIÓN Y PREVISUALIZACIÓN EN VIVO
    # =========================================================================

    def _toggle_play_pause(self):
        """Alterna el estado de reproducción del monitor."""
        tot = self.model.get_total_duration()
        if tot <= 0.05:
            return

        self.is_playing = not self.is_playing
        self.monitor.set_playback_state(self.is_playing)

        if self.is_playing:
            self._last_tick_time = time.time()
            self._playback_loop()

    def _playback_loop(self):
        """Bucle de reproducción síncrono a 30 FPS para previsualización."""
        if not self.is_playing:
            return

        now = time.time()
        dt = now - self._last_tick_time
        self._last_tick_time = now

        tot = self.model.get_total_duration()
        self.current_time += dt

        if self.current_time >= tot:
            self.current_time = 0.0  # Reiniciar al inicio

        self._sync_preview_at(self.current_time)
        self.after(33, self._playback_loop)

    def _on_monitor_seek(self, target_time: float):
        """Responde al movimiento de la seekbar por parte del usuario."""
        tot = self.model.get_total_duration()
        self.current_time = max(0.0, min(target_time, tot))
        self._sync_preview_at(self.current_time)

    def _on_monitor_step(self, delta_seconds: float):
        """Avanza o retrocede en pasos de 1s o 5s."""
        tot = self.model.get_total_duration()
        self.current_time = max(0.0, min(self.current_time + delta_seconds, tot))
        self._sync_preview_at(self.current_time)

    def _on_aspect_change(self, aspect: str):
        """Actualiza la relación de aspecto del monitor."""
        self.selected_aspect = aspect
        self._sync_preview_at(self.current_time)
        self.console.append_log("INFO", f"Relación de aspecto cambiada a: {aspect}")

    def _sync_preview_at(self, time_pos: float):
        """Compone y refresca el fotograma exacto del monitor a time_pos."""
        tot = self.model.get_total_duration()
        self.monitor.update_time_display(time_pos, tot)

        cw = max(10, self.monitor.canvas.winfo_width())
        ch = max(10, self.monitor.canvas.winfo_height())

        frame_img = CompositorEngine.get_preview_frame(
            self.model,
            time_pos,
            self.selected_aspect,
            cw,
            ch
        )
        self.monitor.update_monitor_display(frame_img)

    # =========================================================================
    # EDICIÓN EN LÍNEA DE TIEMPO: SPLIT, DELETE, SPEED, REORDER
    # =========================================================================

    def _on_clip_selected(self, clip_id: str):
        """Carga las propiedades del clip seleccionado en la pestaña Filtros / Ajustes."""
        clip = self.model.get_clip_by_id(clip_id)
        if not clip:
            return

        self.panel1_tabs.set("Filtros / Ajustes")
        self.filter_clip_info_lbl.configure(
            text=f"Clip Activo: '{clip.name}' ({clip.duration:.2f}s | Pista: {clip.track.upper()})",
            text_color=THEME['accent_cyan']
        )

        # Cargar valores en sliders
        f = clip.filters
        self.slider_bright.set(f.get('brightness', 0.0))
        self.slider_contrast.set(f.get('contrast', 1.0))
        self.slider_saturation.set(f.get('saturation', 1.0))

        preset = f.get('preset', 'normal').capitalize()
        if preset == 'Bw':
            preset = 'B&W'
        self.filter_preset_seg.set(preset)

        if f.get('flip_h', False):
            self.check_flip_h.select()
        else:
            self.check_flip_h.deselect()

        rot_deg = f.get('rotation', 0)
        self.rot_menu.set(f"{rot_deg}° Rotación")

        if clip.is_muted:
            self.check_mute.select()
        else:
            self.check_mute.deselect()

        self.slider_volume.set(clip.volume)

    def _apply_filters_to_selected(self, preview_only: bool = False):
        """Aplica los controles de filtro al clip activo."""
        clip = self.model.get_selected_clip()
        if not clip:
            return

        clip.filters['brightness'] = float(self.slider_bright.get())
        clip.filters['contrast'] = float(self.slider_contrast.get())
        clip.filters['saturation'] = float(self.slider_saturation.get())

        p_raw = self.filter_preset_seg.get()
        if p_raw == 'B&W':
            clip.filters['preset'] = 'bw'
        elif p_raw == 'Sepia':
            clip.filters['preset'] = 'sepia'
        elif p_raw == 'Invertir':
            clip.filters['preset'] = 'invert'
        else:
            clip.filters['preset'] = 'normal'

        clip.filters['flip_h'] = bool(self.check_flip_h.get())

        rot_str = self.rot_menu.get()
        clip.filters['rotation'] = int(rot_str.split('°')[0])

        clip.is_muted = bool(self.check_mute.get())
        clip.volume = float(self.slider_volume.get())

        if not preview_only:
            self.console.append_log("INFO", f"Ajustes de video guardados para el clip '{clip.name}'.")

        self._sync_preview_at(self.current_time)

    def _reset_filters_form(self):
        clip = self.model.get_selected_clip()
        if not clip:
            return
        clip.filters = {
            'brightness': 0.0,
            'contrast': 1.0,
            'saturation': 1.0,
            'preset': 'normal',
            'flip_h': False,
            'rotation': 0
        }
        clip.is_muted = False
        clip.volume = 1.0
        self._on_clip_selected(clip.clip_id)
        self._sync_preview_at(self.current_time)
        self.console.append_log("INFO", f"Filtros restablecidos a valores estándar para '{clip.name}'.")

    def _on_timeline_split(self):
        """✂️ Divide el clip seleccionado en la posición actual del cabezal."""
        clip = self.model.get_selected_clip()
        if not clip:
            messagebox.showinfo("Selección requerida", "Por favor haz clic en un clip para seleccionarlo antes de dividir.")
            return

        success, msg = self.model.split_clip(clip.clip_id, self.current_time)
        if success:
            self.console.append_log("INFO", f"✂️ {msg}")
            self.timeline.render_tracks()
            self._sync_preview_at(self.current_time)
        else:
            messagebox.showwarning("No se puede dividir", msg)

    def _on_timeline_delete(self):
        """🗑️ Elimina el clip seleccionado de la pista."""
        clip = self.model.get_selected_clip()
        if not clip:
            return

        name = clip.name
        self.model.remove_clip(clip.clip_id)
        self.console.append_log("INFO", f"🗑️ Clip '{name}' eliminado de la línea de tiempo.")
        self.timeline.render_tracks()
        self._sync_preview_at(self.current_time)

    def _on_timeline_speed(self):
        """⚡ Abre diálogo para cambiar velocidad del clip."""
        clip = self.model.get_selected_clip()
        if not clip:
            messagebox.showinfo("Selección requerida", "Selecciona un clip para modificar su velocidad.")
            return

        dialog = ctk.CTkInputDialog(
            text=f"Velocidad actual de '{clip.name}': {clip.speed:.2f}x\nIntroduce nuevo factor (ej: 0.5, 1.25, 1.5, 2.0):",
            title="⚡ Ajustar Velocidad de Reproducción"
        )
        val = dialog.get_input()
        if val:
            try:
                new_speed = float(val)
                self.model.change_clip_speed(clip.clip_id, new_speed)
                self.console.append_log("INFO", f"Velocidad de '{clip.name}' cambiada a {new_speed:.2f}x.")
                self.timeline.render_tracks()
                self._sync_preview_at(self.current_time)
            except ValueError:
                messagebox.showerror("Error", "Debes ingresar un número válido (ej: 1.5).")

    def _on_timeline_reorder(self, direction: int):
        """🔀 Mueve el clip de video a la izquierda o derecha en la secuencia."""
        clip = self.model.get_selected_clip()
        if not clip:
            return

        if self.model.move_clip_order(clip.clip_id, direction):
            dir_str = "izquierda" if direction == -1 else "derecha"
            self.console.append_log("INFO", f"Clip '{clip.name}' desplazado hacia la {dir_str}.")
            self.timeline.render_tracks()
            self._sync_preview_at(self.current_time)

    def _on_open_concat_modal(self):
        """🔗 Abre el modal de unión y concatenación."""
        ConcatDialog(self, self.model, on_apply=self._after_concat_apply)

    def _after_concat_apply(self):
        self.console.append_log("INFO", "🔗 Clips concatenados y reordenados exitosamente en la pista principal.")
        self.timeline.render_tracks()
        self._sync_preview_at(self.current_time)

    def _on_timeline_clear(self):
        """🧹 Limpia la línea de tiempo tras confirmación."""
        if not self.model.video_clips and not self.model.overlay_clips and not self.model.audio_clips:
            return

        if messagebox.askyesno("Confirmar", "¿Deseas vaciar todos los clips de la línea de tiempo?"):
            self.model.clear_all()
            self.current_time = 0.0
            self.timeline.render_tracks()
            self._sync_preview_at(0.0)
            self.console.append_log("INFO", "Línea de tiempo vaciada.")

    # =========================================================================
    # EXPORTACIÓN CONCURRENTE Y CANCELACIÓN SEGURA
    # =========================================================================

    def _open_export_modal(self):
        """Abre la ventana modal de configuración de exportación."""
        if not self.model.video_clips and not self.model.audio_clips:
            messagebox.showwarning("Timeline vacía", "Añade al menos un clip de video o audio a la línea de tiempo antes de exportar.")
            return

        ExportDialog(self, self.model, on_start_export=self._start_export_worker)

    def _start_export_worker(self, config: dict):
        """Inicia el hilo secundario de exportación con MoviePy."""
        # Pausar reproducción si estaba activa
        if self.is_playing:
            self._toggle_play_pause()

        self.cancel_event.clear()
        self.progress_bar.set(0.0)
        self.lbl_status.configure(text="⚡ Renderizando video con MoviePy y FFmpeg...", text_color=THEME['accent_cyan'])
        self.lbl_progress_num.configure(text="Iniciando codificación...")
        self.btn_cancel_export.configure(state="normal")
        self.btn_export_main.configure(state="disabled")

        self.active_export_worker = ExportWorker(
            self.model,
            config,
            self.event_queue,
            self.cancel_event
        )
        self.active_export_worker.start()

    def _cancel_export_process(self):
        """🛑 Detiene inmediatamente FFmpeg mediante threading.Event y limpia archivos temporales."""
        if self.active_export_worker and self.active_export_worker.is_alive():
            self.cancel_event.set()
            self.lbl_status.configure(text="🛑 Cancelando exportación y limpiando...", text_color=THEME['accent_red'])
            self.console.append_log("WARNING", "Señal de cancelación enviada a MoviePy y FFmpeg...")

    def _poll_event_queue(self):
        """Bucle de recepción de eventos del hilo secundario (a prueba de bloqueos de UI)."""
        try:
            while True:
                msg = self.event_queue.get_nowait()
                msg_type = msg.get('type')

                if msg_type == 'progress':
                    pct = msg['percentage']
                    self.progress_bar.set(pct / 100.0)
                    self.lbl_progress_num.configure(
                        text=f"{pct:.1f}% | Cuadro {msg['frame']}/{msg['total_frames']} | {msg['fps']:.1f} FPS | Restante: {msg['eta']}"
                    )

                elif msg_type == 'log':
                    self.console.append_log(msg['level'], msg['message'])

                elif msg_type == 'complete':
                    self.lbl_status.configure(text="✅ Exportación Completada Exitosamente", text_color=THEME['accent_green'])
                    self.lbl_progress_num.configure(text=f"100.0% | Finalizado en {msg['elapsed']:.1f}s | {msg['filesize_mb']:.2f} MB")
                    self.btn_cancel_export.configure(state="disabled")
                    self.btn_export_main.configure(state="normal")
                    self._show_export_success_dialog(msg['output_path'])

                elif msg_type == 'cancelled':
                    self.lbl_status.configure(text="🛑 Exportación Cancelada por el Usuario", text_color=THEME['accent_red'])
                    self.lbl_progress_num.configure(text="0.0% | Proceso abortado")
                    self.progress_bar.set(0.0)
                    self.btn_cancel_export.configure(state="disabled")
                    self.btn_export_main.configure(state="normal")

                elif msg_type == 'error':
                    self.lbl_status.configure(text="❌ Error Crítico en Renderizado", text_color=THEME['accent_red'])
                    self.btn_cancel_export.configure(state="disabled")
                    self.btn_export_main.configure(state="normal")
                    messagebox.showerror("Error de Renderizado", f"Ocurrió un error al procesar el video:\n\n{msg['error']}")

                elif msg_type == 'demo_ready':
                    self.lbl_status.configure(text="🟢 Medios de prueba generados y listos", text_color=THEME['accent_green'])
                    self.console.append_log("SUCCESS", "¡Clips demo listos! Se han cargado en la biblioteca.")
                    self._refresh_media_list()

        except queue.Empty:
            pass

        # Reprogramar a ~30ms para refresco constante a 60 FPS
        self.after(30, self._poll_event_queue)

    def _show_export_success_dialog(self, out_path: str):
        """Muestra ventana de confirmación con acceso rápido al archivo."""
        if messagebox.askyesno(
            "Exportación Exitosa",
            f"El video se ha exportado correctamente en:\n{out_path}\n\n¿Deseas abrir la carpeta contenedora?"
        ):
            try:
                folder = os.path.dirname(out_path)
                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', folder])
                else:
                    subprocess.run(['xdg-open', folder])
            except Exception as e:
                self.console.append_log("WARNING", f"No se pudo abrir carpeta: {e}")

    # =========================================================================
    # MONITOR DE RECURSOS DEL SISTEMA
    # =========================================================================

    def _update_system_stats(self):
        """Consulta cada 2 segundos el uso de CPU y Memoria RAM vía psutil."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.stats_pill.configure(text=f"⚡ CPU: {cpu:.0f}% | RAM: {ram:.0f}%")
        except Exception:
            pass
        self.after(2000, self._update_system_stats)


if __name__ == "__main__":
    app = VideoEditorProApp()
    app.mainloop()
