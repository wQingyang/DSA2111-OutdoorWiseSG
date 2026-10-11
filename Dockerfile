FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY outdoorwise ./outdoorwise
RUN pip install --no-cache-dir .
COPY config ./config
COPY frontend ./frontend
COPY data/catalog ./data/catalog
RUN mkdir -p /app/data/runtime
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "outdoorwise.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
