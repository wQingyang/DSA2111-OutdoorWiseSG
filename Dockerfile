FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OUTDOORWISE_DATA_ROOT=/app/data
COPY pyproject.toml ./
COPY outdoorwise ./outdoorwise
RUN pip install --no-cache-dir .
COPY config ./config
COPY frontend ./frontend
COPY prediction ./prediction
# Historical cards read this immutable offline evaluation evidence.
COPY docs/forecast_evaluation.json ./docs/forecast_evaluation.json
COPY data/catalog ./data/catalog
# Historical experiment is explicitly isolated and optional at runtime.
COPY data/datasets/snapshot_20261015 ./data/datasets/snapshot_20261015
RUN useradd --uid 10001 --create-home outdoorwise && mkdir -p /app/data/runtime && chown -R 10001:10001 /app/data/runtime
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "outdoorwise.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
