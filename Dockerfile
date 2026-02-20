FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    libz-dev \
    libjpeg-dev \
    libfreetype6-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app 
ENV PYTHONPATH /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
 && pip install -r requirements.txt

RUN python manage.py collectstatic --noinput || true
 
COPY . /app

FROM base AS web

ENV DJANGO_SETTINGS_MODULE=lunastore.settings

EXPOSE 9088

CMD ["gunicorn", "lunastore.wsgi:application", "--bind", "0.0.0.0:9088", "--workers", "3"]