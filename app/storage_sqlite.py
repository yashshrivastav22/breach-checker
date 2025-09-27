import os
import sqlite3
from typing import List, Tuple

HEX = set("0123456789ABCDEF")

def _prefix_upper_bound(prefix: str) -> str:
    """
    Compute the smallest hex string strictly greater than all strings
    with this prefix: essentially increment the prefix as a big hex number.
    If it overflows, return a sentinel larger than any 40-hex hash (e.g., 'Z').
    """
    p = prefix.upper()
    try:
        n = int(p, 16) + 1
        # keep same width with leading zeros
        up = format(n, "X").rjust(len(p), "0")
    except Exception:
        return "Z"
    # if width increased (overflow), use sentinel
    if len(up) > len(p):
        return "Z"
    return up

class SQLiteStore:
    """
    SQLite-backed store for huge datasets.
    Schema:
      CREATE TABLE passwords(
        hash  TEXT PRIMARY KEY,  -- 40-char uppercase hex
        count INTEGER NOT NULL
      );
    """
    def __init__(self, db_path: str, prefix_len: int):
        if prefix_len < 1 or prefix_len >= 40:
            raise ValueError("PREFIX_LEN must be between 1 and 39")
        self.db_path = db_path
        self.prefix_len = prefix_len
        self.conn: sqlite3.Connection | None = None

    def load(self):
        if not os.path.isfile(self.db_path):
            raise RuntimeError(
                f"SQLite DB not found at {self.db_path}. "
                "Run the ingest script first: "
                "python ingest_to_sqlite.py --db data\\pwned.db --paths \"data\\*.txt,data\\*.csv\""
            )
        # open connection
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute("PRAGMA cache_size=-200000;")  # ~200MB cache (adjust as needed)

    def stats(self):
        try:
            cur = self.conn.execute("SELECT value FROM meta WHERE key='row_count';")
            row = cur.fetchone()
            if row and row[0] is not None:
                return {"backend": "sqlite", "db_path": self.db_path, "rows": int(row[0]), "prefix_len": self.prefix_len, "cached": True}
        except Exception:
            # meta table might not exist; fall back to full count
            pass
        cur = self.conn.execute("SELECT COUNT(*) FROM passwords;")
        total = cur.fetchone()[0]
        return {"backend": "sqlite", "db_path": self.db_path, "rows": total, "prefix_len": self.prefix_len, "cached": False}

    def get_suffixes(self, prefix: str) -> List[Tuple[str, int]]:
        p = prefix.upper()
        if len(p) != self.prefix_len or any(c not in HEX for c in p):
            return []
        lo = p
        hi = _prefix_upper_bound(p)
        # Range query on the PRIMARY KEY (hash)
        # substr(hash, N) returns suffix starting at N (1-based)
        cur = self.conn.execute(
            "SELECT substr(hash, ?), count "
            "FROM passwords WHERE hash >= ? AND hash < ? ORDER BY hash;",
            (self.prefix_len + 1, lo, hi)
        )
        return cur.fetchall()

    def get_count_for_hash(self, sha1_hex: str) -> int:
        h = sha1_hex.upper()
        if len(h) != 40 or any(c not in HEX for c in h):
            return 0
        cur = self.conn.execute("SELECT count FROM passwords WHERE hash = ?;", (h,))
        row = cur.fetchone()
        return int(row[0]) if row else 0
