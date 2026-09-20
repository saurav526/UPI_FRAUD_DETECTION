import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "upi_fraud.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            ts TEXT,
            user_id TEXT,
            amount REAL,
            merchant TEXT,
            decision TEXT,
            risk_score REAL,
            reasons TEXT,
            hour INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def count_rows():
    conn = get_conn()
    c = conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"]
    conn.close()
    return c


def insert_transaction(t):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO transactions
        (transaction_id, ts, user_id, amount, merchant, decision, risk_score, reasons, hour)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            t["transaction_id"],
            t["ts"],
            t["user_id"],
            t["amount"],
            t["merchant"],
            t["decision"],
            t["risk_score"],
            "|".join(t.get("reasons", [])),
            t.get("hour", 0),
        ),
    )
    conn.commit()
    conn.close()


def bulk_insert(rows):
    conn = get_conn()
    conn.executemany(
        """INSERT OR REPLACE INTO transactions
        (transaction_id, ts, user_id, amount, merchant, decision, risk_score, reasons, hour)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    conn.close()


def get_recent(limit=10):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_by_id(txn_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id=?", (txn_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM transactions").fetchone()["c"]
    fraud = conn.execute(
        "SELECT COUNT(*) c FROM transactions WHERE decision='FRAUD'"
    ).fetchone()["c"]
    review = conn.execute(
        "SELECT COUNT(*) c FROM transactions WHERE decision='REVIEW'"
    ).fetchone()["c"]
    real = conn.execute(
        "SELECT COUNT(*) c FROM transactions WHERE decision='REAL'"
    ).fetchone()["c"]
    conn.close()
    return {"total": total, "fraud": fraud, "review": review, "real": real}


def get_trend():
    """Return count of REAL/REVIEW/FRAUD transactions bucketed by hour-of-day."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT hour, decision, COUNT(*) c
        FROM transactions
        GROUP BY hour, decision
        ORDER BY hour
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_decision(txn_id, decision, score=None):
    conn = get_conn()
    if score is not None:
        conn.execute(
            "UPDATE transactions SET decision=?, risk_score=? WHERE transaction_id=?",
            (decision, score, txn_id),
        )
    else:
        conn.execute(
            "UPDATE transactions SET decision=? WHERE transaction_id=?",
            (decision, txn_id),
        )
    conn.commit()
    conn.close()