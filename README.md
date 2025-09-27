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
2. Split into **prefix** = first *N* hex (default 8) and **suffix** = remaining 40-N.
3. Client calls `GET /range/{prefix}`.
4. Server returns all `{suffix, count}` pairs for that prefix.
5. Client checks locally if its suffix is present and reads the breach count.

This keeps the full hash private - the server never sees it.

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

### 3) You can download the csv from here or you can use your own csv file:
[Kaggle SHA-1 dump](https://www.kaggle.com/datasets/yashshrivastav22/sha-1-password-hash-dump)

### 4) Build the SQLite database from a **headerless** CSV
This CSV have two columns per line: `SHA1_HEX,COUNT`, no header.

```bash
# Example paths - adjust to your environment
CSV=/home/ubuntu/data/pwned.csv
DB=./data/pwned.db
mkdir -p ./data
python ingest_to_sqlite.py --csv "$CSV" --db "$DB" --batch 200000
```

Script streams the file, commits in batches, and exits when done.

![csv_inject_into_sqlitedb](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/csv_inject_into_sqlitedb.PNG)


### 5) Run the API
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

**Output**
```json
{
  "status": "ok",
  "stats": {
    "backend": "sqlite",
    "db_path": "./data/pwned.db",
    "rows": 262974240,
    "prefix_len": 8,
    "cached": true
  }
}
```
![Health Status](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/health_status.PNG)

### `GET /range/{prefix}`
Return all suffixes + counts for the given prefix (length = `PREFIX_LEN`).

#### 1) Existence 8 prefix

**200**

**OutPut**
```json
{
  "prefix": "0000003F",
  "suffixes": [
    {
      "suffix": "2785CA62D59AB905EEAB3533EFFE337A",
      "count": 15
    },
    {
      "suffix": "A0BC80B317DDE176D6A71F6321CCD35E",
      "count": 2
    }
  ]
}
```
![Range Prefix 1](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/range_prefix_1.PNG)

#### 2) Non-existence 8 prefix

**200**

**OutPut**
```json
{
  "prefix": "0000003A",
  "suffixes": []
}
```
![Range Prefix 2](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/range_prefix_2.PNG)

#### 3) Invalid 8 prefix

**400**

**OutPut**
```json
{
  "detail": "Prefix must be 8 hex characters"
}
```
![Range Prefix 3](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/range_prefix_3.PNG)


### `POST /hash-check`
Exact lookup by **full 40‑hex SHA‑1**.

#### 1) Existence Hash Check:

Generate the SHA-1 hash

```bash
printf '%s' 'usa123' | sha1sum | awk '{print toupper($1)}'
```

![Hash Generate 1](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/hash_generate_1.PNG)

**200**

**Request**
```json
curl -X 'POST' \
  'http://100.25.217.94:8000/hash-check' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "sha1": "087F62B3D37E93191C2BB40336F41DE4DD9D3838"
}'
```

**Response**
```json
{
  "breached": true,
  "count": 38929
}
```
![Hash Check 1A](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/hash_check_1a.PNG)

![Hash Check 1B](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/hash_check_1b.PNG)

#### 2) Non-existence Hash Check

Generate the SHA-1 hash

```bash
printf '%s' 'johndoe123' | sha1sum | awk '{print toupper($1)}'

```
![Hash Generate 2](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/hash_generate_2.PNG)

**200**

**Request**
```json
curl -X 'POST' \
  'http://100.25.217.94:8000/hash-check' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "sha1": "AE2B299B1C065B186F8D50869097CBFF26EA283B"
}'
```

**Response**
```json
{
  "breached": false,
  "count": 0
}
```
![Hash Check 2A](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/hash_check_2a.PNG)

![Hash Check 2B](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/hash_check_2b.PNG)


### `POST /check` (optional, disabled by default)
Server‑side helper: send a raw password, server hashes and checks it.
Enable with `ENABLE_DIRECT_PASSWORD_CHECK=true`.

#### 1) Existence password check
**200**

**Request**
```json
curl -X 'POST' \
  'http://100.25.217.94:8000/check' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "password": "tomjerry"
}'
```

**Response**
```json
{
  "breached": true,
  "count": 3774
}
```

![Password Check 1A](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/password_check_1a.PNG)

![Password Check 1A](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/password_check_1a.PNG)

#### 2) Non-existence password check
**200**

**Request**
```json
curl -X 'POST' \
  'http://100.25.217.94:8000/check' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "password": "bunNy123"
}'
```

**Response**
```json
{
  "breached": false,
  "count": 0
}
```

![Password Check 2B](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/password_check_2a.PNG)

![Password Check 2B](https://github.com/yashshrivastav22/Images/blob/main/breach-checker/password_check_2a.PNG)

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
MIT - adjust as needed for your project.

---

## Acknowledgements
- Inspired by the k‑anonymity model popularized by Have I Been Pwned (HIBP).

