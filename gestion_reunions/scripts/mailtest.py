import os
import smtplib
import ssl

port = 587  # TLS
smtp_server = "smtp.office365.com"
sender_email = "qrmeeting@artci.ci"
receiver_email = "nguessan.saintfourier@artci.ci"
password = os.environ["EMAIL_HOST_PASSWORD"]

message = """\
Subject: Test SMTP brut

Ceci est un test brut via SMTP sans Django."""

try:
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)
    print("✅ Email envoyé avec succès via SMTP brut")
except Exception as e:
    print(f"❌ Échec SMTP brut : {e}")