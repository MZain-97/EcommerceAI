#!/bin/bash

# Exit on error
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

echo "Waiting for Redis..."
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 0.1
done
echo "Redis started"

# Only run migrations and setup for non-celery commands
if [[ "$1" != "celery" ]]; then
  # Run migrations (continue on error for development)
  echo "Running database migrations..."
  python manage.py migrate --noinput || echo "Warning: Some migrations failed, continuing..."

  # Collect static files
  echo "Collecting static files..."
  python manage.py collectstatic --noinput || echo "Warning: collectstatic failed, continuing..."

  # Create superuser if it doesn't exist (skip on error for development)
  echo "Checking for superuser..."
  python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123');
    print('Superuser created');
else:
    print('Superuser already exists');
" || echo "Warning: Could not create superuser, continuing..."
else
  echo "Skipping migrations/collectstatic for celery worker..."
fi

# Execute the main container command
exec "$@"
