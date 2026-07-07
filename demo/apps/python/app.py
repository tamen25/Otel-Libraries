# Python entry service: logs an order then calls the Java service.
import os
import uuid

import requests
from flask import Flask, jsonify

from cloudops_otel_logs import logger

app = Flask(__name__)
JAVA_URL = os.getenv("JAVA_URL", "http://java-app:8080/process")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/order")
def order():
    order_id = str(uuid.uuid4())
    logger.info("order received", {"order_id": order_id, "hop": "python"})
    try:
        resp = requests.get(JAVA_URL, params={"order_id": order_id}, timeout=5)
        logger.info("java responded", {"order_id": order_id, "status": resp.status_code})
    except Exception as exc:  # noqa: BLE001 - demo: log and surface any downstream failure
        logger.error("java call failed", {"order_id": order_id, "error": str(exc)})
        logger.export_logs()
        return jsonify(order_id=order_id, ok=False), 502
    logger.export_logs()
    return jsonify(order_id=order_id, ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
