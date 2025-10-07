FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app 
ENV PYTHONPATH /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
 && pip install -r requirements.txt
 
COPY . /app

FROM base AS web

ENV DJANGO_SETTINGS_MODULE=lunastore.settings

EXPOSE 8088