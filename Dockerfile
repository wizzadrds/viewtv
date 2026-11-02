FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/viewtv/backend:/opt/viewtv

WORKDIR /opt/viewtv

COPY backend /opt/viewtv/backend
RUN pip install --no-cache-dir /opt/viewtv/backend

COPY worker /opt/viewtv/worker

WORKDIR /opt/viewtv
CMD ["uvicorn", "app.main:app", "--app-dir", "/opt/viewtv/backend", "--host", "0.0.0.0", "--port", "8000"]
