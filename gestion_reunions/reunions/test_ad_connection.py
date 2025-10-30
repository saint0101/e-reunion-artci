import os, sys
import django

from service_ad import ActiveDirectoryService

# Ajoute le chemin racine du projet au sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_reunions.settings')

django.setup()

# Test de connexion
ad = ActiveDirectoryService()
success, message = ad.test_connection()
print(f"Test connexion: {message}")

# Test de récupération d'un utilisateur
email_test = "djekou.abraham@artci.ci"  # Remplacez par un vrai email
user_info = ad.get_user_info(email_test)

if user_info:
    print(f"\n✓ Utilisateur trouvé:")
    print(f"  Nom: {user_info['nom']}")
    print(f"  Prénom: {user_info['prenom']}")
    print(f"  Email: {user_info['email']}")
    print(f"  Département: {user_info['departement']}")
    print(f"  Fonction: {user_info['poste']}")
    print(f"  Téléphone: {user_info['telephone']}")
else:
    print(f"\n✗ Utilisateur non trouvé pour {email_test}")