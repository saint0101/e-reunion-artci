import smtplib
import ssl

port = 587  # TLS
smtp_server = "smtp.gmail.com"
sender_email = "warrensaint1@gmail.com"
receiver_email = "fouriersaint@gmail.com"
password = "wcum uphk tocm cter"

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