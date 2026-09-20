import os
import csv
import random
import asyncio
import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app import database as db
from app.detector import detector, merchant_risk, MERCHANT_RISK
from app.agent import explain_transaction
from app.schemas import CheckResponse, OverrideRequest, NewTransactionRequest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(BASE_DIR, "data", "upi_transactions.csv")
STATIC_DIR = os.path.join(BASE_DIR, "static")

MERCHANTS = list(MERCHANT_RISK.keys())

app = FastAPI(title="UPI Fraud Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_from_csv_if_empty():
    if db.count_rows() > 0:
        return
    if not os.path.exists(DATA_CSV):
        return
    rows = []
    with open(DATA_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                (
                    r["transaction_id"],
                    r["ts"],
                    r["user_id"],
                    float(r["amount"]),
                    r["merchant"],
                    r["decision"],
                    float(r["risk_score"]),
                    r.get("reasons", ""),
                    int(r["hour"]),
                )
            )
    db.bulk_insert(rows)


def make_synthetic_transaction(idx: int):
    now = datetime.datetime.now()
    user_id = f"U{random.randint(1000, 9999)}"
    merchant = random.choices(
        MERCHANTS, weights=[1 if merchant_risk(m) < 0.5 else 0.06 for m in MERCHANTS]
    )[0]
    risk = merchant_risk(merchant)
    is_new_device = random.random() < 0.08
    is_new_location = random.random() < 0.08
    amount = round(random.choice(
        [random.uniform(50, 3000), random.uniform(3000, 20000), random.uniform(20000, 120000)]
    ), 2) if random.random() < 0.97 else round(random.uniform(20000, 150000), 2)

    features = {
        "amount": amount,
        "hour": now.hour,
        "is_new_device": int(is_new_device),
        "is_new_location": int(is_new_location),
        "merchant_risk": risk,
        "txn_freq_1h": random.choice([0, 0, 0, 1, 2, 6]),
    }
    decision, score, reasons = detector.predict(features)
    txn_id = f"TXN_{random.randint(100000, 999999)}"
    return {
        "transaction_id": txn_id,
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "hour": now.hour,
        "user_id": user_id,
        "amount": amount,
        "merchant": merchant,
        "decision": decision,
        "risk_score": score,
        "reasons": reasons,
    }


async def live_transaction_stream():
    """Background task: keeps generating a new synthetic transaction every
    few seconds so the dashboard feels like a real-time command center."""
    while True:
        await asyncio.sleep(4)
        try:
            txn = make_synthetic_transaction(0)
            db.insert_transaction(txn)
        except Exception as e:
            print("stream error:", e)


@app.on_event("startup")
async def startup():
    db.init_db()
    seed_from_csv_if_empty()
    asyncio.create_task(live_transaction_stream())


# ---------- API ROUTES ----------

@app.get("/api/health")
def health():
    return {"status": "online", "time": datetime.datetime.now().isoformat()}


@app.get("/api/stats")
def stats():
    s = db.get_stats()
    total = s["total"] or 1
    return {
        "total": s["total"],
        "fraud": s["fraud"],
        "review": s["review"],
        "real": s["real"],
        "fraud_pct": round(100 * s["fraud"] / total, 2),
        "review_pct": round(100 * s["review"] / total, 2),
        "real_pct": round(100 * s["real"] / total, 2),
    }


@app.get("/api/transactions/recent")
def recent(limit: int = 8):
    return db.get_recent(limit)


@app.get("/api/transactions/trend")
def trend():
    return db.get_trend()


@app.post("/api/check", response_model=CheckResponse)
def check_transaction(req: dict):
    txn_id = req.get("transaction_id", "").strip()
    if not txn_id:
        raise HTTPException(400, "transaction_id is required")
    row = db.get_by_id(txn_id)
    if not row:
        return CheckResponse(found=False, message=f"No transaction found with ID {txn_id}")
    reasons = row["reasons"].split("|") if row["reasons"] else []
    explanation = explain_transaction(row, reasons, row["decision"], row["risk_score"])
    return CheckResponse(
        found=True,
        transaction_id=row["transaction_id"],
        decision=row["decision"],
        risk_score=row["risk_score"],
        amount=row["amount"],
        user_id=row["user_id"],
        merchant=row["merchant"],
        ts=row["ts"],
        reasons=reasons,
        ai_explanation=explanation,
    )


@app.post("/api/transaction/predict")
def predict_new(req: NewTransactionRequest):
    now = datetime.datetime.now()
    features = {
        "amount": req.amount,
        "hour": now.hour,
        "is_new_device": int(req.is_new_device),
        "is_new_location": int(req.is_new_location),
        "merchant_risk": merchant_risk(req.merchant),
        "txn_freq_1h": 0,
    }
    decision, score, reasons = detector.predict(features)
    txn = {
        "transaction_id": f"TXN_{random.randint(100000, 999999)}",
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "hour": now.hour,
        "user_id": req.user_id,
        "amount": req.amount,
        "merchant": req.merchant,
        "decision": decision,
        "risk_score": score,
        "reasons": reasons,
    }
    db.insert_transaction(txn)
    explanation = explain_transaction(txn, reasons, decision, score)
    return {**txn, "ai_explanation": explanation}


@app.post("/api/transaction/override")
def override_real(req: OverrideRequest):
    row = db.get_by_id(req.transaction_id)
    if not row:
        raise HTTPException(404, "transaction not found")
    db.update_decision(req.transaction_id, "REAL", 0.05)
    return {"transaction_id": req.transaction_id, "decision": "REAL"}


@app.post("/api/transaction/report")
def report_fraud(req: OverrideRequest):
    row = db.get_by_id(req.transaction_id)
    if not row:
        raise HTTPException(404, "transaction not found")
    db.update_decision(req.transaction_id, "FRAUD", 0.97)
    return {"transaction_id": req.transaction_id, "decision": "FRAUD"}


# ---------- STATIC DASHBOARD ----------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))