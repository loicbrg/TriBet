FROM python:3.11-slim

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY . .

# Dossier pour la base de données SQLite (monté en volume)
RUN mkdir -p /data && chmod 755 /data

EXPOSE 8000

# Initialiser la BDD si elle n'existe pas, puis lancer gunicorn
CMD ["sh", "-c", \
     "[ ! -f /data/tribet.db ] && TRIBET_DB=/data/tribet.db python init_db.py; \
      TRIBET_DB=/data/tribet.db gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 60 app:app"]
