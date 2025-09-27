#!/usr/bin/env python3
"""
CSV -> SQLite ingester (no header).
CSV lines expected: SHA1HEX,count
"""
import argparse, csv, os, sqlite3
from pathlib import Path

def ensure_db(db_path: str):
    Path(os.path.dirname(db_path) or ".").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS passwords(
            hash TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        );
    """)
    # meta table for quick stats
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    conn.commit()
    return conn

def flush(conn, rows):
    conn.executemany(
        "INSERT INTO passwords(hash, count) VALUES (?, ?) "
        "ON CONFLICT(hash) DO UPDATE SET count=excluded.count;",
        rows
    )
    conn.commit()

def ingest(conn, csv_path: str, batch: int = 100000):
    print(f"[INGEST] {csv_path}")
    total = 0
    buf = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            h = row[0].strip().upper()
            if len(row) < 2:
                continue
            try:
                cnt = int(row[1].strip())
            except Exception:
                continue
            if len(h) != 40:
                continue
            buf.append((h, cnt))
            if len(buf) >= batch:
                flush(conn, buf)
                total += len(buf)
                buf.clear()
        if buf:
            flush(conn, buf)
            total += len(buf)

    # At the end of ingest, compute total rows once and store in meta
    cur = conn.execute("SELECT COUNT(*) FROM passwords;")
    rows = cur.fetchone()[0]
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('row_count', ?);", (str(rows),))
    conn.commit()

    print(f"[DONE] inserted/processed approx rows={total:,}; total DB rows={rows:,}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="SQLite DB path e.g. data/pwned.db")
    ap.add_argument("--csv", required=True, help="CSV file path (no header)")
    ap.add_argument("--batch", type=int, default=100000, help="rows per commit")
    args = ap.parse_args()

    conn = ensure_db(args.db)
    ingest(conn, args.csv, args.batch)
    conn.close()

if __name__ == "__main__":
    main()
