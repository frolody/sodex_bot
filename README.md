# SoDEX Autonomous Trading Bot & Dashboard

Project ini terbagi menjadi dua bagian utama untuk memastikan skalabilitas dan kemudahan manajemen di VPS.

## 📁 Struktur Folder
- `/sodex-bot-python`: Otak trading bot berbasis Python. Menggunakan AI (Gemini & MiniMax/NVIDIA) untuk keputusan trading.
- `/sodex-dashboard-nextjs`: Antarmuka web modern berbasis Next.js untuk memantau performa bot secara real-time.

---

## 🚀 Cara Menjalankan

### 1. Bot Trading (Python)
Pastikan kamu berada di folder bot:
```bash
cd sodex-bot-python
python main.py
```

### 2. Dashboard (Next.js)
Buka terminal baru, masuk ke folder dashboard, dan jalankan server pengembangan:
```bash
cd sodex-dashboard-nextjs
npm run dev
```
Dashboard akan tersedia di: [http://localhost:3000](http://localhost:3000)

---

## 🛠 Teknologi
- **Backend Bot**: Python, AsyncIO, EIP-712 Signing.
- **AI Layers**: Google Gemini (Sentiment Filter), NVIDIA Build / MiniMax M2.7 (Decision Maker).
- **Frontend Dashboard**: Next.js 15, Tailwind CSS 4, Lucide Icons.

## 📝 Catatan Migrasi
Saat ini Dashboard menggunakan data *mock* (dummy). Untuk menghubungkan bot asli ke dashboard, disarankan menggunakan database **SQLite** atau **Redis** yang dapat diakses oleh kedua folder secara bersamaan.
