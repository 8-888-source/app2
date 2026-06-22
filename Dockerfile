FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/instance /app/static/videos

EXPOSE 5000

CMD ["sh", "-c", "gunicorn wsgi:application --bind 0.0.0.0:${PORT:-5000}"]
