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
RUN find /app/apps/orders/migrations -type f -name '0*.py' \
    ! -name '0001_initial.py' \
    ! -name '0002_organizationorder_qty_coin_001.py' \
    ! -name '0003_organizationorder_long_table.py' \
    -delete

EXPOSE 8000

CMD ["bash", "-lc", "set -euo pipefail; python - <<'PY'\nimport os, socket, time\nhost = os.getenv('MYSQL_HOST', 'mysql')\nport = int(os.getenv('MYSQL_PORT', '3306'))\nfor i in range(60):\n    try:\n        with socket.create_connection((host, port), timeout=2):\n            break\n    except OSError:\n        if i == 59:\n            raise\n        time.sleep(1)\nPY\npython manage.py migrate --noinput; python manage.py collectstatic --noinput; python manage.py createsuperuser --noinput || true; exec gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
