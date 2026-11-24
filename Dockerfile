FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY hypontech_mqtt.py .

CMD ["python", "/app/hypontech_mqtt.py"]