"""
editor_core.py - Núcleo de Edición, Modelo de Línea de Tiempo y Composición de Video.
Arquitectura estilo CapCut para 'Editor y Procesador de Video Pro'.
Compatible con MoviePy 2.x, Pillow y NumPy.
"""

import os
import uuid
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps

# Importaciones de MoviePy 2.x
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    ColorClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx
)
from moviepy.audio.AudioClip import CompositeAudioClip, AudioArrayClip


class MediaAsset:
    """
    Representa un archivo de medio importado (Video, Audio o Imagen)
    con sus metadatos y miniatura generada para la interfaz.
    """
    def __init__(self, file_path: str):
        self.asset_id: str = str(uuid.uuid4())[:8]
        self.file_path: str = os.path.abspath(file_path)
        self.filename: str = os.path.basename(file_path)
        self.media_type: str = self._detect_type()
        
        self.duration: float = 0.0
        self.fps: float = 30.0
        self.resolution: Tuple[int, int] = (1280, 720)
        self.thumbnail: Optional[Image.Image] = None
        self._clip_cache: Optional[any] = None
        
        self._inspect_media()

    def _detect_type(self) -> str:
        ext = os.path.splitext(self.filename)[1].lower()
        if ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv'):
            return 'video'
        elif ext in ('.mp3', '.wav', '.aac', '.m4a', '.ogg', '.flac'):
            return 'audio'
        elif ext in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
            return 'image'
        return 'unknown'

    def _inspect_media(self):
        """Extrae metadatos y genera miniatura sin saturar la memoria."""
        try:
            if self.media_type == 'video':
                with VideoFileClip(self.file_path) as v_clip:
                    self.duration = float(v_clip.duration or 0.0)
                    self.fps = float(v_clip.fps or 30.0)
                    self.resolution = (int(v_clip.w), int(v_clip.h))
                    # Generar miniatura del primer tercio del video
                    thumb_t = min(1.0, self.duration * 0.3)
                    frame = v_clip.get_frame(thumb_t)
                    thumb_img = Image.fromarray(frame)
                    thumb_img.thumbnail((90, 54), Image.Resampling.LANCZOS)
                    self.thumbnail = thumb_img
            elif self.media_type == 'audio':
                with AudioFileClip(self.file_path) as a_clip:
                    self.duration = float(a_clip.duration or 0.0)
                    self.fps = float(a_clip.fps or 44100.0)
                    self.resolution = (0, 0)
                    self.thumbnail = self._create_audio_icon()
            elif self.media_type == 'image':
                with Image.open(self.file_path) as img:
                    self.resolution = img.size
                    self.duration = 5.0  # Duración por defecto para imágenes en timeline
                    self.fps = 30.0
                    thumb_img = img.copy()
                    thumb_img.thumbnail((90, 54), Image.Resampling.LANCZOS)
                    self.thumbnail = thumb_img
            else:
                self.thumbnail = self._create_unknown_icon()
        except Exception as e:
            print(f"[ERROR inspect_media] {self.filename}: {e}")
            self.thumbnail = self._create_unknown_icon()

    def get_clip_obj(self):
        """Retorna una instancia reutilizable del clip base."""
        if self._clip_cache is None:
            if self.media_type == 'video':
                self._clip_cache = VideoFileClip(self.file_path)
            elif self.media_type == 'audio':
                self._clip_cache = AudioFileClip(self.file_path)
            elif self.media_type == 'image':
                self._clip_cache = ImageClip(self.file_path)
        return self._clip_cache

    def get_frame(self, t: float) -> Optional[np.ndarray]:
        """Extrae un fotograma del medio en el segundo t."""
        try:
            if self.media_type == 'video':
                clip = self.get_clip_obj()
                safe_t = max(0.0, min(t, self.duration - 0.02))
                return clip.get_frame(safe_t)
            elif self.media_type == 'image':
                with Image.open(self.file_path) as img:
                    return np.array(img.convert('RGB'))
        except Exception as e:
            print(f"[ERROR get_frame] {self.filename} en t={t}: {e}")
        return None

    def close(self):
        """Libera recursos del clip en disco."""
        if self._clip_cache is not None:
            try:
                self._clip_cache.close()
            except Exception:
                pass
            self._clip_cache = None

    def _create_audio_icon(self) -> Image.Image:
        img = Image.new('RGB', (90, 54), (25, 35, 45))
        draw = ImageDraw.Draw(img)
        # Dibujar onda estilizada
        points = [(10 + i * 5, 27 + int(15 * np.sin(i * 0.8))) for i in range(15)]
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=(0, 230, 118), width=2)
        return img

    def _create_unknown_icon(self) -> Image.Image:
        img = Image.new('RGB', (90, 54), (30, 30, 30))
        draw = ImageDraw.Draw(img)
        draw.rectangle([5, 5, 85, 49], outline=(100, 100, 100), width=1)
        draw.text((35, 18), "?", fill=(180, 180, 180))
        return img


