FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

EXPOSE 1004

CMD ["gunicorn", "--bind", "0.0.0.0:1004", "app:app"]
