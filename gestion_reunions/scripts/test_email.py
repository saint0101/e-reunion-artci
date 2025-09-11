import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_reunions.settings')
django.setup()

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from reunions.models import Reunion, PresenceRequest
from django.utils import timezone

def test_email_configuration():
    """Teste la configuration email"""
    print("🔧 Test de la configuration email")
    print("=" * 50)
    
    print(f"📤 Backend email: {settings.EMAIL_BACKEND}")
    print(f"📧 Email par défaut: {settings.DEFAULT_FROM_EMAIL}")
    print(f"🌐 URL du site: {getattr(settings, 'SITE_URL', 'Non définie')}")
    
    if hasattr(settings, 'EMAIL_HOST'):
        print(f"🏠 Serveur SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        print(f"🔐 TLS activé: {settings.EMAIL_USE_TLS}")
        print(f"👤 Utilisateur: {settings.EMAIL_HOST_USER}")
    
    print()

def test_simple_email():
    """Teste l'envoi d'un email simple"""
    print("📧 Test d'envoi d'email simple...")
    
    try:
        result = send_mail(
            subject='Test - QR Meeting',
            message='Ceci est un test d\'envoi d\'email depuis l\'application QR Meeting.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['fouriersaint@gmail.com'],
            fail_silently=False,
        )
        
        print(f"✅ Email simple envoyé (result: {result})")
        return True
        
    except Exception as e:
        print(f"❌ Erreur envoi email simple: {e}")
        return False

def test_html_email():
    """Teste l'envoi d'un email HTML"""
    print("🎨 Test d'envoi d'email HTML...")
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Test Email</title>
        <style>
            body { font-family: Arial, sans-serif; color: #333; }
            .header { background: #FF6B35; color: white; padding: 20px; text-align: center; }
            .content { padding: 20px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🧪 Test Email HTML</h1>
        </div>
        <div class="content">
            <p>Ceci est un test d'email HTML depuis l'application <strong>QR Meeting</strong>.</p>
            <p>Si vous recevez cet email, la configuration fonctionne correctement ! ✅</p>
        </div>
    </body>
    </html>
    """
    
    text_content = """
    Test Email - QR Meeting
    
    Ceci est un test d'email depuis l'application QR Meetin.
    Si vous recevez cet email, la configuration fonctionne correctement !
    """
    
    try:
        email = EmailMultiAlternatives(
            subject='Test HTML - QR Meeting',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=['fouriersaint@gmail.com']
        )
        
        email.attach_alternative(html_content, "text/html")
        result = email.send()
        
        print(f"✅ Email HTML envoyé (result: {result})")
        return True
        
    except Exception as e:
        print(f"❌ Erreur envoi email HTML: {e}")
        return False

def test_validation_email():
    """Teste l'envoi d'un email de validation avec de vraies données"""
    print("🎯 Test d'email de validation avec données réelles...")
    
    # Trouver une réunion de test
    reunion = Reunion.objects.first()
    if not reunion:
        print("⚠️ Aucune réunion trouvée. Créez d'abord une réunion de test.")
        return False
    
    # Créer une demande de présence de test
    presence_request, created = PresenceRequest.objects.get_or_create(
        reunion=reunion,
        email='pythondomotique@gmail.com',
        defaults={
            'consent_given': True,
            'status': 'pending'
        }
    )
    
    # Tester l'envoi
    from reunions.views import send_validation_email
    
    try:
        result = send_validation_email(presence_request)
        if result:
            print(f"✅ Email de validation envoyé avec succès")
            print(f"   Réunion: {reunion.titre}")
            print(f"   Email: {presence_request.email}")
            print(f"   Token: {presence_request.validation_token}")
            print(f"   URL: http://localhost:8000/validation/{presence_request.validation_token}/")
        else:
            print("❌ Échec de l'envoi de l'email de validation")
        
        return result
        
    except Exception as e:
        print(f"❌ Erreur lors du test de validation: {e}")
        return False

def configure_gmail():
    """Guide pour configurer Gmail"""
    print("📮 Configuration Gmail")
    print("=" * 30)
    print()
    print("Pour utiliser Gmail, suivez ces étapes :")
    print()
    print("1. 🔐 Activez la validation en 2 étapes sur votre compte Google")
    print("2. 🔑 Générez un mot de passe d'application :")
    print("   - Allez sur https://myaccount.google.com/security")
    print("   - Cliquez sur 'Mots de passe d'application'")
    print("   - Générez un nouveau mot de passe pour 'Autre (nom personnalisé)'")
    print("   - Nommez-le 'QR Meeting' et copiez le mot de passe généré")
    print()
    print("3. ⚙️ Mettez à jour votre fichier .env :")
    print()
    print("USE_REAL_EMAIL=True")
    print("EMAIL_HOST=smtp.gmail.com")
    print("EMAIL_PORT=587")
    print("EMAIL_USE_TLS=True")
    print("EMAIL_HOST_USER=votre.email@gmail.com")
    print("EMAIL_HOST_PASSWORD=votre_mot_de_passe_application")
    print("DEFAULT_FROM_EMAIL=votre.email@gmail.com")
    print()
    print("4. 🔄 Redémarrez le serveur Django")
    print()

def main():
    """Fonction principale"""
    print("🧪 TEST DE CONFIGURATION EMAIL")
    print("=" * 50)
    print()
    
    # Tester la configuration
    test_email_configuration()
    
    print("📋 TESTS DISPONIBLES :")
    print("1. Test email simple")
    print("2. Test email HTML") 
    print("3. Test email de validation réel")
    print("4. Guide configuration Gmail")
    print("5. Tous les tests")
    print("0. Quitter")
    print()
    
    try:
        choice = input("Choisissez un test (0-5): ").strip()
        print()
        
        if choice == '1':
            test_simple_email()
        elif choice == '2':
            test_html_email()
        elif choice == '3':
            test_validation_email()
        elif choice == '4':
            configure_gmail()
        elif choice == '5':
            print("🚀 Exécution de tous les tests...")
            print()
            test_simple_email()
            print()
            test_html_email()
            print()
            test_validation_email()
        elif choice == '0':
            print("👋 Au revoir !")
            return
        else:
            print("❌ Choix invalide")
            
    except KeyboardInterrupt:
        print("\n👋 Test interrompu")
    except Exception as e:
        print(f"❌ Erreur: {e}")
    
    print()
    print("✨ Test terminé")

if __name__ == '__main__':
    main()