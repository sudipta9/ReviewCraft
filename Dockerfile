FROM python:latest

LABEL maintainer="Grega Vrbančič <grega.vrbancic@gmail.com"

ENV DOCKER=true

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

EXPOSE 8000