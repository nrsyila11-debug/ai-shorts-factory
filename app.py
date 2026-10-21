import asyncio, os, re, subprocess, tempfile, textwrap
from pathlib import Path

import streamlit as st
import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont
import numpy as np

st.set_page_config(page_title="AI Shorts Factory", page_icon="🎬", layout="centered")
st.title("🎬 AI Shorts Factory")
st.caption("Buat video vertikal faceless dari naskah, suara AI, visual gradasi, dan subtitle.")

DEFAULT_SCRIPT = """Pernah merasa tertinggal dari semua orang?
Kamu melihat mereka sudah sampai di tempat yang kamu impikan, sementara kamu masih berusaha mengumpulkan tenaga.
Tapi hidup bukan perlombaan dengan garis akhir yang sama.
Ada hal-hal yang memang butuh waktu lebih lama untuk tumbuh.
Jangan meremehkan langkah kecilmu hari ini.
Kamu tetap bergerak, dan itu berarti."""

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def wrap_words(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0,0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current: lines.append(current)
            current = word
    if current: lines.append(current)
    return lines

def make_scene(text, idx, out_path, width=720, height=1280):
    # Procedural gradient background; no external footage or stock-media licensing dependency.
    y, x = np.mgrid[0:height, 0:width]
    palettes = [
        (12, 22, 42, 42, 22, 48),
        (18, 32, 50, 50, 24, 38),
        (22, 20, 42, 34, 32, 58),
        (15, 34, 40, 42, 20, 45),
        (30, 22, 35, 12, 30, 52),
    ]
    a,b,c,d,e,f = palettes[idx % len(palettes)]
    t = (y / max(1, height-1))[...,None]
    top = np.array([a,b,c], dtype=np.float32)
    bot = np.array([d,e,f], dtype=np.float32)
    arr = top*(1-t) + bot*t
    glow = np.exp(-(((x-width*0.72)/(width*0.55))**2 + ((y-height*0.26)/(height*0.32))**2))[...,None]
    arr = np.clip(arr + glow*28, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    # subtle decorative ring
    draw.ellipse((width*0.56, height*0.12, width*1.02, height*0.43), outline=(255,255,255,35), width=3)
    draw.rectangle((48, 110, 54, 180), fill=(238, 204, 145, 230))
    font = get_font(43, True)
    lines = wrap_words(draw, text, font, width-120)
    line_h = 61
    total_h = len(lines)*line_h
    start_y = int(height*0.43 - total_h/2)
    # dark translucent backing for readability
    draw.rounded_rectangle((42, start_y-35, width-42, start_y+total_h+45), radius=26, fill=(0,0,0,75), outline=(255,255,255,28), width=2)
    for j, line in enumerate(lines):
        bbox = draw.textbbox((0,0), line, font=font, stroke_width=1)
        tw = bbox[2]-bbox[0]
        draw.text(((width-tw)/2, start_y+j*line_h), line, font=font, fill=(255,255,255,255), stroke_width=1, stroke_fill=(0,0,0,120))
    footer = "CERITA KECIL • PROSES BESAR"
    ff = get_font(19, False)
    draw.text((48, height-85), footer, font=ff, fill=(255,255,255,170))
    img.save(out_path, quality=95)

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-2500:])
    return p

async def make_voice(text, voice, output):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)

def generate_video(script, voice, title, progress):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"(?<=[.!?])\s+|\n+", script) if p.strip()]
    if not paragraphs:
        raise ValueError("Masukkan naskah terlebih dahulu.")
    # Limit scenes for cloud CPU and reasonable output size.
    paragraphs = paragraphs[:12]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        audio = td/"voice.mp3"
        asyncio.run(make_voice(" ".join(paragraphs), voice, str(audio)))
        # Approximate total duration from TTS file via ffprobe.
        probe = run([ffmpeg, "-i", str(audio), "-f", "null", "-"])
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", probe.stderr)
        if m:
            duration = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
        else:
            duration = max(12, len(script.split())/2.5)
        duration = max(8.0, duration)
        # Each sentence is a scene, with a cap to keep free hosting practical.
        weights = [max(1, len(p.split())) for p in paragraphs]
        total = sum(weights)
        durations = [max(1.8, duration*w/total) for w in weights]
        # Normalize scene durations to audio length.
        factor = duration/sum(durations)
        durations = [d*factor for d in durations]
        concat = td/"scenes.txt"
        with open(concat, "w", encoding="utf-8") as f:
            for i, para in enumerate(paragraphs):
                png = td/f"scene_{i:02d}.png"
                make_scene(para, i, png)
                f.write(f"file '{png.as_posix()}'\n")
                f.write(f"duration {durations[i]:.3f}\n")
            f.write(f"file '{(td/f'scene_{len(paragraphs)-1:02d}.png').as_posix()}'\n")
        silent = td/"silent.mp4"
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(silent)])
        out = td/"ai_shorts.mp4"
        run([ffmpeg, "-y", "-i", str(silent), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)])
        data = out.read_bytes()
    return data

with st.form("generator"):
    topic = st.text_input("Tema / judul video", "Proses yang tidak dilihat orang")
    script = st.text_area("Naskah (satu kalimat per adegan)", DEFAULT_SCRIPT, height=220)
    voice = st.selectbox("Suara AI Bahasa Indonesia", [
        "id-ID-GadisNeural", "id-ID-ArdiNeural"
    ], index=0)
    submitted = st.form_submit_button("✨ Generate video MP4", type="primary", use_container_width=True)

if submitted:
    if len(script.strip()) < 30:
        st.error("Naskah terlalu pendek. Tambahkan beberapa kalimat.")
    else:
        with st.spinner("Membuat narasi AI dan merender video. Jangan tutup halaman dulu; proses dapat memerlukan beberapa menit."):
            try:
                video_bytes = generate_video(script.strip(), voice, topic)
                st.success("Video berhasil dibuat.")
                st.video(video_bytes)
                safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", topic).strip("_")[:48] or "ai_shorts"
                st.download_button("⬇️ Download video MP4", video_bytes, file_name=f"{safe}.mp4", mime="video/mp4", use_container_width=True)
            except Exception as e:
                st.error("Pembuatan video gagal. Coba naskah lebih pendek atau pilih suara lain.")
                st.code(str(e))

with st.expander("Batasan versi gratis"):
    st.write("- Visual dibuat otomatis dari latar gradasi dan teks, jadi belum memakai footage sinematik eksternal.")
    st.write("- Suara memakai layanan text-to-speech online; ketersediaan layanan bisa berubah.")
    st.write("- Hosting gratis dapat tidur saat tidak digunakan dan file hasil perlu diunduh sebelum sesi berakhir.")
    st.write("- Periksa hak penggunaan audio/visual dan kebijakan monetisasi platform sebelum upload.")
