import os
from fastapi import FastAPI, HTTPException, Header
from .storage_sqlite import SQLiteStore, HEX
from .security import sha1_hex
from .models import HashCheckIn, HashCheckOut, PasswordCheckIn, RangeResponse

# --- Config via env ---
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join("data", "pwned.db"))
PREFIX_LEN = int(os.getenv("PREFIX_LEN", "8"))  # default 8 as requested
ENABLE_DIRECT_PASSWORD_CHECK = os.getenv("ENABLE_DIRECT_PASSWORD_CHECK", "false").lower() == "true"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

if PREFIX_LEN < 1 or PREFIX_LEN >= 40:
    raise RuntimeError("PREFIX_LEN must be between 1 and 39")

app = FastAPI(title="Distributed Password Breach Checker (SQLite)", version="2.0.0")
store = SQLiteStore(db_path=SQLITE_DB_PATH, prefix_len=PREFIX_LEN)

@app.on_event("startup")
def startup():
    store.load()

@app.get("/health")
def health():
    return {"status": "ok", "stats": store.stats()}

@app.get("/range/{prefix}", response_model=RangeResponse)
def get_range(prefix: str):
    if len(prefix) != PREFIX_LEN or any(c.upper() not in HEX for c in prefix):
        raise HTTPException(status_code=400, detail=f"Prefix must be {PREFIX_LEN} hex characters")
    rows = store.get_suffixes(prefix)
    return {"prefix": prefix.upper(), "suffixes": [{"suffix": s, "count": c} for s, c in rows]}

@app.post("/hash-check", response_model=HashCheckOut)
def hash_check(payload: HashCheckIn):
    h = payload.sha1.strip().upper()
    if len(h) != 40 or any(c not in HEX for c in h):
        raise HTTPException(status_code=400, detail="Invalid SHA-1 hex")
    count = store.get_count_for_hash(h)
    return {"breached": count > 0, "count": count}

@app.post("/check", response_model=HashCheckOut)
def check_password(payload: PasswordCheckIn):
    if not ENABLE_DIRECT_PASSWORD_CHECK:
        raise HTTPException(status_code=403, detail="Direct password check is disabled")
    h = sha1_hex(payload.password)
    count = store.get_count_for_hash(h)
    return {"breached": count > 0, "count": count}

@app.post("/admin/reload")
def reload_data(x_admin_token: str = Header(default=None)):
    # For SQLite backend, "reload" just re-opens the DB handle if needed.
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    # No-op for now (DB is already on disk). You re-run the ingest script to add data.
    return {"status": "ok", "note": "For new files, re-run ingest_to_sqlite.py to upsert into the DB."}
