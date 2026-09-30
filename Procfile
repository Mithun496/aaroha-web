release: python -m flask --app app db upgrade
web: gunicorn -c gunicorn.conf.py wsgi:app
