FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

CMD ["bash", "-lc", "set -euo pipefail; python manage.py makemigrations --noinput; python manage.py migrate; python manage.py collectstatic --noinput; python manage.py createsuperuser --noinput || true; exec gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
