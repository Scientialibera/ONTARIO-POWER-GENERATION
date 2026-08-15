FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY pyproject.toml .
COPY app/ app/
COPY services/ services/
COPY domain/ domain/
COPY ml/ ml/
COPY frontend/ frontend/
COPY data/sample/ data/sample/
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
