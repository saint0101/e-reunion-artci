#!/bin/bash

# Script d'entrée pour l'application Django

set -e

echo "🚀 Démarrage de l'application ARTCI..."

# Attendre que PostgreSQL soit prêt
echo "⏳ Attente de la base de données..."
while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; do
    echo "Base de données non prête, attente..."
    sleep 2
done

echo "✅ Base de données prête!"

# Appliquer les migrations
echo "🔄 Application des migrations..."
python manage.py migrate --noinput

# Créer un superutilisateur si il n'existe pas
echo "👤 Création du superutilisateur..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@artci.ci', 'admin123')
    print("Superutilisateur créé: admin / admin123")
else:
    print("Superutilisateur existe déjà")
EOF

# Collecter les fichiers statiques
echo "📁 Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

# Charger les données initiales (optionnel)
# echo "📊 Chargement des données initiales..."
# python manage.py loaddata fixtures/initial_data.json

echo "🎉 Application prête!"

# Démarrer Gunicorn
exec gunicorn plaintes_conso.wsgi:application \
    --bind 0.0.0.0:80 \
    --workers 3 \
    --worker-class gthread \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --keep-alive 5 \
    --log-level info \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log