# Dockerfile pour l'application ARTCI e-Réunion
FROM python:3.12-slim


# Métadonnées
LABEL maintainer="ARTCI <artci@artci.ci>"
LABEL description="Application de gestion des réunions ARTCI"
LABEL version="1.0"

# Variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=gestion_reunions.settings

# Créer un utilisateur non-root
RUN adduser --disabled-password --gecos '' appuser

# Installer les dépendances système
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de requirements
COPY requirements.txt /app/
COPY requirements-prod.txt /app/

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copier le code de l'application
COPY . /app/

# Créer les répertoires nécessaires
RUN mkdir -p /app/staticfiles  && chmod -R 777 /app/staticfiles
RUN mkdir -p /app/media && chmod -R 777 /app/media
RUN mkdir -p /app/logs && chmod -R 777 /app/logs
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs
# Changer la propriété des fichiers
RUN chown -R appuser:appuser /app

# Passer à l'utilisateur non-root
USER appuser

# Collecter les fichiers statiques
WORKDIR /app/gestion_reunions
RUN python manage.py collectstatic --noinput
WORKDIR /app
# RUN python manage.py collectstatic --noinput

# Exposer le port
EXPOSE 80

# Script d'entrée
COPY docker-entrypoint.sh /app/
USER root
RUN chmod +x /app/docker-entrypoint.sh
USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "3", "gestion_reunions.wsgi:application"]
