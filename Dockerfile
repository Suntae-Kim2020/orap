FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 설치 (레이어 캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드
COPY app.py gcs_sync.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# uploads 디렉토리는 런타임 쓰기용 (빈 디렉토리 생성)
RUN mkdir -p /app/uploads /app/snapshots

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# gunicorn: 단일 워커 + 멀티스레드 (SQLite + GCS 동기화 안전성)
# timeout 600s — 대용량 CSV 임포트 대응
CMD exec gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 4 \
    --timeout 600 \
    --graceful-timeout 60 \
    app:app
