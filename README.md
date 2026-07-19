# Hermes Bridge 🔗

**Local automation bridge — memberi Hermes Agent tangan & mata di desktop Linux.**

Hermes Agent punya akses terminal, tapi tidak bisa klik UI, isi form, screenshot, atau akses Obsidian vault lewat REST. **Hermes Bridge menjembatani celah itu** — daemon FastAPI lokal yang menyediakan 4 kategori API:

| Kategori | Fungsi |
|----------|--------|
| 🖥️ **Desktop** | Screenshot, mouse, keyboard, click, scroll, cursor — kendali penuh GUI |
| 📁 **Vault** | Baca, tulis, cari file di Obsidian vault Hermes Workspace |
| 🌐 **Proxy** | HTTP proxy aman ke whitelisted domain (GitHub API, dll) |
| ❤️ **Health** | Monitoring service & koneksi 9router |

---

## 📋 Daftar Isi

- [Quick Start](#-quick-start)
- [Instalasi Detail](#-instalasi-detail)
  - [Manual (venv)](#manual-venv)
  - [Docker](#docker)
  - [Systemd Service](#systemd-service)
- [Konfigurasi](#-konfigurasi)
  - [Environment Variables](#environment-variables)
  - [settings.toml](#settingstoml)
  - [Prioritas Config](#prioritas-config)
- [Autentikasi](#-autentikasi)
- [API Reference Lengkap](#-api-reference-lengkap)
  - [Root](#1-root)
  - [Health](#2-health-❤️)
  - [Desktop](#3-desktop-🖥️)
  - [Vault](#4-vault-📁)
  - [Proxy](#5-proxy-🌐)
- [Rate Limiting](#-rate-limiting)
- [Body Size Limits](#-body-size-limits)
- [Error Handling](#-error-handling)
- [Development](#-development)
  - [Project Structure](#project-structure)
  - [Running Tests](#running-tests)
  - [Menambahkan Endpoint Baru](#menambahkan-endpoint-baru)
- [Troubleshooting](#-troubleshooting)
- [Arsitektur](#-arsitektur)
- [Roadmap](#-roadmap)

---

## 🚀 Quick Start

```bash
# 1. Clone
cd ~
git clone https://github.com/Yuanilvu/hermes-bridge.git
cd hermes-bridge

# 2. Buat virtual env & install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Set API key (WAJIB — untuk autentikasi Hermes ↔ Bridge)
export BRIDGE_API_KEY="buat-key-rahasia-sendiri"

# 4. Jalankan
python server.py

# 5. Verifikasi
curl http://127.0.0.1:8199/
# → {"name":"Hermes Bridge","version":"0.2.3","docs":"/docs","health":"/api/health"}

curl http://127.0.0.1:8199/api/health
# → {"status":"ok","timestamp":"...","bridge_version":"0.2.3","uptime_seconds":...}
```

---

## 📦 Instalasi Detail

### Manual (venv)

**Persyaratan:**
- Python 3.11+
- Linux dengan X11/XWayland (untuk desktop automation)
- Obsidian vault di `~/hermes-workspace` (untuk fitur vault)

```bash
cd ~/hermes-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Buat file .env dari contoh
cp .env.example .env
nano .env   # isi BRIDGE_API_KEY dan konfigurasi lain

# Jalankan
python server.py
```

### Docker

```bash
# Build
docker build -t hermes-bridge .

# Run
docker run -d \
  --name hermes-bridge \
  -p 8199:8199 \
  -e BRIDGE_API_KEY="your-secret-key" \
  -e VAULT_PATH="/workspace" \
  -v /home/yuan/hermes-workspace:/workspace \
  hermes-bridge
```

Docker image sudah include:
- ✅ Multi-stage build (slim final image)
- ✅ Non-root user (`appuser`)
- ✅ HEALTHCHECK (`/api/health` tanpa auth)
- ✅ Requirements terinstall di build stage

### Systemd Service

Agar Hermes Bridge menyala otomatis saat boot:

```bash
# Sesuaikan path dan user di hermes-bridge.service, lalu:
sudo cp hermes-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-bridge.service

# Cek status
sudo systemctl status hermes-bridge.service

# Lihat log
sudo journalctl -u hermes-bridge.service -f
```

Fitur systemd:
- ✅ **Restart otomatis** — `Restart=on-failure`
- ✅ **Graceful shutdown** — `ExecStop` membersihkan proses cua-driver
- ✅ **Working Directory** — diatur ke `/home/yuan/hermes-bridge`
- ✅ **Environment file** — baca `.env` dari home directory

---

## ⚙️ Konfigurasi

### Environment Variables

| Variabel | Wajib | Default | Deskripsi |
|----------|-------|---------|-----------|
| `BRIDGE_API_KEY` | ✅ **YA** | `‑` | API key untuk autentikasi (header `X-Bridge-Key`) |
| `BRIDGE_HOST` | ❌ | `127.0.0.1` | Bind address (`0.0.0.0` untuk akses dari luar) |
| `BRIDGE_PORT` | ❌ | `8199` | Port server |
| `VAULT_PATH` | ❌ | `~/hermes-workspace` | Path absolut ke Obsidian vault |
| `GITHUB_OWNER` | ❌ | `Yuanilvu` | Nama user/org GitHub (untuk proxy & info) |
| `GITHUB_REPO` | ❌ | `hermes-bridge` | Nama repo GitHub |
| `ALLOWED_DOMAINS` | ❌ | `api.github.com,raw.githubusercontent.com` | Domain yang diizinkan untuk proxy (pisahkan dengan koma) |
| `RATE_LIMIT_DEFAULT` | ❌ | `30/minute` | Rate limit default semua endpoint |
| `RATE_LIMIT_DESKTOP` | ❌ | `15/minute` | Khusus endpoint screenshot |
| `RATE_LIMIT_VAULT` | ❌ | `30/minute` | Khusus endpoint vault write |
| `RATE_LIMIT_HEALTH` | ❌ | `60/minute` | Khusus endpoint health |
| `CORS_ORIGINS` | ❌ | `*` | Origins yang diizinkan (pisahkan dengan koma) |

### settings.toml

Bisa juga pakai file TOML untuk konfigurasi yang lebih terstruktur. Copy dari example:

```bash
cp config/settings.example.toml config/settings.toml
nano config/settings.toml
```

Isi `config/settings.example.toml`:

```toml
[bridge]
host = "127.0.0.1"
port = 8199

[rate_limit]
default = "30/minute"
health = "60/minute"
desktop = "15/minute"
vault = "30/minute"

[cors]
origins = ["http://localhost:3000"]

[auth]
api_key = ""

[desktop]
display = ":0"
wayland_display = "wayland-0"

[logging]
level = "INFO"
```

### Prioritas Config

**Env var > settings.toml > Code default**

Artinya:
1. Kalau `BRIDGE_API_KEY` diatur lewat env var, itu yang dipakai (settings.toml diabaikan)
2. Kalau env var tidak ada, cari di `config/settings.toml`
3. Kalau file TOML tidak ada atau key tidak ditemukan, pakai default dari kode

Cocok untuk development lokal (env var) dan production/deployment (settings.toml).

---

## 🔐 Autentikasi

**Semua endpoint** (kecuali `/` root dan `/api/health`) **WAJIB** menyertakan header:

```
X-Bridge-Key: <BRIDGE_API_KEY>
```

Contoh:

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api/vault
```

**HTTP Response Codes:**

| Kode | Arti |
|------|------|
| `422` | Header `X-Bridge-Key` tidak dikirim sama sekali (required field) |
| `401` | Header dikirim tapi nilainya salah |
| `200` | Valid |

⚠️ **Best practice:** Jangan pernah commit `BRIDGE_API_KEY` ke git. File `.env` dan `config/settings.toml` sudah otomatis di-ignore oleh `.gitignore`.

---

## 📚 API Reference Lengkap

### 1. Root

#### `GET /`
Info dasar service — **tanpa auth**.

```bash
curl http://127.0.0.1:8199/
```

Response:
```json
{
  "name": "Hermes Bridge",
  "version": "0.2.3",
  "docs": "/docs",
  "health": "/api/health"
}
```

#### `GET /api`
Daftar semua endpoint yang tersedia — **dengan auth**.

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api
```

Response: object dengan key per kategori, masing-masing berisi daftar endpoint + method + deskripsi.

---

### 2. Health ❤️

#### `GET /api/health`
Cek kesehatan service — **tanpa auth** (sengaja, untuk Docker HEALTHCHECK).

```bash
curl http://127.0.0.1:8199/api/health
```

Response:
```json
{
  "status": "ok",
  "timestamp": "2026-07-19T15:26:51.076767",
  "bridge_version": "0.2.3",
  "uptime_seconds": 2.22
}
```

#### `GET /api/health/nine-router`
Cek koneksi ke 9router — **dengan auth**.

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api/health/nine-router
```

---

### 3. Desktop 🖥️

Semua endpoint desktop butuh **cua-driver** terinstall. Kalau cua-driver tidak berjalan, endpoint akan mengembalikan error.

#### `GET /api/desktop/status`
Cek status driver desktop.

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api/desktop/status
```

Response (contoh):
```json
{
  "status": "ok",
  "driver_available": true,
  "display": ":0",
  "wayland_display": "wayland-0"
}
```

#### `GET /api/desktop/cursor`
Posisi cursor mouse saat ini.

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api/desktop/cursor
```

Response:
```json
{
  "x": 960,
  "y": 540
}
```

#### `GET /api/desktop/screenshot`
Ambil screenshot layar — **rate limit 15/menit**.

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api/desktop/screenshot
```

Response: `image/png` binary langsung.

---

#### `POST /api/desktop/mouse`
Gerakkan mouse ke koordinat absolut.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"x": 960, "y": 540}' \
  http://127.0.0.1:8199/api/desktop/mouse
```

Body:
| Field | Tipe | Wajib | Deskripsi |
|-------|------|-------|-----------|
| `x` | integer | ✅ | Posisi X (0 = kiri) |
| `y` | integer | ✅ | Posisi Y (0 = atas) |

---

#### `POST /api/desktop/mouse-relative`
Gerakkan mouse relatif dari posisi sekarang.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"dx": 100, "dy": -50}' \
  http://127.0.0.1:8199/api/desktop/mouse-relative
```

Body:
| Field | Tipe | Wajib | Deskripsi |
|-------|------|-------|-----------|
| `dx` | integer | ✅ | Geser X (positif = kanan) |
| `dy` | integer | ✅ | Geser Y (positif = bawah) |

---

#### `POST /api/desktop/click`
Klik mouse.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"button": "left"}' \
  http://127.0.0.1:8199/api/desktop/click
```

Body:
| Field | Tipe | Wajib | Default | Deskripsi |
|-------|------|-------|---------|-----------|
| `button` | string | ❌ | `"left"` | `"left"`, `"right"`, atau `"middle"` |
| `x` | integer | ❌ | `null` (posisi sekarang) | Klik di koordinat tertentu |
| `y` | integer | ❌ | `null` | Klik di koordinat tertentu |

---

#### `POST /api/desktop/double-click`
Double click (sama formatnya dengan click).

---

#### `POST /api/desktop/type`
Ketik teks.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello World!"}' \
  http://127.0.0.1:8199/api/desktop/type
```

Body:
| Field | Tipe | Wajib | Deskripsi |
|-------|------|-------|-----------|
| `text` | string | ✅ | Teks yang akan diketik |

---

#### `POST /api/desktop/key`
Kirim keyboard shortcut (kombinasi tombol).

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"keys": "ctrl+s"}' \
  http://127.0.0.1:8199/api/desktop/key
```

Body:
| Field | Tipe | Wajib | Deskripsi |
|-------|------|-------|-----------|
| `keys` | string | ✅ | Kombinasi key (pakai `+`, misal: `"ctrl+alt+t"`) |

---

#### `POST /api/desktop/key-hold`
Tahan satu tombol (untuk drag-and-drop).

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"key": "ctrl"}' \
  http://127.0.0.1:8199/api/desktop/key-hold
```

Body:
| Field | Tipe | Wajib | Deskripsi |
|-------|------|-------|-----------|
| `key` | string | ✅ | Tombol yang ditahan (`"ctrl"`, `"shift"`, dll) |

---

#### `POST /api/desktop/key-release`
Lepas tombol yang ditahan.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"key": "ctrl"}' \
  http://127.0.0.1:8199/api/desktop/key-release
```

---

#### `POST /api/desktop/scroll`
Scroll mouse.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"clicks": 3, "direction": "down"}' \
  http://127.0.0.1:8199/api/desktop/scroll
```

Body:
| Field | Tipe | Wajib | Default | Deskripsi |
|-------|------|-------|---------|-----------|
| `clicks` | integer | ❌ | `3` | Jumlah scroll tick |
| `direction` | string | ✅ | `‑` | `"up"` atau `"down"` |

---

### 4. Vault 📁

**Catatan:** Vault path diatur lewat env var `VAULT_PATH` atau `config/settings.toml`. Default: `~/hermes-workspace`. Vault harus berupa direktori yang bisa dibaca oleh user yang menjalankan server.

#### `GET /api/vault`
Info vault + jumlah file/provider.

```bash
curl -H "X-Bridge-Key: rahasia123" http://127.0.0.1:8199/api/vault
```

Response (contoh):
```json
{
  "path": "/home/yuan/hermes-workspace",
  "name": "hermes-workspace",
  "file_count": 142,
  "size_kb": 2840,
  "provider_count": 3
}
```

#### `GET /api/vault/files/search?q=...`
Cari konten file di vault (min 1 karakter).

```bash
curl -H "X-Bridge-Key: rahasia123" \
  "http://127.0.0.1:8199/api/vault/files/search?q=catatan+keuangan"
```

Parameter query:
| Parameter | Wajib | Deskripsi |
|-----------|-------|-----------|
| `q` | ✅ | Kata kunci pencarian (min 1 char) |
| `path` | ❌ | Batasi pencarian ke subfolder tertentu |

Response:
```json
{
  "results": [
    {"file": "notes/projects/catatan-keuangan.md", "line": 5, "match": "...catatan keuangan..."}
  ],
  "total": 3,
  "query": "catatan keuangan"
}
```

Error kalau `q` kosong → `422`.

#### `GET /api/vault/files/read?file=...`
Baca isi file dari vault.

```bash
curl -H "X-Bridge-Key: rahasia123" \
  "http://127.0.0.1:8199/api/vault/files/read?file=notes/daily/2026-07-19.md"
```

Parameter query:
| Parameter | Wajib | Deskripsi |
|-----------|-------|-----------|
| `file` | ✅ | Path relatif dari root vault |

Response:
```json
{
  "file": "notes/daily/2026-07-19.md",
  "path": "/home/yuan/hermes-workspace/notes/daily/2026-07-19.md",
  "size": 1234,
  "content": "# 2026-07-19\n...isi catatan..."
}
```

Error kalau file tidak ditemukan → `404`.

#### `POST /api/vault/files/write`
Tulis/update file di vault — **rate limit 30/menit, max 1 MB**.

```bash
curl -X POST -H "X-Bridge-Key: rahasia123" \
  -H "Content-Type: application/json" \
  -d '{"file": "notes/inbox/test.md", "content": "# Catatan Baru\nIni isi catatan..."}' \
  http://127.0.0.1:8199/api/vault/files/write
```

Body:
| Field | Tipe | Wajib | Deskripsi |
|-------|------|-------|-----------|
| `file` | string | ✅ | Path relatif (akan dibuat otomatis) |
| `content` | string | ✅ | Isi file (max 1.048.576 bytes = 1 MB) |

Response:
```json
{
  "status": "written",
  "file": "notes/inbox/test.md",
  "path": "/home/yuan/hermes-workspace/notes/inbox/test.md",
  "size": 33
}
```

Error kalau content > 1 MB → `422`:

```json
{
  "detail": "Content exceeds maximum size of 1048576 bytes"
}
```

#### `GET /api/vault/files/structure`
Dapatkan struktur direktori vault.

```bash
curl -H "X-Bridge-Key: rahasia123" \
  http://127.0.0.1:8199/api/vault/files/structure
```

Response:
```json
{
  "vault_root": "/home/yuan/hermes-workspace",
  "structure": {
    "notes": {
      "daily": ["2026-07-19.md", "2026-07-18.md"],
      "projects": ["catatan-keuangan.md", "hermes-agent.md"],
      "meetings": ["sprint-1.md"],
      "inbox": [],
      "...": "..."
    },
    "templates": ["daily-note.md", "project.md"],
    "attachments": [],
    "scripts": ["auto-note-mover.sh"]
  }
}
```

---

### 5. Proxy 🌐

#### `GET /api/proxy/allowed-domains`
Lihat daftar domain yang diizinkan untuk proxy.

```bash
curl -H "X-Bridge-Key: rahasia123" \
  http://127.0.0.1:8199/api/proxy/allowed-domains
```

Response:
```json
{
  "allowed_domains": [
    "api.github.com",
    "raw.githubusercontent.com",
    "raw.github.com"
  ],
  "note": "Subdomain matches: *.github.com"
}
```

#### `GET /api/proxy/http?url=...`
Proxy HTTP GET request ke domain yang diizinkan.

```bash
curl -H "X-Bridge-Key: rahasia123" \
  "http://127.0.0.1:8199/api/proxy/http?url=https://api.github.com/repos/Yuanilvu/hermes-bridge"
```

Parameter query:
| Parameter | Wajib | Deskripsi |
|-----------|-------|-----------|
| `url` | ✅ | URL lengkap (hanya http/https, hostname harus di whitelist) |

Response: Response asli dari URL target (termasuk status code, header, body).

Error:
- `400` — URL tidak valid / hostname tidak bisa diparse
- `403` — Domain tidak ada di whitelist
- `400` — Bukan protokol http/https

---

## ⏱️ Rate Limiting

Tiap endpoint punya **rate limit terpisah** (diatur lewat env var atau `config/settings.toml`):

| Endpoint | Limit per menit | Tujuan |
|----------|----------------|--------|
| **Screenshot** | **15/menit** | Paling berat — gambar besar |
| **Vault Write** | **30/menit** | Prevent flooding vault |
| **Health** | **60/menit** | Ringan — monitoring |
| **Semua lain** | **30/menit** | Default umum |

Kalau limit terlampaui, API mengembalikan:

```
HTTP 429 Too Many Requests
Retry-After: 60
```

```json
{
  "detail": "Rate limit exceeded: 15 per 1 minute"
}
```

---

## 📏 Body Size Limits

| Batasan | Nilai | Endpoint |
|---------|-------|----------|
| **Total request body** | **10 MB** | Semua POST endpoint |
| **Vault write content** | **1 MB** | `POST /api/vault/files/write` (validasi tambahan) |

Melebihi batas → `422 Unprocessable Entity`.

---

## ❌ Error Handling

Semua error dikembalikan dalam format JSON standar:

```json
{
  "detail": "Pesan error jelas"
}
```

| HTTP Code | Penyebab Umum |
|-----------|---------------|
| `400` | Parameter tidak valid (hostname kosong, URL bukan http) |
| `401` | `X-Bridge-Key` salah |
| `403` | Domain tidak ada di whitelist proxy |
| `404` | File vault tidak ditemukan |
| `413` | Request body terlalu besar (> 10 MB) |
| `422` | Validasi gagal (field kosong, content > 1 MB, parameter hilang) |
| `429` | Rate limit terlampaui |
| `500` | Internal server error (ada di log) |

---

## 🧪 Development

### Project Structure

```
/home/yuan/hermes-bridge/
├── hermes_bridge/
│   ├── __init__.py          # Version central (VERSION = "0.2.3")
│   ├── __main__.py          # Entry point "python -m hermes_bridge"
│   ├── auth.py              # verify_api_key dependency
│   ├── config_loader.py     # Baca env var + settings.toml + defaults
│   ├── rate_limit.py        # Shared Limiter instance slowapi
│   ├── server.py            # App factory, CORS, middleware, startup/shutdown
│   └── routers/
│       ├── desktop.py       # 11 endpoint desktop automation
│       ├── health.py        # 2 endpoint monitoring
│       ├── vault.py         # 5 endpoint vault
│       └── proxy_http.py    # 2 endpoint proxy
├── config/
│   ├── settings.example.toml # Contoh konfigurasi TOML
│   └── providers.example.txt # Contoh file provider 9router
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Fixtures: client, auth_headers, vault path
│   ├── fixtures/
│   │   └── vault/
│   │       └── test.md      # File test untuk vault
│   ├── test_auth.py         # 4 test: proteksi endpoint
│   ├── test_config.py       # 7 test: config loader
│   ├── test_desktop.py      # 2 test: status, cursor
│   ├── test_health.py       # 4 test: root, health, api root, auth
│   ├── test_proxy.py        # 4 test: domains, validation, forbidden
│   └── test_vault.py        # 6 test: info, structure, search, read, write
├── launcher.sh              # Script startup untuk systemd
├── hermes-bridge.service    # Systemd unit file
├── Dockerfile               # Docker multi-stage build
├── .env.example             # Contoh environment variables
├── .gitignore               # Git ignore rules
├── pyproject.toml           # Project config + pytest settings
├── requirements.txt         # Python dependencies
└── README.md                # File ini
```

### Running Tests

```bash
cd ~/hermes-bridge
source .venv/bin/activate

# Install test dependencies (one time)
pip install pytest httpx

# Jalankan semua test
python -m pytest tests/ -v

# Test spesifik
python -m pytest tests/test_auth.py -v

# Dengan coverage
pip install pytest-cov
python -m pytest tests/ --cov=hermes_bridge -v
```

**31 tests mencakup:**
- ✅ Auth — endpoint publik vs terproteksi, key benar/salah/hilang
- ✅ Config — env var override, default values, TOML fallback
- ✅ Desktop — status, cursor (tanpa cua-driver)
- ✅ Health — root, health json, api root, auth required
- ✅ Proxy — allowed domains, forbidden domain, URL validation
- ✅ Vault — info, search (normal & empty), read (exist & not exist), write (normal & oversized)

### Menambahkan Endpoint Baru

1. Buat file router baru di `hermes_bridge/routers/` atau tambah ke router existing
2. Gunakan dekorator `@router.get/post/...` dengan `prefix` yang sesuai
3. Tambahkan `Depends(verify_api_key)` untuk proteksi auth
4. Tambahkan `@limiter.limit(...)` untuk rate limiting
5. Daftarkan router di `server.py` via `app.include_router()`
6. Tambahkan test di `tests/`
7. Bump versi di `hermes_bridge/__init__.py`

---

## 🔧 Troubleshooting

### Service tidak bisa start

```bash
# Cek log
sudo journalctl -u hermes-bridge.service -n 50 --no-pager

# Verifikasi .env ada
cat ~/hermes-bridge/.env | grep BRIDGE_API_KEY

# Jalankan manual untuk lihat error
cd ~/hermes-bridge && source .venv/bin/activate && python server.py
```

### Desktop endpoint error

```bash
# Cek cua-driver terinstall
which cua-driver

# Cek display tersedia
echo $DISPLAY
echo $WAYLAND_DISPLAY

# Kill & restart cua-driver kalau hang
pkill -f cua-driver
cua-driver start
```

### Vault endpoint 404

```bash
# Cek VAULT_PATH
echo $VAULT_PATH
# Default: ~/hermes-workspace

# Pastikan path-nya benar dan bisa dibaca
ls -la $VAULT_PATH
```

### 401 Unauthorized terus

```bash
# Cek BRIDGE_API_KEY di .env
grep BRIDGE_API_KEY ~/hermes-bridge/.env

# Tes manual
curl -H "X-Bridge-Key: $(grep BRIDGE_API_KEY ~/hermes-bridge/.env | cut -d= -f2)" http://127.0.0.1:8199/api/vault
```

### Rate limit kepanasan

```bash
# Reset dengan restart service
sudo systemctl restart hermes-bridge.service

# Atau naikkan limit lewat env var
export RATE_LIMIT_DESKTOP="60/minute"
```

---

## 🏗️ Arsitektur

```
┌─────────────────────────────────────────────────┐
│                  Hermes Agent                    │
│          (LLM + tools: terminal, file, web)      │
└──────────────┬──────────────────────────┬────────┘
               │ HTTP request              │ WebSocket?
               │ X-Bridge-Key auth         │
               ▼                          ▼
┌──────────────────────────────────────────────┐
│           Hermes Bridge (FastAPI)             │
│                                              │
│  ┌─────────┐ ┌────────┐ ┌──────┐ ┌────────┐ │
│  │ Desktop │ │ Health │ │Vault │ │ Proxy  │ │
│  │ Router  │ │ Router │ │Router│ │ Router │ │
│  └────┬────┘ └───┬────┘ └──┬───┘ └───┬────┘ │
│       │          │         │         │       │
│  ┌────▼────┐ ┌───▼────┐ ┌──▼───┐ ┌──▼────┐  │
│  │cua-drvr │ │9router │ │Obsid.│ │GitHub │  │
│  │(desktop)│ │(API)   │ │Vault │ │API    │  │
│  └─────────┘ └────────┘ └──────┘ └───────┘  │
└──────────────────────────────────────────────┘
```

**Alur data:**
1. **Hermes Agent** mengirim HTTP request ke Bridge (localhost:8199)
2. **Middleware** mengecek auth (`X-Bridge-Key`), body size, CORS
3. **Router** meneruskan ke handler sesuai endpoint
4. **Handler** menjalankan aksi (screenshot via cua-driver, baca vault, proxy HTTP)
5. **Rate limiter** memastikan tidak ada abuse per endpoint
6. **Response** dikembalikan ke Hermes Agent

**Security layers (dari luar ke dalam):**
1. CORS — membatasi origin browser
2. Body size limit — mencegah request raksasa (10 MB)
3. Auth header — X-Bridge-Key (kecuali `/` dan `/api/health`)
4. Rate limiter — mencegah brute force / abuse per endpoint
5. Whitelist domain — proxy hanya ke domain tertentu
6. Content validator — vault write max 1 MB, search min 1 char
7. Git ignore — .env dan settings.toml tidak pernah masuk git

---

## 🗺️ Roadmap

### ✅ Selesai
- [x] FastAPI server dengan 4 router (desktop, health, vault, proxy)
- [x] API key authentication
- [x] Config loader (env var + TOML + defaults)
- [x] Desktop automation (screenshot, mouse, keyboard, click, scroll)
- [x] Vault integration (read, write, search, structure)
- [x] HTTP proxy dengan domain whitelist
- [x] Rate limiting per-endpoint
- [x] Systemd service dengan graceful shutdown
- [x] Docker multi-stage build
- [x] Pytest suite (31 tests)
- [x] Version sentral
- [x] CORS configurable
- [x] Graceful shutdown cua-driver

### 🔜 Potensi Mendatang
- [ ] Playwright browser automation
- [ ] 9router SQLite direct import
- [ ] Key rotator & health checker otomatis
- [ ] Webhook system (event → trigger endpoint)
- [ ] File upload endpoint (attachments)
- [ ] WebSocket untuk real-time desktop streaming
- [ ] Endpoint documentation generator (OpenAPI tags sudah siap)

---


