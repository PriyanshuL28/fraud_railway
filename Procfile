web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn insurance_fraud_detection.wsgi:application --bind 0.0.0.0:$PORT
release: python manage.py migrate