"""Generate a synthetic UPI transaction dataset.

Produces data/upi_transactions.csv with ~10,000 rows and a fraud rate that
mirrors a realistic production distribution (~2% fraud, ~3% review, rest
legitimate), used both to train the model and to seed the live dashboard.
"""
import os
import csv
import random
import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.detector import MERCHANT_RISK, merchant_risk, FraudDetector

random.seed(42)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE_DIR, "data", "upi_transactions.csv")

N_ROWS = 10000
MERCHANTS = list(MERCHANT_RISK.keys())


def random_timestamp_last_24h():
    now = datetime.datetime.now()
    delta = datetime.timedelta(
        hours=random.randint(0, 23), minutes=random.randint(0, 59), seconds=random.randint(0, 59)
    )
    return now - delta


LOW_RISK_MERCHANTS = [m for m in MERCHANTS if merchant_risk(m) < 0.5]
HIGH_RISK_MERCHANTS = [m for m in MERCHANTS if merchant_risk(m) >= 0.5]


def gen_row(i, detector):
    ts = random_timestamp_last_24h()
    user_id = f"U{random.randint(1000, 9999)}"

    # ~5% of transactions are drawn from a "risky" template where several
    # risk factors correlate (as real fraud patterns tend to), so the
    # overall dataset lands close to a realistic ~2% fraud / ~3% review /
    # ~95% legitimate split, instead of independent low-probability flags
    # that almost never stack up together.
    is_risky = random.random() < 0.05

    if is_risky:
        merchant = random.choice(HIGH_RISK_MERCHANTS)
        is_new_device = 1 if random.random() < 0.55 else 0
        is_new_location = 1 if random.random() < 0.5 else 0
        txn_freq_1h = random.choice([0, 1, 2, 6, 7, 8])
        roll = random.random()
        if roll < 0.4:
            amount = round(random.uniform(200, 15000), 2)
        elif roll < 0.75:
            amount = round(random.uniform(15000, 60000), 2)
        else:
            amount = round(random.uniform(60000, 150000), 2)
    else:
        merchant = random.choice(LOW_RISK_MERCHANTS)
        is_new_device = 1 if random.random() < 0.04 else 0
        is_new_location = 1 if random.random() < 0.04 else 0
        txn_freq_1h = random.choice([0, 0, 0, 0, 0, 1, 1, 2])
        roll = random.random()
        if roll < 0.97:
            amount = round(random.uniform(20, 5000), 2)
        elif roll < 0.995:
            amount = round(random.uniform(5000, 25000), 2)
        else:
            amount = round(random.uniform(25000, 60000), 2)

    risk = merchant_risk(merchant)

    features = {
        "amount": amount,
        "hour": ts.hour,
        "is_new_device": is_new_device,
        "is_new_location": is_new_location,
        "merchant_risk": risk,
        "txn_freq_1h": txn_freq_1h,
    }
    decision, score, reasons = detector.predict(features)

    return {
        "transaction_id": f"TXN_{100000 + i}",
        "ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "hour": ts.hour,
        "user_id": user_id,
        "amount": amount,
        "merchant": merchant,
        "is_new_device": is_new_device,
        "is_new_location": is_new_location,
        "merchant_risk": risk,
        "txn_freq_1h": txn_freq_1h,
        "decision": decision,
        "risk_score": score,
        "reasons": "|".join(reasons),
        "label": 1 if decision == "FRAUD" else 0,
    }


def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    detector = FraudDetector()  # rule-based (no model.joblib yet) -> used to label data
    fieldnames = [
        "transaction_id", "ts", "hour", "user_id", "amount", "merchant",
        "is_new_device", "is_new_location", "merchant_risk", "txn_freq_1h",
        "decision", "risk_score", "reasons", "label",
    ]
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(N_ROWS):
            writer.writerow(gen_row(i, detector))

    print(f"Wrote {N_ROWS} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()