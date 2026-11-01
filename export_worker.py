"""
export_worker.py - Módulo de Renderizado Concurrente, Progreso y Cancelación Inmediata.
Utiliza MoviePy 2.x, proglog, psutil y threading con queue.Queue para mantener la UI fluida a 60 FPS.
"""

import os
import time
import queue
import threading
from typing import Dict, Any, Optional
import psutil
import proglog

from editor_core import TimelineModel, CompositorEngine


class RenderCancelledException(Exception):
    """Excepción lanzada cuando el usuario pulsa 🛑 Cancelar Exportación."""
    pass


class UIProgressLogger(proglog.ProgressBarLogger):
    """
    Captura los eventos de renderizado de MoviePy/FFmpeg y los despacha
    a una cola segura de hilos (queue.Queue) para consumo por la interfaz CustomTkinter.
    Monitorea de forma síncrona el evento threading.Event de cancelación.
    """
    def __init__(self, event_queue: queue.Queue, cancel_event: threading.Event):
        super().__init__()
        self.queue = event_queue
        self.cancel_event = cancel_event
        self.total_frames = 1
        self.current_frame = 0
        self.start_time = time.time()
        self.last_update_time = 0.0

    def bars_callback(self, bar, attr, value, old_value=None):
        # 1. Comprobación crítica de cancelación
        if self.cancel_event.is_set():
            raise RenderCancelledException("Exportación abortada por solicitud del usuario.")

        # 2. Captura de cuadros de renderizado
        if attr == 'total':
            if value and value > 0:
                self.total_frames = max(1, int(value))
        elif attr == 'index':
            self.current_frame = int(value)
            now = time.time()
            
            # Limitar actualizaciones a ~20 por segundo para no saturar la cola de la UI
            if (now - self.last_update_time >= 0.05) or (self.current_frame == self.total_frames):
                self.last_update_time = now
                elapsed = max(0.01, now - self.start_time)
                pct = min(100.0, (self.current_frame / self.total_frames) * 100.0)
                fps_render = self.current_frame / elapsed
                rem_frames = max(0, self.total_frames - self.current_frame)
                eta_sec = rem_frames / fps_render if fps_render > 0.1 else 0
                eta_str = f"{int(eta_sec // 60):02d}:{int(eta_sec % 60):02d}"

                self.queue.put({
                    'type': 'progress',
                    'percentage': pct,
                    'frame': self.current_frame,
                    'total_frames': self.total_frames,
                    'fps': fps_render,
                    'eta': eta_str
                })

    def callback(self, **changes):
        # Captura de mensajes de proglog
        if self.cancel_event.is_set():
            raise RenderCancelledException("Exportación abortada por solicitud del usuario.")
        message = changes.get('message', None)
        if message:
            self.queue.put({
                'type': 'log',
                'level': 'RENDER',
                'message': str(message).strip()
            })


