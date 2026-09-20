"""Train a RandomForest fraud classifier on data/upi_transactions.csv
and save the bundle to models/model.joblib.
"""
import os
import sys
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

DATA_CSV = os.path.join(BASE_DIR, "data", "upi_transactions.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "model.joblib")

FEATURES = ["amount", "hour", "is_new_device", "is_new_location", "merchant_risk", "txn_freq_1h"]


def main():
    if not os.path.exists(DATA_CSV):
        print("Dataset not found. Run scripts/generate_data.py first.")
        sys.exit(1)

    df = pd.read_csv(DATA_CSV)
    X = df[FEATURES]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200, max_depth=8, class_weight="balanced", random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    print(classification_report(y_test, preds, digits=3))
    try:
        print("ROC AUC:", round(roc_auc_score(y_test, proba), 4))
    except ValueError:
        pass

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES}, MODEL_PATH)
    print(f"Saved model to {MODEL_PATH}")


if __name__ == "__main__":
    main()