class TimelineClip:
    """
    Representa una instancia de clip posicionada en una pista de la línea de tiempo.
    Guarda recortes (in_point, out_point), velocidad, filtros y superposiciones.
    """
    def __init__(
        self,
        clip_id: str,
        name: str,
        track: str,  # 'video', 'overlay', 'audio'
        asset: Optional[MediaAsset] = None,
        start_time: float = 0.0,
        in_point: float = 0.0,
        out_point: Optional[float] = None,
        speed: float = 1.0,
        volume: float = 1.0,
        is_muted: bool = False
    ):
        self.clip_id: str = clip_id
        self.name: str = name
        self.track: str = track
        self.asset: Optional[MediaAsset] = asset
        
        self.start_time: float = max(0.0, start_time)
        self.in_point: float = max(0.0, in_point)
        
        raw_dur = asset.duration if asset else 5.0
        self.out_point: float = out_point if out_point is not None else raw_dur
        self.speed: float = max(0.1, min(speed, 8.0))
        self.volume: float = max(0.0, min(volume, 2.0))
        self.is_muted: bool = is_muted

        # Filtros y ajustes visuales
        self.filters: Dict[str, any] = {
            'brightness': 0.0,     # -0.5 a +0.5
            'contrast': 1.0,       # 0.5 a 2.0
            'saturation': 1.0,     # 0.0 (B&W) a 2.0
            'preset': 'normal',    # 'normal', 'bw', 'sepia', 'invert'
            'flip_h': False,       # Espejo horizontal
            'rotation': 0          # 0, 90, 180, 270
        }

        # Datos de superposición (usado para pista 'overlay')
        self.overlay_data: Dict[str, any] = {
            'text': 'Texto CapCut Pro',
            'font_size': 36,
            'text_color': '#FFFFFF',
            'bg_style': 'box',     # 'none', 'box'
            'pos_preset': 'bottom', # 'center', 'bottom', 'top', 'watermark_tr', 'watermark_br'
            'opacity': 0.95
        }

    @property
    def source_duration(self) -> float:
        return max(0.05, self.out_point - self.in_point)

    @property
    def duration(self) -> float:
        """Duración efectiva en la línea de tiempo considerando la velocidad."""
        return self.source_duration / self.speed

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    def clone(self, new_id: Optional[str] = None) -> 'TimelineClip':
        """Copia profunda del clip para operaciones como Split o Duplicar."""
        c = TimelineClip(
            clip_id=new_id or str(uuid.uuid4())[:8],
            name=self.name,
            track=self.track,
            asset=self.asset,
            start_time=self.start_time,
            in_point=self.in_point,
            out_point=self.out_point,
            speed=self.speed,
            volume=self.volume,
            is_muted=self.is_muted
        )
        c.filters = self.filters.copy()
        c.overlay_data = self.overlay_data.copy()
        return c


