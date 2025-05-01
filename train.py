import mlflow
import mlflow.sklearn
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.datasets import make_classification

# MLflow tracking setup
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("FraudDetection")

# Generate dummy data (replace with real credit card data)
X, y = make_classification(n_samples=10000, n_features=20, weights=[0.9, 0.1], random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, random_state=42)

with mlflow.start_run():
    model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1)
    model.fit(X_train, y_train)

    preds = model.predict_proba(X_test)[:, 1]
    roc_auc = roc_auc_score(y_test, preds)

    mlflow.log_metric("roc_auc", roc_auc)
    mlflow.sklearn.log_model(model, "model")
    print(f"ROC AUC: {roc_auc:.4f}")