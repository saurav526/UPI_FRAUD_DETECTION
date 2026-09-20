import os
import joblib
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.joblib")

DEFAULT_FEATURES = [
    "amount",
    "hour",
    "is_new_device",
    "is_new_location",
    "merchant_risk",
    "txn_freq_1h",
]

# Simple merchant risk lookup used both for synthetic data generation
# and for scoring transactions coming in from the API / dashboard.
MERCHANT_RISK = {
    "Amazon Pay": 0.05,
    "Flipkart": 0.05,
    "Swiggy": 0.05,
    "Zomato": 0.05,
    "PhonePe": 0.05,
    "Google Pay": 0.05,
    "Paytm": 0.08,
    "IRCTC": 0.05,
    "BookMyShow": 0.1,
    "Myntra": 0.05,
    "BigBasket": 0.05,
    "RummyCircle": 0.85,
    "Dream11": 0.7,
    "Unknown Merchant": 0.9,
    "Crypto Exchange": 0.8,
    "Betting App": 0.9,
}


def merchant_risk(name: str) -> float:
    return MERCHANT_RISK.get(name, 0.2)


class FraudDetector:
    def __init__(self):
        self.model = None
        self.feature_names = DEFAULT_FEATURES
        self.load()

    def load(self):
        if os.path.exists(MODEL_PATH):
            bundle = joblib.load(MODEL_PATH)
            self.model = bundle["model"]
            self.feature_names = bundle["features"]

    def predict(self, features: dict):
        """features: dict with keys matching self.feature_names.
        Returns (decision, score, reasons)."""
        if self.model is not None:
            x = pd.DataFrame([[features.get(f, 0) for f in self.feature_names]], columns=self.feature_names)
            score = float(self.model.predict_proba(x)[0][1])
        else:
            score = self._rule_score(features)

        score = round(min(max(score, 0.0), 0.99), 2)

        if score >= 0.75:
            decision = "FRAUD"
        elif score >= 0.40:
            decision = "REVIEW"
        else:
            decision = "REAL"

        reasons = self._reasons(features)
        return decision, score, reasons

    def _rule_score(self, f):
        score = 0.05
        if f.get("amount", 0) > 50000:
            score += 0.30
        elif f.get("amount", 0) > 20000:
            score += 0.12
        if f.get("is_new_device"):
            score += 0.20
        if f.get("is_new_location"):
            score += 0.15
        if f.get("merchant_risk", 0) > 0.6:
            score += 0.25
        hour = f.get("hour", 12)
        if hour < 5 or hour >= 23:
            score += 0.10
        if f.get("txn_freq_1h", 0) > 5:
            score += 0.15
        return min(score, 0.98)

    def _reasons(self, f):
        reasons = []
        if f.get("amount", 0) > 50000:
            reasons.append("High transaction amount (outlier detected)")
        hour = f.get("hour", 12)
        if hour < 5 or hour >= 23:
            reasons.append("Unusual time pattern (late night)")
        if f.get("is_new_device") or f.get("is_new_location"):
            reasons.append("New device / location")
        if f.get("merchant_risk", 0) > 0.6:
            reasons.append("Suspicious merchant category (gambling/high-risk)")
        if f.get("txn_freq_1h", 0) > 5:
            reasons.append("Frequent transactions in short time")
        if not reasons:
            reasons.append("No strong risk signals detected")
        return reasons


detector = FraudDetector()