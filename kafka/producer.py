#!/usr/bin/env python3
import csv
import json
import time
import uuid
from confluent_kafka import Producer

def load_config(path="kafka/client.properties"):
    """
    Load Kafka client properties from file into a dict.
    Expects lines like: key=value
    Ignores blank lines and comments (#).
    """
    conf = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, val = line.split("=", 1)
            conf[key.strip()] = val.strip()
    return conf

def delivery_report(err, msg):
    """Callback for message delivery reports."""
    if err is not None:
        print(f"❌ Message delivery failed: {err}")
    else:
        print(f"✅ Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

def stream_transactions(csv_path, topic, delay, count=None):
    """Read CSV and send each row as a JSON message to Kafka."""
    conf = load_config()
    producer = Producer(conf)
    print(f"Starting stream → topic '{topic}'")

    with open(csv_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for i, row in enumerate(reader):
            if count is not None and i >= count:
                break
            key = str(uuid.uuid4())
            value = json.dumps(row)
            producer.produce(
                topic=topic,
                key=key,
                value=value,
                callback=delivery_report
            )
            # Serve delivery callbacks
            producer.poll(0)
            time.sleep(delay)

    # Wait for all messages to be delivered
    producer.flush()
    print("Stream complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Kafka producer for fraud transactions."
    )
    parser.add_argument(
        "--topic",
        default="raw-transactions",
        help="Kafka topic to send raw transaction data into"
    )
    parser.add_argument(
        "--file",
        default="data/fraud_sample_fixed.csv",
        help="Path to the transactions CSV file"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Seconds to wait between sending messages"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Optional: stop after sending N messages"
    )
    args = parser.parse_args()

    stream_transactions(args.file, args.topic, args.delay, count=args.count)
