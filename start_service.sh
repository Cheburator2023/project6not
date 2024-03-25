#!/bin/bash
celery -A app.mail.celery worker -l DEBUG -c4 &
gunicorn --workers 5 --bind 0.0.0.0:5025 wsgi:app
