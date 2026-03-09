web: gunicorn bookmyshow.wsgi --log-file -
worker: celery -A bookmyshow worker --loglevel=info --concurrency=1