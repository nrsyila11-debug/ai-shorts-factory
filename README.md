---
title: AI Shorts Factory
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8501
pinned: false
---

# AI Shorts Factory

Generator video vertikal sederhana untuk quotes/storytelling berbahasa Indonesia.

## Deploy gratis

1. Buat akun GitHub dan Hugging Face jika belum punya.
2. Upload `app.py`, `requirements.txt`, `Dockerfile`, dan `README.md` ke sebuah repository GitHub.
3. Buka Streamlit Community Cloud: https://share.streamlit.io/
4. Hubungkan GitHub, pilih repository dan file `app.py`, lalu Deploy.
5. Tunggu build selesai, buka URL aplikasi dari HP/laptop.

Catatan: proyek ini ditargetkan untuk Streamlit Community Cloud. README Hugging Face ini hanya dokumentasi proyek; tidak perlu membuat Hugging Face Space jika menggunakan Streamlit Community Cloud.

## Fitur

- Naskah manual atau dibantu ChatGPT
- TTS bahasa Indonesia melalui edge-tts
- Visual gradasi dengan teks/subtitle per adegan
- Ekspor MP4 9:16

Versi awal ini sengaja memakai visual grafis otomatis, bukan mengunduh footage eksternal yang hak penggunaannya tidak pasti.
