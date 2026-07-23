FROM python:3.12-slim

WORKDIR /app
COPY generator.py /app/generator.py

USER 65532:65532
ENTRYPOINT ["python", "/app/generator.py"]
