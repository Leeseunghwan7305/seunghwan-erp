FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 (psycopg2 빌드용은 binary 패키지라 불필요하지만, 안정성 위해 최소 유지)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
