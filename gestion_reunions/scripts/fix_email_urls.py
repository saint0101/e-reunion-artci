import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_reunions.settings')
django.setup()

from reunions.models import PresenceRequest
from django.conf import settings

def fix_email_urls():
    """Corrige les URLs des demandes de présence en attente"""
    print("🔧 Correction des URLs d'email...")
    
    # URL de base correcte
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    # Trouver toutes les demandes en attente
    pending_requests = PresenceRequest.objects.filter(status='pending')
    
    print(f"📋 {pending_requests.count()} demande(s) en attente trouvée(s)")
    
    for request in pending_requests:
        correct_url = f"{site_url}/validation/{request.validation_token}/"
        print(f"✅ {request.email} -> {correct_url}")
    
    print()
    print("💡 Pour renvoyer les emails avec les bonnes URLs :")
    print("   1. Supprimez les demandes en attente avec de mauvaises URLs")
    print("   2. Demandez aux utilisateurs de rescanner le QR code")
    print("   3. Ou utilisez le script de renvoi d'emails")

def resend_validation_emails():
    """Renvoie les emails de validation pour toutes les demandes en attente"""
    print("📧 Renvoi des emails de validation...")
    
    from reunions.views import send_validation_email
    
    pending_requests = PresenceRequest.objects.filter(status='pending')
    
    if not pending_requests.exists():
        print("ℹ️ Aucune demande en attente trouvée")
        return
    
    success_count = 0
    error_count = 0
    
    for request in pending_requests:
        try:
            result = send_validation_email(request)
            if result:
                print(f"✅ Email renvoyé à: {request.email}")
                success_count += 1
            else:
                print(f"❌ Échec envoi à: {request.email}")
                error_count += 1
        except Exception as e:
            print(f"❌ Erreur pour {request.email}: {e}")
            error_count += 1
    
    print()
    print(f"📊 Résultats: {success_count} succès, {error_count} erreurs")

if __name__ == '__main__':
    print("🔧 CORRECTION DES EMAILS")
    print("=" * 30)
    print()
    print("1. Vérifier les URLs")
    print("2. Renvoyer les emails")
    print("0. Quitter")
    print()
    
    choice = input("Choisissez une option (0-2): ").strip()
    print()
    
    if choice == '1':
        fix_email_urls()
    elif choice == '2':
        resend_validation_emails()
    elif choice == '0':
        print("👋 Au revoir !")
    else:
        print("❌ Choix invalide")