class TimelineModel:
    """
    Gestor integral de las pistas del proyecto (Video, Superposiciones y Audio).
    Permite operaciones de corte, inserción, eliminación, velocidad y concatenación.
    """
    def __init__(self):
        self.video_clips: List[TimelineClip] = []
        self.overlay_clips: List[TimelineClip] = []
        self.audio_clips: List[TimelineClip] = []
        self.selected_clip_id: Optional[str] = None

    def add_clip(self, asset: MediaAsset, track: Optional[str] = None) -> TimelineClip:
        """Añade un nuevo clip al final de la pista indicada o inferida."""
        if track is None:
            if asset.media_type == 'audio':
                track = 'audio'
            else:
                track = 'video'

        clip_id = str(uuid.uuid4())[:8]
        start_t = 0.0

        if track == 'video':
            if self.video_clips:
                last_clip = self.video_clips[-1]
                start_t = last_clip.end_time
            clip = TimelineClip(clip_id, asset.filename, track, asset, start_time=start_t)
            self.video_clips.append(clip)
        elif track == 'audio':
            if self.audio_clips:
                start_t = self.audio_clips[-1].end_time
            clip = TimelineClip(clip_id, asset.filename, track, asset, start_time=start_t)
            self.audio_clips.append(clip)
        else: # overlay
            clip = TimelineClip(clip_id, asset.filename, track, asset, start_time=0.0)
            self.overlay_clips.append(clip)

        self.selected_clip_id = clip.clip_id
        return clip

    def add_text_overlay(
        self,
        text: str = "Título Pro",
        font_size: int = 36,
        text_color: str = "#FFFFFF",
        pos_preset: str = "bottom",
        bg_style: str = "box",
        opacity: float = 0.95,
        start_time: float = 0.0,
        duration: float = 4.0
    ) -> TimelineClip:
        """Crea un clip de superposición de texto dinámico."""
        clip_id = str(uuid.uuid4())[:8]
        clip = TimelineClip(
            clip_id=clip_id,
            name=f"Texto: {text[:15]}",
            track='overlay',
            asset=None,
            start_time=start_time,
            in_point=0.0,
            out_point=duration,
            speed=1.0
        )
        clip.overlay_data = {
            'text': text,
            'font_size': font_size,
            'text_color': text_color,
            'bg_style': bg_style,
            'pos_preset': pos_preset,
            'opacity': opacity
        }
        self.overlay_clips.append(clip)
        self.selected_clip_id = clip.clip_id
        return clip

    def get_clip_by_id(self, clip_id: str) -> Optional[TimelineClip]:
        for clip in self.video_clips + self.overlay_clips + self.audio_clips:
            if clip.clip_id == clip_id:
                return clip
        return None

    def get_selected_clip(self) -> Optional[TimelineClip]:
        if self.selected_clip_id:
            return self.get_clip_by_id(self.selected_clip_id)
        return None

    def remove_clip(self, clip_id: str) -> bool:
        """Elimina un clip y reajusta la pista de video si correspondía a ella."""
        target = self.get_clip_by_id(clip_id)
        if not target:
            return False

        if target in self.video_clips:
            self.video_clips.remove(target)
            self.repack_video_clips()
        elif target in self.overlay_clips:
            self.overlay_clips.remove(target)
        elif target in self.audio_clips:
            self.audio_clips.remove(target)

        if self.selected_clip_id == clip_id:
            self.selected_clip_id = self.video_clips[0].clip_id if self.video_clips else None
        return True

    def repack_video_clips(self):
        """Reordena temporalmente los clips de video principales secuencialmente sin huecos."""
        current_t = 0.0
        for clip in self.video_clips:
            clip.start_time = current_t
            current_t += clip.duration

    def split_clip(self, clip_id: str, split_time: float) -> Tuple[bool, str]:
        """
        Divide un clip seleccionado exactamente en split_time creando dos segmentos independientes.
        """
        clip = self.get_clip_by_id(clip_id)
        if not clip:
            return False, "Clip no encontrado."

        if not (clip.start_time < split_time < clip.end_time):
            return False, f"El cabezal ({split_time:.2f}s) debe estar dentro de la duración del clip ({clip.start_time:.2f}s - {clip.end_time:.2f}s)."

        # Tiempo transcurrido dentro del clip en segundos reales del medio original
        dt_effective = split_time - clip.start_time
        dt_source = dt_effective * clip.speed

        # Segmento 1: Recortar out_point
        old_out = clip.out_point
        clip.out_point = clip.in_point + dt_source

        # Segmento 2: Nuevo clip
        new_clip = clip.clone(new_id=str(uuid.uuid4())[:8])
        new_clip.name = f"{clip.name} (Parte 2)"
        new_clip.in_point = clip.out_point
        new_clip.out_point = old_out
        new_clip.start_time = split_time

        # Insertar en la lista correspondiente tras el clip original
        if clip in self.video_clips:
            idx = self.video_clips.index(clip)
            self.video_clips.insert(idx + 1, new_clip)
            self.repack_video_clips()
        elif clip in self.overlay_clips:
            idx = self.overlay_clips.index(clip)
            self.overlay_clips.insert(idx + 1, new_clip)
        elif clip in self.audio_clips:
            idx = self.audio_clips.index(clip)
            self.audio_clips.insert(idx + 1, new_clip)

        self.selected_clip_id = new_clip.clip_id
        return True, f"Clip '{clip.name}' dividido exitosamente en {split_time:.2f}s."

    def change_clip_speed(self, clip_id: str, new_speed: float) -> bool:
        """Modifica la velocidad del clip y reajusta la línea de tiempo."""
        clip = self.get_clip_by_id(clip_id)
        if not clip:
            return False
        clip.speed = max(0.25, min(new_speed, 4.0))
        if clip in self.video_clips:
            self.repack_video_clips()
        return True

    def move_clip_order(self, clip_id: str, direction: int) -> bool:
        """
        Mueve un clip en su lista de orden (direction: -1 izquierda/arriba, +1 derecha/abajo).
        """
        clip = self.get_clip_by_id(clip_id)
        if not clip or clip not in self.video_clips:
            return False

        idx = self.video_clips.index(clip)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.video_clips):
            self.video_clips[idx], self.video_clips[new_idx] = (
                self.video_clips[new_idx],
                self.video_clips[idx]
            )
            self.repack_video_clips()
            return True
        return False

    def get_total_duration(self) -> float:
        """Retorna la duración total del proyecto considerando todas las pistas."""
        durations = [0.0]
        if self.video_clips:
            durations.append(max(c.end_time for c in self.video_clips))
        if self.overlay_clips:
            durations.append(max(c.end_time for c in self.overlay_clips))
        if self.audio_clips:
            durations.append(max(c.end_time for c in self.audio_clips))
        return max(durations)

    def clear_all(self):
        """Limpia todas las pistas del proyecto."""
        self.video_clips.clear()
        self.overlay_clips.clear()
        self.audio_clips.clear()
        self.selected_clip_id = None


