FROM postgres:16
FROM apache/airflow:2.10.2

RUN apt-get update && apt-get install -y \
    postgresql-16-postgis-3 \
    postgresql-16-pgvector \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt