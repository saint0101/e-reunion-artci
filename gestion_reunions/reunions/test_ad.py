import os, sys
import django
from service_ad import ActiveDirectoryService

# Ajoute le chemin racine du projet au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_reunions.settings')

django.setup()

# Création du service AD
ad_service = ActiveDirectoryService()

# Test de connexion
success, message = ad_service.test_connection()
print(f"Test connexion AD: {message}")

# Test récupération d'un utilisateur
email_test = "dja.rodrigue@artci.ci"
user_info = ad_service.get_user_info(email_test)

if user_info:
    print("\n✅ Utilisateur trouvé dans AD:")
    print(f"Nom complet : {user_info['nom_complet']}")
    print(f"Prénom     : {user_info['prenom']}")
    print(f"Nom        : {user_info['nom']}")
    print(f"Email      : {user_info['email']}")
    print(f"Fonction   : {user_info['fonction']}")
    print(f"Organisation: {user_info['organisation']}")
    print(f"Téléphone  : {user_info['contact']}")
    print(f"Département: {user_info['departement']}")
    print(f"Bureau     : {user_info['bureau']}")
    print(f"Compte     : {user_info['compte']}")
else:
    print(f"\n❌ Aucun utilisateur trouvé pour {email_test}")