class CompositorEngine:
    """
    Motor gráfico encargado de renderizar fotogramas de previsualización (vía Pillow)
    y estructurar la composición para la exportación final (vía MoviePy 2.x).
    """

    @staticmethod
    def apply_pil_filters(img: Image.Image, filters: Dict[str, any]) -> Image.Image:
        """Aplica filtros visuales y transformaciones a una imagen Pillow."""
        res = img

        # Presets de color
        preset = filters.get('preset', 'normal')
        if preset == 'bw':
            res = res.convert('L').convert('RGB')
        elif preset == 'sepia':
            sepia_matrix = (
                0.393, 0.769, 0.189, 0,
                0.349, 0.686, 0.168, 0,
                0.272, 0.534, 0.131, 0
            )
            res = res.convert('RGB', sepia_matrix)
        elif preset == 'invert':
            res = ImageOps.invert(res.convert('RGB'))

        # Brillo (-0.5 a +0.5 -> factor 0.5 a 1.5)
        bright_val = filters.get('brightness', 0.0)
        if abs(bright_val) > 0.01:
            factor = max(0.1, 1.0 + bright_val)
            res = ImageEnhance.Brightness(res).enhance(factor)

        # Contraste (0.5 a 2.0)
        contrast_val = filters.get('contrast', 1.0)
        if abs(contrast_val - 1.0) > 0.01:
            res = ImageEnhance.Contrast(res).enhance(contrast_val)

        # Saturación (0.0 a 2.0)
        sat_val = filters.get('saturation', 1.0)
        if abs(sat_val - 1.0) > 0.01:
            res = ImageEnhance.Color(res).enhance(sat_val)

        # Espejo horizontal (Flip H)
        if filters.get('flip_h', False):
            res = res.transpose(Image.FLIP_LEFT_RIGHT)

        # Rotación
        rot_val = filters.get('rotation', 0)
        if rot_val in (90, 180, 270):
            res = res.rotate(-rot_val, expand=True)

        return res

    @staticmethod
    def draw_overlay_on_image(base_img: Image.Image, overlay_clip: TimelineClip) -> Image.Image:
        """Dibuja texto o marca de agua sobre la imagen base."""
        data = overlay_clip.overlay_data
        text = data.get('text', '')
        if not text:
            return base_img

        font_size = data.get('font_size', 36)
        text_color = data.get('text_color', '#FFFFFF')
        pos_preset = data.get('pos_preset', 'bottom')
        bg_style = data.get('bg_style', 'box')
        opacity = max(0.1, min(data.get('opacity', 1.0), 1.0))

        W, H = base_img.size
        overlay_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay_layer)

        # Cargar tipografía del sistema o predeterminada
        font = None
        for font_name in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
            try:
                font = ImageFont.truetype(font_name, font_size)
                break
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()

        # Calcular tamaño del texto
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x, pad_y = 16, 10
        bw = tw + pad_x * 2
        bh = th + pad_y * 2

        # Calcular posición según preset
        if pos_preset == 'center':
            x = (W - bw) // 2
            y = (H - bh) // 2
        elif pos_preset == 'top':
            x = (W - bw) // 2
            y = int(H * 0.08)
        elif pos_preset == 'watermark_tr':
            x = W - bw - 20
            y = 20
        elif pos_preset == 'watermark_br':
            x = W - bw - 20
            y = H - bh - 20
        else: # 'bottom'
            x = (W - bw) // 2
            y = H - bh - int(H * 0.08)

        # Caja de fondo
        if bg_style == 'box':
            alpha_box = int(190 * opacity)
            draw.rounded_rectangle(
                [x, y, x + bw, y + bh],
                radius=10,
                fill=(15, 15, 18, alpha_box),
                outline=(0, 210, 196, int(150 * opacity)),
                width=1
            )

        # Texto con color y alfa
        alpha_text = int(255 * opacity)
        rgb_color = CompositorEngine.parse_hex_color(text_color)
        draw.text((x + pad_x, y + pad_y - bbox[1]), text, font=font, fill=(*rgb_color, alpha_text))

        composed = Image.alpha_composite(base_img.convert('RGBA'), overlay_layer)
        return composed.convert('RGB')

    @staticmethod
    def parse_hex_color(color_str: str) -> Tuple[int, int, int]:
        color_str = color_str.lstrip('#')
        if len(color_str) == 6:
            try:
                return (
                    int(color_str[0:2], 16),
                    int(color_str[2:4], 16),
                    int(color_str[4:6], 16)
                )
            except ValueError:
                pass
        return (255, 255, 255)

    @staticmethod
    def get_preview_frame(
        model: TimelineModel,
        time_pos: float,
        aspect_ratio: str,
        canvas_w: int,
        canvas_h: int
    ) -> Image.Image:
        """
        Genera el fotograma exacto compuesto para la pantalla del monitor a un aspect ratio dado.
        """
        # 1. Determinar tamaño base según la relación de aspecto elegida
        if aspect_ratio == "16:9":
            target_aspect = 16.0 / 9.0
        elif aspect_ratio == "9:16":
            target_aspect = 9.0 / 16.0
        elif aspect_ratio == "1:1":
            target_aspect = 1.0
        else:
            target_aspect = 16.0 / 9.0

        # Encontrar clip de video activo
        active_v_clip = None
        for clip in model.video_clips:
            if clip.start_time <= time_pos <= clip.end_time:
                active_v_clip = clip
                break

        # Renderizar fondo o frame base
        if active_v_clip and active_v_clip.asset:
            # Calcular tiempo interno dentro del archivo fuente
            internal_dt = (time_pos - active_v_clip.start_time) * active_v_clip.speed
            clip_t = active_v_clip.in_point + internal_dt
            raw_frame = active_v_clip.asset.get_frame(clip_t)
            if raw_frame is not None:
                base_img = Image.fromarray(raw_frame)
            else:
                base_img = CompositorEngine.create_placeholder(640, 360, "Sin fotograma")
            # Aplicar filtros del clip
            base_img = CompositorEngine.apply_pil_filters(base_img, active_v_clip.filters)
        else:
            # Monitor en reposo / sin clip en ese segundo
            base_img = CompositorEngine.create_idle_monitor(640, 360, time_pos)

        # 2. Aplicar superposiciones activas en time_pos
        for o_clip in model.overlay_clips:
            if o_clip.start_time <= time_pos <= o_clip.end_time:
                base_img = CompositorEngine.draw_overlay_on_image(base_img, o_clip)

        # 3. Ajustar al Canvas manteniendo el aspect ratio con barras de encuadre profesional
        canvas_aspect = canvas_w / max(1, canvas_h)
        if canvas_aspect > target_aspect:
            # El canvas es más ancho que el objetivo: limitante es la altura
            frame_h = int(canvas_h * 0.95)
            frame_w = int(frame_h * target_aspect)
        else:
            # Limitante es el ancho
            frame_w = int(canvas_w * 0.95)
            frame_h = int(frame_w / target_aspect)

        frame_w = max(10, frame_w)
        frame_h = max(10, frame_h)

        scaled_img = base_img.resize((frame_w, frame_h), Image.Resampling.BILINEAR)

        # Crear lienzo final negro/mate centrado
        final_canvas = Image.new('RGB', (canvas_w, canvas_h), (18, 18, 20))
        offset_x = (canvas_w - frame_w) // 2
        offset_y = (canvas_h - frame_h) // 2
        final_canvas.paste(scaled_img, (offset_x, offset_y))

        # Dibujar sutil borde neón en el área de video activa
        draw = ImageDraw.Draw(final_canvas)
        draw.rectangle(
            [offset_x - 1, offset_y - 1, offset_x + frame_w, offset_y + frame_h],
            outline=(40, 40, 48),
            width=1
        )
        return final_canvas

    @staticmethod
    def create_idle_monitor(w: int, h: int, time_pos: float) -> Image.Image:
        """Crea una retícula moderna estilo estudio cuando no hay video activo."""
        img = Image.new('RGB', (w, h), (14, 14, 16))
        draw = ImageDraw.Draw(img)
        # Retícula sutil
        for x in range(0, w, 40):
            draw.line([(x, 0), (x, h)], fill=(24, 24, 28), width=1)
        for y in range(0, h, 40):
            draw.line([(0, y), (w, y)], fill=(24, 24, 28), width=1)

        # Mira central
        cx, cy = w // 2, h // 2
        draw.line([(cx - 25, cy), (cx + 25, cy)], fill=(0, 210, 196), width=1)
        draw.line([(cx, cy - 25), (cx, cy + 25)], fill=(0, 210, 196), width=1)
        draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], outline=(0, 210, 196), width=1)

        time_str = f"{int(time_pos//60):02d}:{int(time_pos%60):02d}.{int((time_pos%1)*100):02d}"
        draw.text((cx - 55, cy + 35), "CapCut Pro Monitor", fill=(160, 160, 170))
        draw.text((cx - 30, cy + 55), time_str, fill=(0, 210, 196))
        return img

    @staticmethod
    def create_placeholder(w: int, h: int, label: str) -> Image.Image:
        img = Image.new('RGB', (w, h), (25, 25, 30))
        draw = ImageDraw.Draw(img)
        draw.text((w // 2 - 40, h // 2 - 10), label, fill=(200, 200, 200))
        return img

    @staticmethod
    def build_export_composition(
        model: TimelineModel,
        target_res: Tuple[int, int],
        aspect_ratio: str = "16:9"
    ) -> Tuple[Optional[any], float]:
        """
        Construye el grafo de composición final de MoviePy 2.x para renderizar en disco.
        """
        if not model.video_clips and not model.audio_clips:
            return None, 0.0

        target_w, target_h = target_res
        processed_video_clips = []

        # 1. Procesar clips de video principales
        for v_clip in model.video_clips:
            if not v_clip.asset:
                continue

            # Subclip según in y out points
            sub = v_clip.asset.get_clip_obj().subclipped(v_clip.in_point, v_clip.out_point)

            # Velocidad
            if abs(v_clip.speed - 1.0) > 0.02:
                sub = sub.with_effects([vfx.MultiplySpeed(v_clip.speed)])

            # Ajustes de audio en el clip
            if v_clip.is_muted or v_clip.volume <= 0.01:
                sub = sub.without_audio()
            elif sub.audio is not None and abs(v_clip.volume - 1.0) > 0.05:
                sub = sub.with_volume_scaled(v_clip.volume)

            # Filtros visuales (aplicados con PIL mediante image_transform)
            filters = v_clip.filters
            if (
                filters.get('preset') != 'normal'
                or abs(filters.get('brightness', 0.0)) > 0.01
                or abs(filters.get('contrast', 1.0) - 1.0) > 0.01
                or abs(filters.get('saturation', 1.0) - 1.0) > 0.01
                or filters.get('flip_h', False)
                or filters.get('rotation', 0) != 0
            ):
                def make_filter_fn(f_dict):
                    def _filter_frame(frame_np):
                        pil_img = Image.fromarray(frame_np)
                        filtered = CompositorEngine.apply_pil_filters(pil_img, f_dict)
                        return np.array(filtered)
                    return _filter_frame
                sub = sub.image_transform(make_filter_fn(filters))

            # Escalar y centrar en la resolución de destino preservando relación de aspecto
            scale = min(target_w / sub.w, target_h / sub.h)
            new_w = int(sub.w * scale)
            new_h = int(sub.h * scale)
            # Asegurar dimensiones pares para H.264
            new_w = new_w if new_w % 2 == 0 else new_w - 1
            new_h = new_h if new_h % 2 == 0 else new_h - 1

            sub_scaled = sub.resized((new_w, new_h)).with_position(('center', 'center'))

            # Lienzo base negro para letterbox
            bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=sub.duration)
            framed_clip = CompositeVideoClip([bg, sub_scaled]).with_start(v_clip.start_time)
            processed_video_clips.append(framed_clip)

        # 2. Ensamblar pista principal
        if processed_video_clips:
            main_composition = CompositeVideoClip(processed_video_clips, size=target_res)
        else:
            total_dur = model.get_total_duration() or 5.0
            main_composition = ColorClip(size=target_res, color=(0, 0, 0), duration=total_dur)

        total_duration = main_composition.duration

        # 3. Superponer elementos de texto / títulos
        overlay_clips_mpy = []
        for o_clip in model.overlay_clips:
            # Crear imagen PIL de la superposición
            dummy_img = Image.new('RGB', target_res, (0, 0, 0))
            overlay_composed = CompositorEngine.draw_overlay_on_image(dummy_img, o_clip)

            # Extraer canal alfa del texto generado
            data = o_clip.overlay_data
            text = data.get('text', '')
            if not text:
                continue

            # Convertir a ImageClip transparente con duración y tiempo de inicio
            arr = np.array(overlay_composed)
            # Para evitar fondo negro opaco, creamos un frame transparente con PIL
            W, H = target_res
            transparent_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            # Dibujar directamente en la capa transparente
            # Cargar fuente
            font = None
            for font_name in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
                try:
                    font = ImageFont.truetype(font_name, data.get('font_size', 36))
                    break
                except Exception:
                    pass
            if font is None:
                font = ImageFont.load_default()

            draw = ImageDraw.Draw(transparent_layer)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            pad_x, pad_y = 16, 10
            bw, bh = tw + pad_x * 2, th + pad_y * 2

            pos_preset = data.get('pos_preset', 'bottom')
            if pos_preset == 'center':
                x, y = (W - bw) // 2, (H - bh) // 2
            elif pos_preset == 'top':
                x, y = (W - bw) // 2, int(H * 0.08)
            elif pos_preset == 'watermark_tr':
                x, y = W - bw - 20, 20
            elif pos_preset == 'watermark_br':
                x, y = W - bw - 20, H - bh - 20
            else:
                x, y = (W - bw) // 2, H - bh - int(H * 0.08)

            opacity = max(0.1, min(data.get('opacity', 1.0), 1.0))
            if data.get('bg_style', 'box') == 'box':
                draw.rounded_rectangle(
                    [x, y, x + bw, y + bh],
                    radius=10,
                    fill=(15, 15, 18, int(190 * opacity)),
                    outline=(0, 210, 196, int(150 * opacity)),
                    width=1
                )
            rgb_col = CompositorEngine.parse_hex_color(data.get('text_color', '#FFFFFF'))
            draw.text((x + pad_x, y + pad_y - bbox[1]), text, font=font, fill=(*rgb_col, int(255 * opacity)))

            txt_arr = np.array(transparent_layer)
            txt_clip = (
                ImageClip(txt_arr, is_mask=False)
                .with_start(o_clip.start_time)
                .with_duration(o_clip.duration)
            )
            overlay_clips_mpy.append(txt_clip)

        if overlay_clips_mpy:
            main_composition = CompositeVideoClip([main_composition] + overlay_clips_mpy, size=target_res)

        # 4. Mezclar pista de audio secundaria (música de fondo)
        audio_tracks = []
        if main_composition.audio is not None:
            audio_tracks.append(main_composition.audio)

        for a_clip in model.audio_clips:
            if not a_clip.asset:
                continue
            snd = a_clip.asset.get_clip_obj().subclipped(a_clip.in_point, a_clip.out_point)
            if a_clip.is_muted or a_clip.volume <= 0.01:
                continue
            snd = snd.with_start(a_clip.start_time).with_volume_scaled(a_clip.volume)
            audio_tracks.append(snd)

        if audio_tracks:
            final_audio = CompositeAudioClip(audio_tracks)
            main_composition = main_composition.with_audio(final_audio)

        return main_composition, total_duration
