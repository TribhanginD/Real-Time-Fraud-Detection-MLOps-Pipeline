import json
import pandas as pd
import requests
from kafka import KafkaConsumer, KafkaProducer
from model.train_model import feature_engineer, drop_high_missing
from prometheus_client import start_http_server, Counter, Histogram
import time

# Start Prometheus metrics server on port 8000
start_http_server(8000)

# MLflow REST endpoint
SCORING_URL = "http://127.0.0.1:5000/invocations"

# Kafka setup
# Create a counter
scored_counter = Counter("scored_transactions_total", "Number of scored transactions")
failed_counter = Counter("failed_transactions_total", "Number of failed scoring attempts")
latency_histogram = Histogram("scoring_latency_seconds", "Latency of model scoring requests")


consumer = KafkaConsumer(
    "raw-transactions",
    bootstrap_servers="localhost:9092",
    auto_offset_reset="earliest",
    value_deserializer=lambda m: json.loads(m.decode("utf-8"))
)
producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda m: json.dumps(m).encode("utf-8"),
)

print("📡 Kafka consumer started...")

for msg in consumer:
    record = msg.value  # incoming dict from producer

    try:
        start_time = time.time()
        
        df = pd.DataFrame([record])

        # Optional cleaning 
        df = drop_high_missing(df,0.90)
        df = df.apply(lambda col: pd.to_numeric(col, errors="coerce"))
        df = feature_engineer(df)
        X = df.fillna(0).drop("isFraud", axis=1, errors="ignore")

        # Prepare MLflow request payload
        payload = {"dataframe_records": X.to_dict(orient="records")}
        response = requests.post(SCORING_URL, json=payload)
        response.raise_for_status()
        prediction = response.json()["predictions"][0]

        # Attach and send result
        record["fraud_score"] = float(prediction)
        producer.send("scored-transactions", record)
        # After successful prediction
        latency = time.time() - start_time
        latency_histogram.observe(latency)
        scored_counter.inc()
        print(f" Scored record → fraud_score: {prediction} (latency: {latency:.3f}s)")



    except Exception as e:
        print(f"Failed to score record: {e}")
        # print("🪵 Record:", record)
        failed_counter.inc()


print("Kafka consumer session complete.")
