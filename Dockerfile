# Dockerfile pour l'application ARTCI e-Réunion
FROM python:3.12-slim

# Métadonnées
LABEL maintainer="ARTCI <artci@artci.ci>"
LABEL description="Application de gestion des réunions ARTCI (QR Meeting)"
LABEL version="1.0"

# Variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=gestion_reunions.settings

# Installer les dépendances système en tant que root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        gettext \
        curl \
        nano \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root avec UID/GID spécifiques
RUN groupadd -r appuser -g 1000 && useradd -u 1000 -r -g appuser appuser

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de requirements et installer les dépendances
COPY requirements.txt /app/
COPY requirements-prod.txt /app/
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copier le code de l'application
COPY . /app/

# Créer les répertoires nécessaires avec les bonnes permissions
RUN mkdir -p /app/staticfiles \
    && mkdir -p /app/media \
    && mkdir -p /app/logs \
    && mkdir -p /app/gestion_reunions/static \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Copier et configurer le script d'entrée
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Créer le dossier logs et donner les droits
RUN mkdir -p /app/gestion_reunions/reunions/logs \
    && chown -R appuser:appuser /app/gestion_reunions/reunions/logs


# Passer à l'utilisateur non-root
USER appuser

# Exposer le port 8080
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Point d'entrée - UTILISER LE SCRIPT
ENTRYPOINT ["docker-entrypoint.sh"]

# Pas de CMD - le script d'entrée lance gunicorn