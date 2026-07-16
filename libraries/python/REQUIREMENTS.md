# Python — what to install

## Toolchain (install on the machine)

- **Python ≥ 3.11**
- **pip**
- To build a wheel: `pip install build` (uses the `hatchling` backend declared in `pyproject.toml`)

## Library dependencies

Each package pins its dependencies. Install per package with either the
`requirements.txt` or the package itself:

```bash
cd logs   && pip install -r requirements.txt     # or: pip install .
cd traces && pip install -r requirements.txt     # or: pip install .
```

**`logs`** (`logs/requirements.txt`):
- `opentelemetry-api==1.41.0`
- `opentelemetry-sdk==1.41.0`
- `opentelemetry-exporter-otlp-proto-http==1.41.0`

**`traces`** (`traces/requirements.txt`) — the above plus:
- `opentelemetry-instrumentation-flask==0.62b0`
- `opentelemetry-instrumentation-requests==0.62b0`

## To run the tests

```bash
pip install pytest
cd logs   && PYTHONPATH=src python -m pytest -q
cd traces && PYTHONPATH=src python -m pytest -q
```
