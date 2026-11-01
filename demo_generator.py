"""
demo_generator.py - Generador Autónomo de Medios de Prueba.
Crea clips de video sintetizados, audio estéreo y marcas de agua PNG
para que el usuario pueda probar el editor de inmediato sin buscar archivos locales.
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
from moviepy.audio.AudioClip import AudioArrayClip


def ensure_demo_media(target_dir: str = "demo_assets") -> dict:
    """
    Verifica o genera los archivos de muestra en target_dir.
    Retorna un diccionario con las rutas generadas.
    """
    target_dir = os.path.abspath(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    clip1_path = os.path.join(target_dir, "clip1_synthwave.mp4")
    clip2_path = os.path.join(target_dir, "clip2_geometric.mp4")
    music_path = os.path.join(target_dir, "demo_music.mp3")
    logo_path = os.path.join(target_dir, "watermark_pro.png")

    results = {
        'clip1': clip1_path,
        'clip2': clip2_path,
        'music': music_path,
        'logo': logo_path
    }

    # 1. Clip 1: Synthwave Neon Video (3.5s)
    if not os.path.exists(clip1_path):
        _generate_synthwave_clip(clip1_path, duration=3.5, fps=20, w=1280, h=720)

    # 2. Clip 2: Geometric Shapes Video (3.0s)
    if not os.path.exists(clip2_path):
        _generate_geometric_clip(clip2_path, duration=3.0, fps=20, w=1280, h=720)

    # 3. Audio de fondo melódico (8.0s)
    if not os.path.exists(music_path):
        _generate_synth_audio(music_path, duration=8.0, sample_rate=44100)

    # 4. Marca de agua transparente PNG
    if not os.path.exists(logo_path):
        _generate_logo_png(logo_path, w=320, h=90)

    return results


def _generate_synthwave_clip(out_path: str, duration: float = 3.5, fps: int = 20, w: int = 1280, h: int = 720):
    total_frames = int(duration * fps)
    frames = []

    font = None
    for fn in ("segoeui.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(fn, 32)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    for idx in range(total_frames):
        t = idx / fps
        im = Image.new('RGB', (w, h), (14, 14, 20))
        draw = ImageDraw.Draw(im)

        # Rejilla de perspectiva inferior estilo synthwave
        horizon = int(h * 0.55)
        draw.line([(0, horizon), (w, horizon)], fill=(0, 210, 196), width=2)
        for i in range(15):
            x_bottom = int(w * (i / 14))
            draw.line([(w // 2, horizon), (x_bottom, h)], fill=(40, 30, 70), width=1)
        for j in range(6):
            y_line = int(horizon + (h - horizon) * (j / 5.5)**1.5)
            draw.line([(0, y_line), (w, y_line)], fill=(50, 40, 85), width=1)

        # Sol de neón de fondo
        sun_radius = 80
        sun_cx, sun_cy = w // 2, horizon - 20
        draw.ellipse(
            [sun_cx - sun_radius, sun_cy - sun_radius, sun_cx + sun_radius, sun_cy + sun_radius],
            fill=(255, 60, 130)
        )
        # Líneas de corte en el sol
        for sl in range(4):
            ly = sun_cy + 10 + sl * 15
            draw.line([(sun_cx - sun_radius, ly), (sun_cx + sun_radius, ly)], fill=(14, 14, 20), width=4)

        # Esfera neón cian en movimiento orbital
        ball_x = int(w // 2 + (w * 0.35) * math.sin(t * 3.5))
        ball_y = int(horizon - 70 + 40 * math.cos(t * 3.5))
        r = 30
        draw.ellipse([ball_x - r, ball_y - r, ball_x + r, ball_y + r], fill=(0, 210, 196), outline=(255, 255, 255), width=2)

        # Insignia de texto
        draw.text((40, 40), f"⚡ DEMO CLIP 1 - {t:.2f}s", font=font, fill=(255, 255, 255))
        frames.append(np.array(im))

    clip = ImageSequenceClip(frames, fps=fps)

    # Audio sintetizado con arpegio
    sr = 44100
    t_a = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Secuencia de frecuencias 440, 554.37, 659.25
    freq = 440.0 + 100.0 * np.sin(2 * np.pi * 1.5 * t_a)
    wave = 0.15 * np.sin(2 * np.pi * freq * t_a)
    stereo = np.column_stack([wave, wave])
    clip.audio = AudioArrayClip(stereo, fps=sr)

    clip.write_videofile(out_path, fps=fps, codec='libx264', audio_codec='aac', logger=None)
    clip.close()


def _generate_geometric_clip(out_path: str, duration: float = 3.0, fps: int = 20, w: int = 1280, h: int = 720):
    total_frames = int(duration * fps)
    frames = []

    font = None
    for fn in ("segoeui.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(fn, 32)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    for idx in range(total_frames):
        t = idx / fps
        im = Image.new('RGB', (w, h), (18, 22, 35))
        draw = ImageDraw.Draw(im)

        # Anillos concéntricos rotatorios
        cx, cy = w // 2, h // 2
        for ring_i in range(1, 5):
            radius = ring_i * 60
            angle_offset = t * (ring_i * 1.2)
            for pt in range(6):
                ang = angle_offset + pt * (2 * math.pi / 6)
                px = int(cx + radius * math.cos(ang))
                py = int(cy + radius * math.sin(ang))
                draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(123, 97, 255), outline=(0, 230, 118), width=1)

        # Rombo central con gradiente de tamaño
        d_size = int(50 + 20 * math.sin(t * 4))
        poly = [(cx, cy - d_size), (cx + d_size, cy), (cx, cy + d_size), (cx - d_size, cy)]
        draw.polygon(poly, fill=(0, 210, 196), outline=(255, 255, 255))

        draw.text((40, 40), f"🎨 DEMO CLIP 2 - DINAMISMO ({t:.2f}s)", font=font, fill=(0, 230, 118))
        frames.append(np.array(im))

    clip = ImageSequenceClip(frames, fps=fps)

    # Audio suave sintetizado
    sr = 44100
    t_a = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = 0.15 * np.sin(2 * np.pi * 329.63 * t_a) * (1.0 + 0.3 * np.sin(2 * np.pi * 3 * t_a))
    stereo = np.column_stack([wave, wave])
    clip.audio = AudioArrayClip(stereo, fps=sr)

    clip.write_videofile(out_path, fps=fps, codec='libx264', audio_codec='aac', logger=None)
    clip.close()


def _generate_synth_audio(out_path: str, duration: float = 8.0, sample_rate: int = 44100):
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Acorde sintetizado en progresión (Do Mayor / La menor)
    chord1 = 0.12 * np.sin(2 * np.pi * 261.63 * t)  # C4
    chord2 = 0.10 * np.sin(2 * np.pi * 329.63 * t)  # E4
    chord3 = 0.08 * np.sin(2 * np.pi * 392.00 * t)  # G4
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.8 * t)
    wave = (chord1 + chord2 + chord3) * lfo

    # Envolvente fade-in y fade-out
    fade_len = int(sample_rate * 0.5)
    wave[:fade_len] *= np.linspace(0, 1, fade_len)
    wave[-fade_len:] *= np.linspace(1, 0, fade_len)

    stereo = np.column_stack([wave, wave])
    audio_clip = AudioArrayClip(stereo, fps=sample_rate)
    audio_clip.write_audiofile(out_path, fps=sample_rate, logger=None)
    audio_clip.close()


def _generate_logo_png(out_path: str, w: int = 320, h: int = 90):
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Caja estilizada de marca
    draw.rounded_rectangle([5, 5, w - 5, h - 5], radius=16, fill=(15, 15, 20, 220), outline=(0, 210, 196, 255), width=2)
    
    font = None
    for fn in ("segoeui.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(fn, 28)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    draw.text((25, 28), "🎬 CAPCUT PRO", font=font, fill=(0, 210, 196, 255))
    draw.rectangle([250, 32, 290, 58], fill=(123, 97, 255, 255))
    draw.text((255, 36), "HD", fill=(255, 255, 255, 255))
    img.save(out_path, format='PNG')
