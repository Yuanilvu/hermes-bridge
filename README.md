# Hermes Bridge 🔗

**Local automation bridge — memberi Hermes Agent "tangan & mata" di desktop kamu.**

Hermes punya akses terminal, tapi tidak bisa klik-klik UI, isi form, atau akses dashboard web yang butuh login. **Hermes Bridge menjembatani celah itu** — daemon FastAPI lokal yang bisa:

- ✅ **Health check** — cek status 9router, API key, koneksi sistem
- ✅ **Provider manager** — import/manage API keys dari file `providers.txt`
- ✅ **9router integration** — cek status provider, rotasi key (coming soon)
- ✅ **Browser automation** — kendalikan browser via Playwright (coming soon)
- ✅ **Vault integration** — baca/tulis Obsidian notes via API (coming soon)

## 🚀 Quick Start

```bash
# 1. Install dependencies
cd ~/hermes-bridge
pip install -r requirements.txt

# 2. Set API key (untuk auth antara Hermes dan Bridge)
export BRIDGE_API_KEY="hermes-local-2026"

# 3. Jalanin server
python server.py

# 4. Cek kesehatan
curl http://127.0.0.1:8199/api/health

# 5. Lihat Swagger docs
# Buka http://127.0.0.1:8199/docs di browser
```

## 📝 Konfigurasi

Bridge membaca konfigurasi dari beberapa sumber (prioritas tinggi ke rendah):
1. **Environment variables** — `BRIDGE_API_KEY`, `GITHUB_TOKEN`, `9ROUTER_URL`
2. **`config/settings.toml`** — file konfigurasi utama
3. **`config/providers.txt`** — daftar API key (format: `label,api_key`)

### providers.txt format

```txt
# Satu baris per key
google_ai_1,AIzaSyYourKeyHere
openrouter_1,sk-or-v1-your-key
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/api/health/nine-router` | GET | Check 9router connectivity |
| `/api/providers` | GET | List all providers |
| `/api/providers` | POST | Add new provider |
| `/api/providers/health` | GET | Check all provider statuses |

Semua endpoint (kecuali `/docs`) butuh header `X-Bridge-Key`.

## 🗺️ Roadmap

- [x] FastAPI server with health & provider endpoints
- [x] API key auth
- [x] Config loader (env + toml + file)
- [ ] Playwright browser automation
- [ ] 9router SQLite direct import
- [ ] Systemd service auto-start
- [ ] Key rotator & health checker
- [ ] Obsidian vault integration

## 📄 Lisensi

MIT
