FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/instance/uploads

EXPOSE 8000

CMD ["sh", "-c", "python -m flask --app app db upgrade && exec gunicorn -c gunicorn.conf.py wsgi:app"]
