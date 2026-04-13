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

CMD ["bash", "-lc", "set -euo pipefail; python - <<'PY'\nimport os, socket, time\nhost = os.getenv('MYSQL_HOST', 'mysql')\nport = int(os.getenv('MYSQL_PORT', '3306'))\nfor i in range(60):\n    try:\n        with socket.create_connection((host, port), timeout=2):\n            break\n    except OSError:\n        if i == 59:\n            raise\n        time.sleep(1)\nPY\npython manage.py migrate contenttypes 0001 --noinput --fake-initial || true\nif python - <<'PY'\nimport os, sys, MySQLdb\nconn = MySQLdb.connect(\n    host=os.getenv('MYSQL_HOST', 'mysql'),\n    port=int(os.getenv('MYSQL_PORT', '3306')),\n    user=os.getenv('MYSQL_USER', 'cashline'),\n    passwd=os.getenv('MYSQL_PASSWORD', 'cashline123'),\n    db=os.getenv('MYSQL_DATABASE', 'cashline'),\n)\ncur = conn.cursor()\ncur.execute(\"\"\"\nSELECT COUNT(1)\nFROM information_schema.COLUMNS\nWHERE TABLE_SCHEMA = DATABASE()\n  AND TABLE_NAME='django_content_type'\n  AND COLUMN_NAME='name'\n\"\"\")\nhas_name = cur.fetchone()[0] > 0\nconn.close()\nsys.exit(0 if has_name else 10)\nPY\nthen\n  :\nelse\n  rc=$?\n  if [ \"$rc\" -eq 10 ]; then\n    python manage.py migrate contenttypes 0002 --fake --noinput\n  else\n    exit \"$rc\"\n  fi\nfi\npython manage.py migrate --noinput --fake-initial; python manage.py collectstatic --noinput; python manage.py createsuperuser --noinput || true; exec gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
