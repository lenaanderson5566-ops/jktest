#!/usr/bin/env bash
set -euo pipefail

# Keep runtime deps aligned with bind-mounted source code in docker-compose dev mode.
pip install --no-cache-dir -r requirements.txt

python manage.py migrate
python manage.py collectstatic --noinput

python manage.py shell -c "from django.contrib.auth import get_user_model;import os;U=get_user_model();u=os.getenv('DJANGO_SUPERUSER_USERNAME','admin');e=os.getenv('DJANGO_SUPERUSER_EMAIL','admin@example.com');p=os.getenv('DJANGO_SUPERUSER_PASSWORD','admin123');U.objects.filter(username=u).exists() or U.objects.create_superuser(u,e,p)"

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
