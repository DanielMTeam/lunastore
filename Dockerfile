FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libz-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install -r requirements.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=lunastore.settings

EXPOSE 8000

CMD ["gunicorn", "lunastore.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]