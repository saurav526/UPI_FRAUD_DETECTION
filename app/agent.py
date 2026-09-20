import os
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def explain_transaction(txn: dict, reasons: list, decision: str, score: float) -> str:
    """Return a short natural-language explanation of why a transaction was
    flagged. Uses Groq if GROQ_API_KEY is set in the environment, otherwise
    falls back to a deterministic template so the dashboard always works
    out of the box."""
    if GROQ_API_KEY:
        try:
            return _ask_groq(txn, reasons, decision, score)
        except Exception:
            pass
    return _fallback_explanation(reasons, decision, score)


def _ask_groq(txn, reasons, decision, score):
    prompt = (
        "You are a fraud investigator AI for a UPI payments platform. "
        f"Transaction {txn.get('transaction_id')}: amount ₹{txn.get('amount')}, "
        f"merchant {txn.get('merchant')}, user {txn.get('user_id')}, "
        f"risk score {score}, decision {decision}. "
        f"Flag reasons: {', '.join(reasons)}. "
        "Write a 2-3 sentence plain-English explanation of why this transaction "
        "was flagged this way, for a fraud analyst reviewing it. Be concise."
    )
    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 200,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _fallback_explanation(reasons, decision, score):
    reason_text = "; ".join(r.lower() for r in reasons)
    if decision == "FRAUD":
        return (
            f"This transaction is flagged as fraud due to a combination of {reason_text}. "
            "Recommend holding the funds and contacting the user before release."
        )
    if decision == "REVIEW":
        return (
            f"This transaction shows moderate risk (score {score}) because of {reason_text}. "
            "It doesn't clearly indicate fraud but warrants a manual look."
        )
    return (
        f"This transaction looks consistent with normal behavior (score {score}); "
        "no major risk signals were found."
    )