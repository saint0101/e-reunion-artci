#!/bin/bash

# Script d'entrée pour l'application Django ARTCI e-Réunion
set -euo pipefail

echo "🚀 Démarrage de l'application ARTCI e-Réunion..."

# Fonction pour vérifier les variables d'environnement
check_env_vars() {
    echo "🔍 Vérification des variables d'environnement..."
    export DB_HOST="${DB_HOST:-db}"
    export DB_PORT="${DB_PORT:-5432}"
    export DB_USER="${DB_USER:-e_reunion_artci}"
    export DB_NAME="${DB_NAME:-gestion_reunions}"

    echo "📊 Configuration:"
    echo "   - Database: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
    echo "   - User: ${DB_USER}"
    echo "   - Working dir: $(pwd)"
    echo "   - IP publique: 196.216.227.105:80"
}

# Créer les répertoires nécessaires
create_directories() {
    echo "📁 Création des répertoires nécessaires..."
    mkdir -p /app/staticfiles /app/media /app/logs /app/gestion_reunions/static
    echo "✅ Répertoires créés"
}

# Attendre que PostgreSQL soit prêt
wait_for_database() {
    echo "⏳ Attente de la base de données..."
    local max_attempts=30
    local attempt=1
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1 || [ $attempt -gt $max_attempts ]; do
        echo "   Tentative $attempt/$max_attempts - En attente..."
        attempt=$((attempt + 1))
        sleep 2
    done

    if [ $attempt -gt $max_attempts ]; then
        echo "❌ Impossible de se connecter à la base de données après $max_attempts tentatives"
        exit 1
    fi

    echo "✅ Base de données prête!"
}

# Appliquer les migrations Django
apply_migrations() {
    echo "🔄 Application des migrations..."
    if [ ! -f "manage.py" ]; then
        cd /app/gestion_reunions || {
            echo "❌ Impossible de trouver le répertoire gestion_reunions"
            exit 1
        }
    fi
    python manage.py migrate --noinput
    echo "✅ Migrations appliquées"
}

# Créer le superutilisateur
create_superuser() {
    echo "👤 Vérification/Création du superutilisateur..."
    local username="${DJANGO_SUPERUSER_USERNAME:-admin}"
    local email="${DJANGO_SUPERUSER_EMAIL:-admin@artci.ci}"
    local password="${DJANGO_SUPERUSER_PASSWORD:-admin123}"

    python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$username').exists():
    User.objects.create_superuser('$username', '$email', '$password')
    print(f"✅ Superutilisateur créé: $username / $password")
else:
    print("ℹ️ Superutilisateur existe déjà")
EOF
}

# Collecter les fichiers statiques
collect_static() {
    echo "📁 Collecte des fichiers statiques..."
    python manage.py collectstatic --noinput --clear || echo "⚠️ Erreur lors de la collecte des fichiers statiques, mais on continue..."
    echo "✅ Fichiers statiques traités"
}

# Charger les données initiales (optionnel)
load_initial_data() {
    if [ "${LOAD_INITIAL_DATA:-false}" = "true" ]; then
        echo "📊 Chargement des données initiales..."
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
    check_env_vars
    create_directories
    wait_for_database
    apply_migrations
    create_superuser
    collect_static
    load_initial_data

    echo ""
    echo "🎉 Application prête!"
    echo ""
    echo "🌐 Informations de connexion:"
    echo "   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   📱 URL publique: http://196.216.227.105:80"
    echo "   🏠 URL locale:   http://172.16.0.153:8000"
    echo "   👤 Admin:        ${DJANGO_SUPERUSER_USERNAME:-admin}"
    echo "   🔑 Password:     ${DJANGO_SUPERUSER_PASSWORD:-admin123}"
    echo "   🔧 Admin panel:  http://196.216.227.105:80/admin"
    echo "   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    echo "🚀 Démarrage de Gunicorn sur 0.0.0.0:8000..."
    
    # ✅ CORRECTION FINALE: Gunicorn avec logs vers stdout/stderr
    exec gunicorn gestion_reunions.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --worker-class gthread \
        --worker-connections 1000 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --timeout 120 \
        --keep-alive 5 \
        --log-level info \
        --access-logfile=- \
        --error-logfile=- \
        --capture-output
}

# Gestion des signaux
trap "echo '🛑 Arrêt de l'application...'; exit 0" SIGTERM SIGINT

# Lancer l'application
main "$@"