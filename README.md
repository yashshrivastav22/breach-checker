# Breach Checker API (FastAPI + Uvicorn+ SQLite)

A high‑performance, privacy‑preserving password breach lookup service. Clients never send raw passwords; instead they use **k‑anonymity**: send only the first *N* hex characters of the SHA‑1 hash (default: 8, configurable), and the API returns the matching suffixes + counts.

---

## ✨ Features
- **FastAPI + Uvicorn** single‑binary web service
- **SQLite** backend with primary‑key range scans (no server DB required)
- **Headerless CSV → SQLite** ingester for very large datasets (e.g., 11GB)
- **K‑anonymity** range endpoint (`/range/{prefix}`)
- **Exact hash check** for admin/testing
- Configurable prefix length (default 8; set to 5 to match HIBP style)

---

## 📁 Repository Structure
```
.
├─ app/                # Python package
│  ├─ __init__.py
│  ├─ main.py          # FastAPI app (entrypoint when importing)
│  ├─ models.py        # Pydantic request/response models
│  ├─ security.py      # SHA-1 helper
│  └─ storage_sqlite.py# SQLite access & range queries
├─ ingest_to_sqlite.py # CSV→SQLite ingester (headerless CSV)
├─ requirements.txt    # Python deps
└─ README.md
```

> If you prefer a flat layout, you can run the app module directly with `uvicorn app.main:app ...`.

---

## 🔐 How k‑Anonymity Works (Quick)
1. Client computes `sha1(password)` → 40‑hex uppercase.
2. Split into **prefix** = first *N* hex (default 8) and **suffix** = remaining 40−N.
3. Client calls `GET /range/{prefix}`.
4. Server returns all `{suffix, count}` pairs for that prefix.
5. Client checks locally if its suffix is present and reads the breach count.

This keeps the full hash private — the server never sees it.

---

## 🚀 Getting Started

### 1) Prerequisites
- Python 3.10+
- SQLite 3 (usually preinstalled on Ubuntu)

### 2) Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Build the SQLite database from a **headerless** CSV
Your CSV must have two columns per line: `SHA1_HEX,COUNT`, no header.

```bash
# Example paths — adjust to your environment
CSV=/home/ubuntu/data/pwned.csv
DB=./data/pwned.db
mkdir -p ./data

python ingest_to_sqlite.py --csv "$CSV" --db "$DB" --batch 200000
# Script streams the file, commits in batches, and exits when done.
```

### 4) Run the API
```bash
export SQLITE_DB_PATH=./data/pwned.db
export PREFIX_LEN=8                 # set 5 for HIBP-style
# optional: enable server-side password check helper (off by default)
# export ENABLE_DIRECT_PASSWORD_CHECK=true
# optional: protect admin reload endpoint
# export ADMIN_TOKEN=your-secret

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers $(nproc)
```

Open: `http://<your_server_ip>:8000/docs`

---

## 🔧 Configuration (env vars)
- `SQLITE_DB_PATH` — path to the SQLite file (default: `data/pwned.db`)
- `PREFIX_LEN` — number of hex chars for k‑anonymity prefix (default: `8`)
- `ENABLE_DIRECT_PASSWORD_CHECK` — `true|false` to allow `/check` (default: `false`)
- `ADMIN_TOKEN` — if set, required as `X-Admin-Token` header for `/admin/reload`

> **Tip:** Set `PREFIX_LEN=8` to emulate Have I Been Pwned’s prefix length.

---

## 📘 API Reference
All responses are JSON unless otherwise noted.

### `GET /health`
Basic liveness + DB stats.

**200**
```json
{
  "status": "ok",
  "stats": {
    "backend": "sqlite",
    "db_path": "data/pwned.db",
    "rows": 123456789,
    "prefix_len": 8,
    "cached": true
  }
}
```

### `GET /range/{prefix}`
Return all suffixes + counts for the given prefix (length = `PREFIX_LEN`).

**200**
```json
{
  "prefix": "5BAA61E4",
  "suffixes": [
    { "suffix": "C9B93F3F0682250B6CF8331B7EE68FD8", "count": 100 },
    { "suffix": "...", "count": 1 }
  ]
}
```

**400** if length is wrong or non-hex.

### `POST /hash-check`
Exact lookup by **full 40‑hex SHA‑1**.

**Request**
```json
{ "sha1": "5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8" }
```
**Response**
```json
{ "breached": true, "count": 100 }
```

### `POST /check` (optional, disabled by default)
Server‑side helper: send a raw password, server hashes and checks it.
Enable with `ENABLE_DIRECT_PASSWORD_CHECK=true`.

**Request**
```json
{ "password": "password" }
```
**Response**
```json
{ "breached": true, "count": 100 }
```

### `POST /admin/reload`
No‑op placeholder for SQLite (DB lives on disk). If `ADMIN_TOKEN` is set, include header:
```
X-Admin-Token: <your-token>
```
**200** `{ "status": "ok" }`

---

## 🧪 Quick Test Snippets
**Hash a password (Ubuntu):**
```bash
printf '%s' 'password' | sha1sum | awk '{print toupper($1)}'
# 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
```

**Range query:**
```bash
curl -s "http://localhost:8000/range/5BAA61E4" | jq .
```

**Exact check:**
```bash
curl -s -X POST http://localhost:8000/hash-check \
  -H 'Content-Type: application/json' \
  -d '{"sha1":"5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8"}'
```

---

## ⚙️ Performance Notes
- Use `--workers $(nproc)` for parallel request handling.
- SQLite is read‑optimized here: WAL mode, large page cache, primary‑key range scans.
- The ingester upserts and normalizes to uppercase to ensure deterministic lookups.

---

## 🔒 Security Notes
- Prefer client‑side hashing + `/range/{prefix}` (k‑anonymity).
- Keep `/check` disabled in production unless you absolutely need it.
- Restrict inbound security group rules (port 8000) to trusted IPs or front with Nginx/TLS.

---

## 🧹 Operations
- **Update data**: re‑run `ingest_to_sqlite.py` against the same DB path to upsert.
- **Backup**: snapshot/copy the `.db` file (include `-wal` / `-shm` if copying while running).
- **Rotate**: stop service → swap DB atomically → start service.

---

## 📄 License
MIT — adjust as needed for your project.

---

## 🙏 Acknowledgements
- Inspired by the k‑anonymity model popularized by Have I Been Pwned (HIBP).

