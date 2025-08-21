#!/bin/bash

# Script d'entrée pour l'application Django ARTCI e-Réunion

set -e

echo "🚀 Démarrage de l'application ARTCI e-Réunion..."

# Fonction pour vérifier les variables d'environnement
check_env_vars() {
    echo "🔍 Vérification des variables d'environnement..."
    
    # Variables par défaut si non définies
    export DB_HOST=${DB_HOST:-db}
    export DB_PORT=${DB_PORT:-5432}
    export DB_USER=${DB_USER:-e_reunion_artci}
    export DB_NAME=${DB_NAME:-gestion_reunions}
    
    echo "📊 Configuration:"
    echo "   - Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
    echo "   - User: ${DB_USER}"
    echo "   - Working dir: $(pwd)"
}

# Créer les répertoires nécessaires
create_directories() {
    echo "📁 Création des répertoires nécessaires..."
    
    # Créer les répertoires s'ils n'existent pas
    mkdir -p /app/staticfiles
    mkdir -p /app/media
    mkdir -p /app/logs
    mkdir -p /app/gestion_reunions/static
    
    # Créer les fichiers de log vides pour éviter les erreurs de permissions
    touch /app/logs/access.log 2>/dev/null || echo "⚠️ Impossible de créer access.log"
    touch /app/logs/error.log 2>/dev/null || echo "⚠️ Impossible de créer error.log"
    touch /app/logs/django.log 2>/dev/null || echo "⚠️ Impossible de créer django.log"
    
    echo "✅ Répertoires créés"
}

# Attendre que PostgreSQL soit prêt
wait_for_database() {
    echo "⏳ Attente de la base de données..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER > /dev/null 2>&1; then
            echo "✅ Base de données prête!"
            return 0
        fi
        
        echo "   Tentative $attempt/$max_attempts - En attente..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "❌ Impossible de se connecter à la base de données après $max_attempts tentatives"
    exit 1
}

# Appliquer les migrations Django
apply_migrations() {
    echo "🔄 Application des migrations..."
    
    # Vérifier si on est dans le bon répertoire
    if [ ! -f "manage.py" ]; then
        echo "📂 Navigation vers le répertoire Django..."
        cd /app/gestion_reunions || {
            echo "❌ Impossible de trouver le répertoire gestion_reunions"
            exit 1
        }
    fi
    
    # Appliquer les migrations
    python manage.py migrate --noinput
    echo "✅ Migrations appliquées"
}

# Créer le superutilisateur
create_superuser() {
    echo "👤 Vérification/Création du superutilisateur..."
    
    # Variables d'environnement avec valeurs par défaut
    local username=${DJANGO_SUPERUSER_USERNAME:-admin}
    local email=${DJANGO_SUPERUSER_EMAIL:-admin@artci.ci}
    local password=${DJANGO_SUPERUSER_PASSWORD:-admin123}
    
    python manage.py shell << EOF
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = '$username'
email = '$email'
password = '$password'

if not User.objects.filter(username=username).exists():
    try:
        User.objects.create_superuser(username, email, password)
        print(f"✅ Superutilisateur créé: {username} / {password}")
    except Exception as e:
        print(f"❌ Erreur lors de la création du superutilisateur: {e}")
else:
    print("ℹ️ Superutilisateur existe déjà")
EOF
}

# Collecter les fichiers statiques
collect_static() {
    echo "📁 Collecte des fichiers statiques..."
    
    # Collecter les fichiers statiques en ignorant les erreurs
    python manage.py collectstatic --noinput --clear || {
        echo "⚠️ Erreur lors de la collecte des fichiers statiques, mais on continue..."
    }
    
    echo "✅ Fichiers statiques traités"
}

# Charger les données initiales (optionnel)
load_initial_data() {
    if [ "${LOAD_INITIAL_DATA:-false}" = "true" ]; then
        echo "📊 Chargement des données initiales..."
        
        # Vérifier si le fichier de fixtures existe
        if [ -f "fixtures/initial_data.json" ]; then
            python manage.py loaddata fixtures/initial_data.json
            echo "✅ Données initiales chargées"
        else
            echo "⚠️ Fichier de données initiales non trouvé"
        fi
    fi
}

# Fonction principale
main() {
    # Vérifications préliminaires
    check_env_vars
    create_directories
    
    # Attendre la base de données
    wait_for_database
    
    # Préparation Django
    apply_migrations
    create_superuser
    collect_static
    load_initial_data
    
    echo "🎉 Application prête!"
    echo ""
    echo "🌐 Informations de connexion:"
    echo "   - URL: http://196.216.227.105"
    echo "   - Admin: ${DJANGO_SUPERUSER_USERNAME:-admin}"
    echo "   - Password: ${DJANGO_SUPERUSER_PASSWORD:-admin123}"
    echo ""
    
    # Démarrer Gunicorn avec la bonne configuration
    echo "🚀 Démarrage de Gunicorn..."
    
    # Configuration des logs pour éviter les erreurs de permissions
    local access_log="/dev/stdout"
    local error_log="/dev/stderr"
    
    # Essayer d'utiliser les fichiers de log s'ils sont accessibles en écriture
    if [ -w "/app/logs" ]; then
        access_log="/app/logs/access.log"
        error_log="/app/logs/error.log"
    fi
    
    exec gunicorn gestion_reunions.wsgi:application \
        --bind 0.0.0.0:8080 \
        --workers 3 \
        --worker-class gthread \
        --worker-connections 1000 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --timeout 120 \
        --keep-alive 5 \
        --log-level info \
        --access-logfile "$access_log" \
        --error-logfile "$error_log" \
        --capture-output \
        --enable-stdio-inheritance
}

# Gestion des signaux pour un arrêt propre
cleanup() {
    echo ""
    echo "🛑 Arrêt de l'application..."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Exécuter la fonction principale
main "$@"