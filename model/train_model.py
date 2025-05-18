#!/usr/bin/env python3
"""
train_model.py

Train a LightGBM model on transaction data (full IEEE-CIS dataset), log runs to MLflow, save the best model,
and automatically register it in MLflow Model Registry.
"""
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from lightgbm import LGBMClassifier
from sklearn.metrics import roc_auc_score, precision_score, recall_score
import joblib
import mlflow
import mlflow.lightgbm
from mlflow.tracking import MlflowClient

# Constants
TXN_PATH        = "data/train_transaction.csv"
ID_PATH         = "data/train_identity.csv"
MODEL_PATH      = "model/model.pkl"
MLFLOW_URI      = "http://localhost:5001"  # MLflow server URI
MISSING_THRESH  = 0.90                      # drop cols with >90% missing
MODEL_NAME      = "FraudDetectorLGBM"


def load_full_data(txn_path: str, id_path: str) -> pd.DataFrame:
    """Load and merge transaction+identity tables on TransactionID."""
    txn = pd.read_csv(txn_path)
    ident = pd.read_csv(id_path)
    df = txn.merge(ident, how="left", on="TransactionID")
    return df


def drop_high_missing(df: pd.DataFrame, thresh: float) -> pd.DataFrame:
    """Drop columns with fraction of missing values > thresh."""
    missing_frac = df.isna().mean()
    drop_cols = missing_frac[missing_frac > thresh].index.tolist()
    return df.drop(columns=drop_cols)


def feature_engineer(df):
    origin = pd.Timestamp("2017-12-01")

    # Optional: Convert all numeric-like columns safely
    df = df.apply(lambda col: pd.to_numeric(col, errors="ignore"))

    # Robust handling of TransactionDT (optional feature)
    if "TransactionDT" in df.columns:
        try:
            df["TransactionDT"] = pd.to_timedelta(df["TransactionDT"], unit="s") + origin
            df["hour"] = df["TransactionDT"].dt.hour
            df["dayofweek"] = df["TransactionDT"].dt.dayofweek
        except Exception as e:
            print(f"Failed to process 'TransactionDT': {e}")
        df.drop("TransactionDT", axis=1, inplace=True, errors="ignore")
    else:
        # Provide default values if TransactionDT is absent
        df["hour"] = -1
        df["dayofweek"] = -1

    return df




def eval_metrics(y_true, y_pred_proba, y_pred):
    return {
        "roc_auc": roc_auc_score(y_true, y_pred_proba),
        "precision": precision_score(y_true, y_pred),
        "recall": recall_score(y_true, y_pred),
    }


def main():
    # Configure MLflow
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("fraud_detection")

    # Load & preprocess
    df = load_full_data(TXN_PATH, ID_PATH)
    df = drop_high_missing(df, MISSING_THRESH)
    df = feature_engineer(df)

    # Features/target split
    X = df.drop("isFraud", axis=1)
    y = df["isFraud"]

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    with mlflow.start_run() as run:
        # Log params
        mlflow.log_param("n_samples", len(df))
        mlflow.log_param("n_features", X.shape[1])

        # Train model
        model = LGBMClassifier(
            n_estimators=100,
            learning_rate=0.1,
            random_state=42
        )
        model.fit(X_train, y_train)

        # Evaluate
        y_proba = model.predict_proba(X_test)[:,1]
        y_pred  = (y_proba >= 0.5).astype(int)
        metrics = eval_metrics(y_test, y_proba, y_pred)
        for k, v in metrics.items():
            mlflow.log_metric(k, v)

        # Log model artifact to MLflow
        mlflow.lightgbm.log_model(model, artifact_path="lgbm-model")

        # Save local copy
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        print(f"Model saved to {MODEL_PATH}")

    # After run completes, register in Model Registry
    run_id = run.info.run_id
    client = MlflowClient()
    try:
        client.create_registered_model(MODEL_NAME)
    except Exception:
        pass  # already exists
    model_uri = f"runs:/{run_id}/lgbm-model"
    mv = client.create_model_version(name=MODEL_NAME, source=model_uri, run_id=run_id)
    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=mv.version,
        stage="Staging",
        archive_existing_versions=False
    )
    print(f"Registered {MODEL_NAME} version {mv.version} to 'Staging'")
    # ➕ Add model version tag
    client.set_tag(run_id, "mlflow.version", mv.version)

    # Return AUC so that DAG can optionally use it
    return metrics["roc_auc"]

if __name__ == "__main__":
    main()
