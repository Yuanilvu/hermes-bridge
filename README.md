# Hermes Bridge 🔗

**Local automation bridge — tangan & mata Hermes Agent di desktop kamu.**

Hermes punya akses terminal, tapi tidak bisa klik UI, isi form, atau screenshot.
**Hermes Bridge menjembatani celah itu** — daemon FastAPI lokal dengan 4 router:

| Router | Endpoints | Fungsi |
|--------|-----------|--------|
| **Desktop** 🖥️ | screenshot, click, type, key, scroll, status, cursor, mouse-relative, key-hold/release | Kendali desktop lewat API |
| **Vault** 📁 | info, search, read, write, structure | Akses Obsidian vault via REST |
| **Proxy** 🌐 | http, allowed-domains | HTTP proxy dengan whitelist domain |
| **Health** ❤️ | health, nine-router | Monitoring & cek koneksi 9router |

## 🚀 Quick Start

```bash
cd ~/hermes-bridge

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Konfigurasi
export BRIDGE_API_KEY="your-secret-key"
export VAULT_PATH="$HOME/hermes-workspace"

# Jalankan
python server.py
```

## 📝 Konfigurasi

Prioritas: **env var** > **config/settings.toml** > **code default**.

| Env var | Default | Fungsi |
|---------|---------|--------|
| `BRIDGE_API_KEY` | *(required)* | Auth header `X-Bridge-Key` |
| `BRIDGE_HOST` | `127.0.0.1` | Bind address |
| `BRIDGE_PORT` | `8199` | Port |
| `VAULT_PATH` | `~/hermes-workspace` | Path ke Obsidian vault |
| `ALLOWED_DOMAINS` | `api.github.com,raw.githubusercontent.com,...` | Domain whitelist untuk proxy |
| `GITHUB_OWNER` | `Yuanilvu` | GitHub org/user |
| `GITHUB_REPO` | `hermes-bridge` | Repo name |

Copy & edit `config/settings.example.toml` → `config/settings.toml` untuk config lebih granular (CORS origins, rate limit tiap endpoint, dll).

### 🔐 Auth

Semua endpoint (kecuali `/` root & `/api/health`) butuh header:
```
X-Bridge-Key: your-secret-key
```

## 🔌 API Endpoints

### Root
| Endpoint | Auth | Deskripsi |
|----------|------|-----------|
| `GET /` | ❌ | Root info + version |
| `GET /api` | ✅ | API index + daftar semua endpoint |

### Health
| Endpoint | Auth | Deskripsi |
|----------|------|-----------|
| `GET /api/health` | ❌ | System health (untuk Docker HEALTHCHECK) |
| `GET /api/health/nine-router` | ✅ | Cek koneksi 9router |

### Desktop
| Endpoint | Method | Deskripsi | Rate limit |
|----------|--------|-----------|------------|
| `/api/desktop/status` | GET | Status cua-driver & display | 30/min |
| `/api/desktop/screenshot` | GET | Screenshot PNG (base64) | **15/min** |
| `/api/desktop/cursor` | GET | Posisi cursor | 30/min |
| `/api/desktop/mouse` | POST | Gerakin mouse absolute | 30/min |
| `/api/desktop/mouse-relative` | POST | Gerakin mouse relatif | 30/min |
| `/api/desktop/click` | POST | Click (left/right/middle) | 30/min |
| `/api/desktop/double-click` | POST | Double click | 30/min |
| `/api/desktop/type` | POST | Ketik teks | 30/min |
| `/api/desktop/key` | POST | Keyboard shortcut | 30/min |
| `/api/desktop/key-hold` | POST | Tahan tombol | 30/min |
| `/api/desktop/key-release` | POST | Lepas tombol | 30/min |
| `/api/desktop/scroll` | POST | Scroll | 30/min |

### Vault
| Endpoint | Method | Deskripsi | Rate limit |
|----------|--------|-----------|------------|
| `/api/vault` | GET | Info vault + provider count | 30/min |
| `/api/vault/files/search?q=...` | GET | Cari konten file (min 1 char) | 30/min |
| `/api/vault/files/read?file=...` | GET | Baca file dari vault | 30/min |
| `/api/vault/files/write` | POST | Tulis file (max 1 MB) | **30/min** |
| `/api/vault/files/structure` | GET | Struktur direktori vault | 30/min |

### Proxy
| Endpoint | Method | Deskripsi |
|----------|--------|-----------|
| `/api/proxy/allowed-domains` | GET | Daftar domain yang diizinkan |
| `/api/proxy/http?url=...` | GET | Proxy GET request (whitelisted domain only) |

## 🧪 Testing

```bash
cd ~/hermes-bridge
source .venv/bin/activate
pip install pytest  # one-time
python -m pytest tests/ -v
```

**31 tests** — auth, config, health, vault, proxy, desktop.

## ⚙️ Deployment

```bash
# Systemd service (auto-start)
sudo cp hermes-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-bridge.service

# Docker
docker build -t hermes-bridge .
docker run -d -p 8199:8199 -e BRIDGE_API_KEY=... hermes-bridge
```

## 📄 Lisensi

MIT
