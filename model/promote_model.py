import os
from mlflow.tracking import MlflowClient

MLFLOW_URI = os.getenv("MLFLOW_URI", "http://localhost:5001")
MODEL_NAME = "FraudDetectorLGBM"

client = MlflowClient(tracking_uri=MLFLOW_URI)

# Get new (Staging) version
staging_version = None
for mv in client.search_model_versions(f"name='{MODEL_NAME}'"):
    if mv.current_stage == "Staging":
        staging_version = mv
        break

if not staging_version:
    print("No model in Staging. Skipping promotion.")
    exit(1)

# Get AUC of new model
new_auc = float(client.get_metric_history(staging_version.run_id, "roc_auc")[-1].value)

# Find current Production model (if any)
prod_versions = [
    mv for mv in client.search_model_versions(f"name='{MODEL_NAME}'")
    if mv.current_stage == "Production"
]

if prod_versions:
    current_prod = prod_versions[0]
    prod_auc = float(client.get_metric_history(current_prod.run_id, "roc_auc")[-1].value)

    print(f"AUC — New: {new_auc:.4f} | Current Prod: {prod_auc:.4f}")

    if new_auc > prod_auc:
        client.transition_model_version_stage(
            name=MODEL_NAME,
            version=staging_version.version,
            stage="Production",
            archive_existing_versions=True,
        )
        print(f"Promoted version {staging_version.version} to Production.")
    else:
        print("New model did not outperform current Production. No promotion.")
else:
    # No production model yet — promote directly
    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=staging_version.version,
        stage="Production",
        archive_existing_versions=False,
    )
    print(f"First-time promotion: version {staging_version.version} promoted to Production.")
