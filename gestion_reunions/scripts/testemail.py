# test_email.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_smtp_connection():
    """Test de connexion SMTP pour ARTCI"""
    
    # Configuration
    smtp_server = "smtp.office365.com"
    port = 587
    sender_email = "qrmeeting@artci.ci"
    password = "Admin/QR25"
    
    try:
        # Création de la connexion
        print("🔗 Connexion au serveur SMTP...")
        server = smtplib.SMTP(smtp_server, port)
        
        # Activation du mode debug
        server.set_debuglevel(1)
        
        # Démarrage TLS
        print("🔒 Démarrage TLS...")
        server.starttls()
        
        # Authentification
        print("🔑 Authentification...")
        server.login(sender_email, password)
        
        print("✅ Connexion SMTP réussie !")
        
        # Test d'envoi d'email
        recipient_email = "nguessan.saintfourier@artci.ci"  # Remplacez par un email de test
        
        message = MIMEMultipart("alternative")
        message["Subject"] = "Test SMTP ARTCI"
        message["From"] = sender_email
        message["To"] = recipient_email
        
        text = """
        Bonjour,
        
        Ceci est un test de configuration SMTP pour QR Meeting.
        
        Si vous recevez ce message, la configuration fonctionne !
        """
        
        part = MIMEText(text, "plain")
        message.attach(part)
        
        # Envoi
        server.sendmail(sender_email, [recipient_email], message.as_string())
        print(f"✅ Email de test envoyé à {recipient_email}")
        
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Erreur d'authentification: {e}")
        print("💡 Vérifiez les identifiants ou activez l'accès pour les applications moins sécurisées")
        return False
        
    except smtplib.SMTPException as e:
        print(f"❌ Erreur SMTP: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return False

if __name__ == "__main__":
    test_smtp_connection()