"""
ui_components.py - Componentes Visuales Reutilizables de Interfaz CapCut Dark Mode.
Construido con CustomTkinter, Pillow y Tkinter Canvas de alto rendimiento.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Optional, Dict, List
import customtkinter as ctk
from PIL import Image, ImageTk

from editor_core import TimelineModel, TimelineClip, CompositorEngine


# Paleta de colores oficial estilo CapCut Pro Dark Mode
THEME = {
    'bg_dark': '#121214',
    'panel_bg': '#1A1A1E',
    'panel_border': '#27272F',
    'accent_cyan': '#00D2C4',
    'accent_cyan_hover': '#00B4A7',
    'accent_purple': '#7B61FF',
    'accent_purple_hover': '#694DF8',
    'accent_green': '#00E676',
    'accent_red': '#FF4D4D',
    'accent_red_hover': '#E03E3E',
    'text_primary': '#FFFFFF',
    'text_secondary': '#A0A0AB',
    'console_bg': '#0A0A0C',
    'track_video_border': '#00D2C4',
    'track_overlay_border': '#7B61FF',
    'track_audio_border': '#00E676'
}


class PreviewMonitorWidget(ctk.CTkFrame):
    """
    Monitor de previsualización estilo estación de edición profesional.
    Soporta relaciones de aspecto dinámicas (16:9, 9:16, 1:1), controles de transporte y seekbar.
    """
    def __init__(
        self,
        master,
        on_play_pause: Callable[[], None],
        on_seek: Callable[[float], None],
        on_step: Callable[[float], None],
        on_aspect_change: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, fg_color=THEME['panel_bg'], corner_radius=10, border_width=1, border_color=THEME['panel_border'], **kwargs)
        self.on_play_pause = on_play_pause
        self.on_seek = on_seek
        self.on_step = on_step
        self.on_aspect_change = on_aspect_change

        self.current_aspect: str = "16:9"
        self.total_duration: float = 0.0
        self.current_time: float = 0.0
        self.is_playing: bool = False
        self._photo_cache = None

        self._build_ui()

    def _build_ui(self):
        # 1. Barra superior del monitor
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=12, pady=(10, 6))

        title_lbl = ctk.CTkLabel(
            top_bar,
            text="🖥️ MONITOR DE EDICIÓN",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        title_lbl.pack(side="left")

        # Selector de Relación de Aspecto
        self.aspect_segmented = ctk.CTkSegmentedButton(
            top_bar,
            values=["16:9", "9:16", "1:1"],
            command=self._handle_aspect_change,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color=THEME['accent_cyan'],
            selected_hover_color=THEME['accent_cyan_hover']
        )
        self.aspect_segmented.set("16:9")
        self.aspect_segmented.pack(side="right")

        aspect_tag = ctk.CTkLabel(
            top_bar,
            text="Formato:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=THEME['text_secondary']
        )
        aspect_tag.pack(side="right", padx=(0, 6))

        # 2. Lienzo visual (Tk Canvas para alto refresco a 60 FPS)
        self.canvas_container = ctk.CTkFrame(self, fg_color="#0A0A0C", corner_radius=6)
        self.canvas_container.pack(fill="both", expand=True, padx=12, pady=4)

        self.canvas = tk.Canvas(
            self.canvas_container,
            bg="#0E0E10",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # 3. Barra de Transporte y Seekbar
        bottom_bar = ctk.CTkFrame(self, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=12, pady=(6, 10))

        # Indicador de tiempo
        self.time_label = ctk.CTkLabel(
            bottom_bar,
            text="00:00.00 / 00:00.00",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        self.time_label.pack(side="left", padx=(0, 10))

        # Barra deslizante de reproducción (Scrubber)
        self.seek_slider = ctk.CTkSlider(
            bottom_bar,
            from_=0.0,
            to=1.0,
            command=self._handle_slider_move,
            button_color=THEME['accent_cyan'],
            button_hover_color=THEME['accent_cyan_hover'],
            progress_color=THEME['accent_cyan']
        )
        self.seek_slider.set(0.0)
        self.seek_slider.pack(side="left", fill="x", expand=True, padx=8)

        # Botones de control
        btn_box = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        btn_box.pack(side="right")

        self.btn_rewind_5 = ctk.CTkButton(
            btn_box, text="⏮ -5s", width=46, height=28,
            fg_color="#27272F", hover_color="#34343F",
            command=lambda: self.on_step(-5.0)
        )
        self.btn_rewind_5.pack(side="left", padx=2)

        self.btn_rewind_1 = ctk.CTkButton(
            btn_box, text="◀ -1s", width=46, height=28,
            fg_color="#27272F", hover_color="#34343F",
            command=lambda: self.on_step(-1.0)
        )
        self.btn_rewind_1.pack(side="left", padx=2)

        self.btn_play_pause = ctk.CTkButton(
            btn_box, text="▶ Play", width=68, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=THEME['accent_cyan'], text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            command=self.on_play_pause
        )
        self.btn_play_pause.pack(side="left", padx=4)

        self.btn_forward_1 = ctk.CTkButton(
            btn_box, text="+1s ▶", width=46, height=28,
            fg_color="#27272F", hover_color="#34343F",
            command=lambda: self.on_step(1.0)
        )
        self.btn_forward_1.pack(side="left", padx=2)

        self.btn_forward_5 = ctk.CTkButton(
            btn_box, text="+5s ⏭", width=46, height=28,
            fg_color="#27272F", hover_color="#34343F",
            command=lambda: self.on_step(5.0)
        )
        self.btn_forward_5.pack(side="left", padx=2)

    def _handle_aspect_change(self, aspect: str):
        self.current_aspect = aspect
        self.on_aspect_change(aspect)

    def _handle_slider_move(self, value: float):
        t = value * max(0.01, self.total_duration)
        self.on_seek(t)

    def _on_canvas_resize(self, event):
        # Redibujar fotograma en redimensionamiento de ventana
        self.update_monitor_display(None)

    def set_playback_state(self, is_playing: bool):
        self.is_playing = is_playing
        if is_playing:
            self.btn_play_pause.configure(text="⏸ Pausa", fg_color=THEME['accent_purple'], hover_color=THEME['accent_purple_hover'], text_color="#FFFFFF")
        else:
            self.btn_play_pause.configure(text="▶ Play", fg_color=THEME['accent_cyan'], hover_color=THEME['accent_cyan_hover'], text_color="#000000")

    def update_time_display(self, current_time: float, total_duration: float):
        self.current_time = current_time
        self.total_duration = total_duration

        cur_min = int(current_time // 60)
        cur_sec = current_time % 60
        tot_min = int(total_duration // 60)
        tot_sec = total_duration % 60

        self.time_label.configure(
            text=f"{cur_min:02d}:{cur_sec:05.2f} / {tot_min:02d}:{tot_sec:05.2f}"
        )

        if total_duration > 0.01:
            progress = max(0.0, min(1.0, current_time / total_duration))
            self.seek_slider.set(progress)
        else:
            self.seek_slider.set(0.0)

    def update_monitor_display(self, pil_image: Optional[Image.Image]):
        """Renderiza una imagen Pillow centrada sobre el canvas de forma instantánea."""
        cw = max(10, self.canvas.winfo_width())
        ch = max(10, self.canvas.winfo_height())

        if pil_image is None:
            pil_image = CompositorEngine.create_idle_monitor(cw, ch, self.current_time)

        # Escalar la imagen al canvas si difiere
        if pil_image.size != (cw, ch):
            pil_image = pil_image.resize((cw, ch), Image.Resampling.BILINEAR)

        self._photo_cache = ImageTk.PhotoImage(pil_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo_cache)


class TimelineView(ctk.CTkFrame):
    """
    Representación visual multi-pista estilo CapCut:
    - Pista 1: Video Principal
    - Pista 2: Superposición / Texto
    - Pista 3: Audio Secundario / Música
    """
    def __init__(
        self,
        master,
        model: TimelineModel,
        on_clip_selected: Callable[[str], None],
        on_split: Callable[[], None],
        on_delete: Callable[[], None],
        on_speed: Callable[[], None],
        on_reorder: Callable[[int], None],
        on_open_concat: Callable[[], None],
        on_clear: Callable[[], None],
        **kwargs
    ):
        super().__init__(master, fg_color=THEME['panel_bg'], corner_radius=10, border_width=1, border_color=THEME['panel_border'], **kwargs)
        self.model = model
        self.on_clip_selected = on_clip_selected
        self.on_split = on_split
        self.on_delete = on_delete
        self.on_speed = on_speed
        self.on_reorder = on_reorder
        self.on_open_concat = on_open_concat
        self.on_clear = on_clear

        self._build_ui()

    def _build_ui(self):
        # 1. Barra de Herramientas Rápida
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(8, 4))

        title_lbl = ctk.CTkLabel(
            toolbar,
            text="🎞️ LÍNEA DE TIEMPO (TIMELINE)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#FFFFFF"
        )
        title_lbl.pack(side="left")

        # Botones de Acción Rápida
        btn_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_box.pack(side="right")

        self.btn_split = ctk.CTkButton(
            btn_box, text="✂️ Dividir (Split)", width=105, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=self.on_split
        )
        self.btn_split.pack(side="left", padx=3)

        self.btn_delete = ctk.CTkButton(
            btn_box, text="🗑️ Eliminar Clip", width=105, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E2E38", hover_color=THEME['accent_red_hover'],
            command=self.on_delete
        )
        self.btn_delete.pack(side="left", padx=3)

        self.btn_speed = ctk.CTkButton(
            btn_box, text="⚡ Velocidad", width=95, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=self.on_speed
        )
        self.btn_speed.pack(side="left", padx=3)

        self.btn_move_left = ctk.CTkButton(
            btn_box, text="◀ Reordenar", width=90, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=lambda: self.on_reorder(-1)
        )
        self.btn_move_left.pack(side="left", padx=2)

        self.btn_move_right = ctk.CTkButton(
            btn_box, text="Reordenar ▶", width=90, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=lambda: self.on_reorder(1)
        )
        self.btn_move_right.pack(side="left", padx=2)

        self.btn_concat = ctk.CTkButton(
            btn_box, text="🔗 Unir Clips", width=95, height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME['accent_cyan'], text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            command=self.on_open_concat
        )
        self.btn_concat.pack(side="left", padx=3)

        self.btn_clear = ctk.CTkButton(
            btn_box, text="🧹", width=36, height=28,
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=self.on_clear
        )
        self.btn_clear.pack(side="left", padx=3)

        # 2. Contenedor deslizable de Pistas
        self.tracks_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="#141418",
            corner_radius=6,
            orientation="vertical",
            height=160
        )
        self.tracks_scroll.pack(fill="both", expand=True, padx=12, pady=(4, 8))

        self.render_tracks()

    def render_tracks(self):
        """Reconstruye visualmente las pistas y sus clips correspondientes."""
        for widget in self.tracks_scroll.winfo_children():
            widget.destroy()

        # Pista 1: Video Principal
        self._render_track_row("🎥 Pista de Video Principal", self.model.video_clips, THEME['track_video_border'], "video")

        # Pista 2: Superposición / Texto
        self._render_track_row("🔤 Superposición y Títulos", self.model.overlay_clips, THEME['track_overlay_border'], "overlay")

        # Pista 3: Audio
        self._render_track_row("🎵 Pista de Audio / Música", self.model.audio_clips, THEME['track_audio_border'], "audio")

    def _render_track_row(self, title: str, clips: List[TimelineClip], border_col: str, track_type: str):
        row_frame = ctk.CTkFrame(self.tracks_scroll, fg_color="#1A1A20", corner_radius=6, border_width=1, border_color="#25252E")
        row_frame.pack(fill="x", pady=4, padx=2)

        # Cabecera de la pista
        header = ctk.CTkFrame(row_frame, fg_color="transparent", width=170)
        header.pack(side="left", padx=8, pady=6)
        lbl = ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#C0C0D0",
            anchor="w",
            width=165
        )
        lbl.pack(side="left")

        # Contenedor horizontal de clips
        clips_container = ctk.CTkFrame(row_frame, fg_color="transparent")
        clips_container.pack(side="left", fill="x", expand=True, padx=4, pady=4)

        if not clips:
            empty_lbl = ctk.CTkLabel(
                clips_container,
                text="-- Sin clips en esta pista --",
                font=ctk.CTkFont(family="Segoe UI", size=10, slant="italic"),
                text_color="#606070"
            )
            empty_lbl.pack(side="left", padx=8)
            return

        for clip in clips:
            is_selected = (clip.clip_id == self.model.selected_clip_id)
            clip_card = self._create_clip_card(clips_container, clip, is_selected, border_col)
            clip_card.pack(side="left", padx=4, pady=2)

    def _create_clip_card(self, parent, clip: TimelineClip, is_selected: bool, border_col: str) -> ctk.CTkFrame:
        card_bg = "#252530" if not is_selected else "#2F2F40"
        card_border = "#00D2C4" if is_selected else border_col

        card = ctk.CTkFrame(
            parent,
            fg_color=card_bg,
            corner_radius=6,
            border_width=2 if is_selected else 1,
            border_color=card_border
        )

        # Nombre del clip y tiempo
        name_text = clip.name if len(clip.name) <= 18 else clip.name[:16] + ".."
        title = ctk.CTkLabel(
            card,
            text=f"📌 {name_text}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#FFFFFF" if is_selected else "#D0D0E0"
        )
        title.pack(anchor="w", padx=8, pady=(4, 0))

        # Indicador de tiempo y velocidad
        dur_info = f"[{clip.start_time:.1f}s - {clip.end_time:.1f}s] ({clip.duration:.1f}s)"
        if abs(clip.speed - 1.0) > 0.05:
            dur_info += f" ⚡{clip.speed:.1f}x"
        if clip.is_muted:
            dur_info += " 🔇"

        sub_info = ctk.CTkLabel(
            card,
            text=dur_info,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=THEME['accent_cyan'] if is_selected else "#9090A0"
        )
        sub_info.pack(anchor="w", padx=8, pady=(0, 4))

        # Vincular clic para seleccionar
        def _on_click(event, cid=clip.clip_id):
            self.model.selected_clip_id = cid
            self.render_tracks()
            self.on_clip_selected(cid)

        card.bind("<Button-1>", _on_click)
        title.bind("<Button-1>", _on_click)
        sub_info.bind("<Button-1>", _on_click)

        return card


class ConcatDialog(ctk.CTkToplevel):
    """
    Ventana modal '🔗 Unir Clips' con contenedor deslizable (CTkScrollableFrame)
    para ordenar y concatenar los clips seleccionados.
    """
    def __init__(self, master, model: TimelineModel, on_apply: Callable[[], None]):
        super().__init__(master)
        self.model = model
        self.on_apply = on_apply

        self.title("🔗 Gestor de Concatenación y Unión de Clips")
        self.geometry("620x520")
        self.configure(fg_color=THEME['panel_bg'])
        self.attributes("-topmost", True)
        self.resizable(False, False)

        # Copia de trabajo para reordenar
        self.clips_list: List[TimelineClip] = list(model.video_clips)

        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=12)

        lbl = ctk.CTkLabel(
            header,
            text="🔗 Unir y Concatenar Clips de Video",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        lbl.pack(anchor="w")

        desc = ctk.CTkLabel(
            header,
            text="Organiza la secuencia de clips que formarán la composición final. Utiliza los botones para subir o bajar el orden.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=THEME['text_secondary']
        )
        desc.pack(anchor="w", pady=(2, 0))

        # Contenedor Deslizable de Clips
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="#131317",
            corner_radius=8,
            height=300
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=8)

        self._render_list()

        # Resumen y Acciones
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=16, pady=(4, 14))

        self.summary_lbl = ctk.CTkLabel(
            bottom_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        self.summary_lbl.pack(side="left")
        self._update_summary()

        btn_apply = ctk.CTkButton(
            bottom_frame,
            text="🔗 Aplicar Unión a Timeline",
            fg_color=THEME['accent_cyan'],
            text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._apply_concat
        )
        btn_apply.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            bottom_frame,
            text="Cerrar",
            fg_color="#2E2E38",
            hover_color="#3C3C4A",
            command=self.destroy
        )
        btn_cancel.pack(side="right")

    def _render_list(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if not self.clips_list:
            lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="No hay clips de video en el proyecto para concatenar.",
                font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
                text_color="#808090"
            )
            lbl.pack(pady=40)
            return

        for idx, clip in enumerate(self.clips_list):
            row = ctk.CTkFrame(self.scroll_frame, fg_color="#1E1E26", corner_radius=6)
            row.pack(fill="x", pady=3, padx=4)

            # Número de orden
            num_lbl = ctk.CTkLabel(
                row,
                text=f"{idx + 1}.",
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                text_color=THEME['accent_cyan'],
                width=24
            )
            num_lbl.pack(side="left", padx=(8, 4))

            # Información del clip
            info_lbl = ctk.CTkLabel(
                row,
                text=f"{clip.name}   |   {clip.duration:.2f}s",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                anchor="w"
            )
            info_lbl.pack(side="left", fill="x", expand=True, padx=6)

            # Botones Subir y Bajar
            btn_up = ctk.CTkButton(
                row, text="⬆️", width=32, height=26,
                fg_color="#2C2C36", hover_color="#3A3A48",
                command=lambda i=idx: self._move(i, -1)
            )
            btn_up.pack(side="left", padx=2)

            btn_down = ctk.CTkButton(
                row, text="⬇️", width=32, height=26,
                fg_color="#2C2C36", hover_color="#3A3A48",
                command=lambda i=idx: self._move(i, 1)
            )
            btn_down.pack(side="left", padx=2)

    def _move(self, idx: int, direction: int):
        new_idx = idx + direction
        if 0 <= new_idx < len(self.clips_list):
            self.clips_list[idx], self.clips_list[new_idx] = self.clips_list[new_idx], self.clips_list[idx]
            self._render_list()
            self._update_summary()

    def _update_summary(self):
        tot_dur = sum(c.duration for c in self.clips_list)
        self.summary_lbl.configure(text=f"Clips a unir: {len(self.clips_list)} | Duración total resultante: {tot_dur:.2f}s")

    def _apply_concat(self):
        self.model.video_clips = list(self.clips_list)
        self.model.repack_video_clips()
        self.on_apply()
        self.destroy()


class ExportDialog(ctk.CTkToplevel):
    """
    Modal de Configuración de Exportación Avanzada:
    Presets de Resolución (1080p, 720p, 9:16 Vertical, 1:1 Cuadrado), FPS, Formato y Calidad.
    """
    def __init__(self, master, model: TimelineModel, on_start_export: Callable[[Dict[str, any]], None]):
        super().__init__(master)
        self.model = model
        self.on_start_export = on_start_export

        self.title("🚀 Exportar Proyecto de Video Pro")
        self.geometry("540x580")
        self.configure(fg_color=THEME['panel_bg'])
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        # Cabecera
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 10))

        title = ctk.CTkLabel(
            header,
            text="🚀 Renderizar y Exportar Composición",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        title.pack(anchor="w")

        # Formulario
        form = ctk.CTkFrame(self, fg_color="#15151A", corner_radius=8)
        form.pack(fill="both", expand=True, padx=20, pady=8)

        # 1. Preset de Resolución
        self._add_label(form, "Resolución y Relación de Aspecto:")
        self.res_var = ctk.StringVar(value="1080p Full HD (1920x1080)")
        self.res_menu = ctk.CTkOptionMenu(
            form,
            variable=self.res_var,
            values=[
                "1080p Full HD (1920x1080)",
                "720p HD (1280x720)",
                "480p SD (854x480)",
                "9:16 Vertical (1080x1920) - Shorts/TikTok",
                "1:1 Cuadrado (1080x1080) - Instagram"
            ],
            fg_color="#2A2A34",
            button_color=THEME['accent_cyan'],
            button_hover_color=THEME['accent_cyan_hover'],
            dropdown_fg_color="#1E1E26"
        )
        self.res_menu.pack(fill="x", padx=16, pady=(0, 10))

        # 2. Tasa de Cuadros (FPS)
        self._add_label(form, "Tasa de Cuadros por Segundo (FPS):")
        self.fps_var = ctk.StringVar(value="30 FPS (Estándar)")
        self.fps_menu = ctk.CTkOptionMenu(
            form,
            variable=self.fps_var,
            values=["24 FPS (Cinematográfico)", "30 FPS (Estándar)", "60 FPS (Ultra Fluido)"],
            fg_color="#2A2A34",
            button_color=THEME['accent_cyan'],
            button_hover_color=THEME['accent_cyan_hover'],
            dropdown_fg_color="#1E1E26"
        )
        self.fps_menu.pack(fill="x", padx=16, pady=(0, 10))

        # 3. Formato de Salida
        self._add_label(form, "Formato de Contenedor:")
        self.format_var = ctk.StringVar(value=".mp4 (H.264 / AAC)")
        self.format_menu = ctk.CTkOptionMenu(
            form,
            variable=self.format_var,
            values=[
                ".mp4 (H.264 / AAC)",
                ".mov (QuickTime)",
                ".gif (Animación Web)",
                ".mp3 (Solo Audio Consolidado)"
            ],
            fg_color="#2A2A34",
            button_color=THEME['accent_cyan'],
            button_hover_color=THEME['accent_cyan_hover'],
            dropdown_fg_color="#1E1E26"
        )
        self.format_menu.pack(fill="x", padx=16, pady=(0, 10))

        # 4. Calidad / Bitrate
        self._add_label(form, "Calidad de Renderizado:")
        self.quality_var = ctk.StringVar(value="Alta")
        self.quality_segmented = ctk.CTkSegmentedButton(
            form,
            values=["Rápida", "Media", "Alta"],
            variable=self.quality_var,
            selected_color=THEME['accent_cyan'],
            selected_hover_color=THEME['accent_cyan_hover']
        )
        self.quality_segmented.pack(fill="x", padx=16, pady=(0, 14))

        # 5. Ruta de Destino
        self._add_label(form, "Archivo de Salida:")
        path_box = ctk.CTkFrame(form, fg_color="transparent")
        path_box.pack(fill="x", padx=16, pady=(0, 14))

        default_out = os.path.join(os.path.expanduser("~"), "Videos", "Export_CapCutPro.mp4")
        self.path_entry = ctk.CTkEntry(path_box, fg_color="#202028")
        self.path_entry.insert(0, default_out)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_browse = ctk.CTkButton(
            path_box,
            text="Examinar...",
            width=85,
            fg_color="#2E2E38",
            hover_color="#3C3C4A",
            command=self._browse_path
        )
        btn_browse.pack(side="right")

        # Botones Inferiores
        action_bar = ctk.CTkFrame(self, fg_color="transparent")
        action_bar.pack(fill="x", padx=20, pady=(10, 16))

        btn_start = ctk.CTkButton(
            action_bar,
            text="🚀 Iniciar Renderizado",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=THEME['accent_cyan'],
            text_color="#000000",
            hover_color=THEME['accent_cyan_hover'],
            height=34,
            command=self._confirm_export
        )
        btn_start.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            action_bar,
            text="Cancelar",
            fg_color="#2E2E38",
            hover_color="#3C3C4A",
            height=34,
            command=self.destroy
        )
        btn_cancel.pack(side="right")

    def _add_label(self, parent, text: str):
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#B0B0C0"
        )
        lbl.pack(anchor="w", padx=16, pady=(8, 2))

    def _browse_path(self):
        fmt = self.format_var.get()
        ext = ".mp4"
        if ".mov" in fmt:
            ext = ".mov"
        elif ".gif" in fmt:
            ext = ".gif"
        elif ".mp3" in fmt:
            ext = ".mp3"

        fpath = filedialog.asksaveasfilename(
            title="Guardar Video Exportado",
            defaultextension=ext,
            filetypes=[("Archivo de Salida", f"*{ext}"), ("Todos los archivos", "*.*")]
        )
        if fpath:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, fpath)

    def _confirm_export(self):
        out_path = self.path_entry.get().strip()
        if not out_path:
            messagebox.showwarning("Ruta requerida", "Por favor selecciona una ruta de destino para guardar el video.")
            return

        # Mapeo de resoluciones
        res_str = self.res_var.get()
        if "1920x1080" in res_str:
            res = (1920, 1080)
            aspect = "16:9"
        elif "1280x720" in res_str:
            res = (1280, 720)
            aspect = "16:9"
        elif "854x480" in res_str:
            res = (854, 480)
            aspect = "16:9"
        elif "1080x1920" in res_str:
            res = (1080, 1920)
            aspect = "9:16"
        elif "1080x1080" in res_str:
            res = (1080, 1080)
            aspect = "1:1"
        else:
            res = (1920, 1080)
            aspect = "16:9"

        # Mapeo de FPS
        fps_str = self.fps_var.get()
        fps = 30
        if "24" in fps_str:
            fps = 24
        elif "60" in fps_str:
            fps = 60

        # Formato
        fmt_str = self.format_var.get()
        fmt = ".mp4"
        if ".mov" in fmt_str:
            fmt = ".mov"
        elif ".gif" in fmt_str:
            fmt = ".gif"
        elif ".mp3" in fmt_str:
            fmt = ".mp3"

        config = {
            'output_path': out_path,
            'resolution': res,
            'resolution_name': res_str,
            'aspect_ratio': aspect,
            'fps': fps,
            'format': fmt,
            'quality': self.quality_var.get()
        }

        self.on_start_export(config)
        self.destroy()


class ConsoleWidget(ctk.CTkFrame):
    """
    Consola de registros en formato monospace (#0A0A0C) con soporte
    de marcas de tiempo, etiquetas de color y exportación de logs.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=THEME['panel_bg'], corner_radius=10, border_width=1, border_color=THEME['panel_border'], **kwargs)
        self._build_ui()

    def _build_ui(self):
        # Cabecera
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(6, 2))

        lbl = ctk.CTkLabel(
            header,
            text="📟 CONSOLA DE RENDIMIENTO Y REGISTROS EN VIVO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME['accent_cyan']
        )
        lbl.pack(side="left")

        btn_clear = ctk.CTkButton(
            header, text="🧹 Limpiar", width=65, height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=self.clear_logs
        )
        btn_clear.pack(side="right", padx=(4, 0))

        btn_save = ctk.CTkButton(
            header, text="💾 Guardar Log", width=85, height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#2E2E38", hover_color="#3C3C4A",
            command=self.save_logs
        )
        btn_save.pack(side="right")

        # Área de texto monospace
        self.textbox = ctk.CTkTextbox(
            self,
            fg_color=THEME['console_bg'],
            text_color="#D8D8E0",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=6,
            wrap="word",
            height=90
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(2, 8))

    def append_log(self, level: str, message: str):
        now_str = tk.datetime.datetime.now().strftime("%H:%M:%S") if hasattr(tk, 'datetime') else ""
        if not now_str:
            import time
            now_str = time.strftime("%H:%M:%S")

        prefix = f"[{now_str}] [{level}] "
        line = f"{prefix}{message}\n"

        self.textbox.insert("end", line)
        self.textbox.see("end")

    def clear_logs(self):
        self.textbox.delete("1.0", "end")

    def save_logs(self):
        text = self.textbox.get("1.0", "end").strip()
        if not text:
            return
        fpath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Archivos de Texto", "*.txt")]
        )
        if fpath:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(text)
