FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

EXPOSE 1004

# Un seul worker : les fichiers JSON et le blocage des PIN ne sont pas partagés entre processus.
# Timeout > 3 appels IA successifs de 20 s.
CMD ["gunicorn", "--workers", "1", "--timeout", "90", "--bind", "0.0.0.0:1004", "app:app"]