class ExportWorker(threading.Thread):
    """
    Hilo de trabajo secundario para la exportación de video sin congelar la interfaz gráfica.
    Controla la limpieza de archivos temporales y la finalización forzosa de procesos FFmpeg.
    """
    def __init__(
        self,
        timeline_model: TimelineModel,
        export_config: Dict[str, Any],
        event_queue: queue.Queue,
        cancel_event: threading.Event
    ):
        super().__init__(name="ExportWorkerThread", daemon=True)
        self.model = timeline_model
        self.config = export_config
        self.queue = event_queue
        self.cancel_event = cancel_event
        self.output_path = os.path.abspath(export_config.get('output_path', 'output.mp4'))

    def run(self):
        start_time = time.time()
        self._log("INFO", f"Iniciando motor de exportación para: {os.path.basename(self.output_path)}")
        self._log("INFO", f"Configuración: Formato={self.config.get('format')} | Res={self.config.get('resolution_name')} | FPS={self.config.get('fps')} | Calidad={self.config.get('quality')}")

        try:
            # 1. Comprobar cancelación temprana
            if self.cancel_event.is_set():
                raise RenderCancelledException()

            # 2. Resolver resolución
            res_tuple = self.config.get('resolution', (1920, 1080))
            fps = int(self.config.get('fps', 30))
            fmt = self.config.get('format', '.mp4').lower()
            quality = self.config.get('quality', 'Media')

            # Asegurar directorio de destino
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            # 3. Construir la composición MoviePy
            self._log("INFO", "Compilando grafo de clips, efectos de color y pistas de audio...")
            composite_clip, total_duration = CompositorEngine.build_export_composition(
                self.model,
                res_tuple,
                self.config.get('aspect_ratio', '16:9')
            )

            if composite_clip is None:
                raise ValueError("No hay clips válidos en la línea de tiempo para exportar.")

            self._log("INFO", f"Composición lista: Duración={total_duration:.2f}s, Fotogramas estimados={int(total_duration * fps)}")

            # 4. Configurar logger de progreso
            logger = UIProgressLogger(self.queue, self.cancel_event)

            # 5. Ejecutar renderizado según formato seleccionado
            if fmt == '.mp3':
                self._log("RENDER", "Exportando únicamente la pista de audio consolidada...")
                if composite_clip.audio is None:
                    raise ValueError("El proyecto actual no contiene pistas de audio.")
                composite_clip.audio.write_audiofile(
                    self.output_path,
                    fps=44100,
                    logger=logger
                )
            elif fmt == '.gif':
                self._log("RENDER", "Generando animación GIF de alta fidelidad...")
                composite_clip.write_gif(
                    self.output_path,
                    fps=min(fps, 15),
                    logger=logger
                )
            else:
                # Video MP4 o MOV
                bitrate_map = {
                    'Alta': '8000k',
                    'Media': '4000k',
                    'Rápida': '2000k'
                }
                preset_map = {
                    'Alta': 'medium',
                    'Media': 'fast',
                    'Rápida': 'veryfast'
                }
                bitrate = bitrate_map.get(quality, '4000k')
                ffmpeg_preset = preset_map.get(quality, 'fast')

                self._log("RENDER", f"Iniciando codificación H.264/AAC [Bitrate={bitrate}, Preset={ffmpeg_preset}]...")
                composite_clip.write_videofile(
                    self.output_path,
                    fps=fps,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate=bitrate,
                    preset=ffmpeg_preset,
                    threads=max(1, os.cpu_count() - 1),
                    logger=logger
                )

            # 6. Comprobar si se canceló al final
            if self.cancel_event.is_set():
                raise RenderCancelledException()

            elapsed_total = time.time() - start_time
            file_size_mb = os.path.getsize(self.output_path) / (1024 * 1024) if os.path.exists(self.output_path) else 0.0

            self._log("SUCCESS", f"¡Renderizado completado con éxito en {elapsed_total:.2f}s! Tamaño: {file_size_mb:.2f} MB")
            self.queue.put({
                'type': 'complete',
                'output_path': self.output_path,
                'duration': total_duration,
                'filesize_mb': file_size_mb,
                'elapsed': elapsed_total
            })

        except RenderCancelledException:
            self._handle_cancellation()
        except Exception as e:
            self._log("ERROR", f"Fallo crítico durante el renderizado: {str(e)}")
            self.queue.put({
                'type': 'error',
                'error': str(e)
            })
            self._cleanup_partial_file()

    def _handle_cancellation(self):
        """Detiene subprocesos FFmpeg y limpia archivos parciales."""
        self._log("WARNING", "Detención forzosa solicitada. Terminando subprocesos FFmpeg y limpiando temporales...")
        self._terminate_ffmpeg_subprocesses()
        self._cleanup_partial_file()
        self._log("WARNING", "Proceso de exportación cancelado correctamente.")
        self.queue.put({'type': 'cancelled'})

    def _terminate_ffmpeg_subprocesses(self):
        """Localiza y termina cualquier proceso FFmpeg hijo generado por la app."""
        try:
            current_proc = psutil.Process()
            for child in current_proc.children(recursive=True):
                try:
                    if 'ffmpeg' in child.name().lower() or 'ffprobe' in child.name().lower():
                        self._log("INFO", f"Terminando proceso FFmpeg huérfano (PID: {child.pid})")
                        child.terminate()
                        child.wait(timeout=1.5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    try:
                        child.kill()
                    except Exception:
                        pass
        except Exception as e:
            self._log("WARNING", f"Aviso al terminar subprocesos: {e}")

    def _cleanup_partial_file(self):
        """Elimina el archivo de salida incompleto para evitar archivos corruptos."""
        time.sleep(0.3)
        if os.path.exists(self.output_path):
            try:
                os.remove(self.output_path)
                self._log("INFO", f"Archivo temporal eliminado: {os.path.basename(self.output_path)}")
            except Exception as e:
                self._log("WARNING", f"No se pudo eliminar archivo temporal {self.output_path}: {e}")

    def _log(self, level: str, message: str):
        self.queue.put({
            'type': 'log',
            'level': level,
            'message': message
        })
