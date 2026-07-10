FROM python:3.11-slim
WORKDIR /app
# Install the locally-built logs + traces wheels first (from build context).
COPY artifacts/otel_logs-0.1.0-py3-none-any.whl /tmp/
COPY artifacts/otel_traces-0.1.0-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/otel_logs-0.1.0-py3-none-any.whl /tmp/otel_traces-0.1.0-py3-none-any.whl
COPY apps/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/python/app.py .
EXPOSE 8000
CMD ["python", "app.py"]
