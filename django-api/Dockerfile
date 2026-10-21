FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Sin compilador: todas las dependencias (psycopg2-binary incluido) llegan
# ya compiladas para x86 y para el ARM del servidor de Oracle. Antes se
# instalaban gcc y libpq-dev en cada imagen sin usarlos: cientos de MB y
# un paso más en cada actualización.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
