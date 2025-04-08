FROM python:3.10-slim-buster

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

COPY . /app

ENTRYPOINT ["python", "app.py", "--certfile", "/certs/tls.crt", "--keyfile", "/certs/tls.key", "--port", "443"]