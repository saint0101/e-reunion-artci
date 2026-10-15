"""
Page d'échec CSRF lisible (settings.CSRF_FAILURE_VIEW).

Le contrôle CSRF reste actif : cette vue remplace seulement la page 403 brute
de Django. Cas fréquent : participant sur iPhone dont le navigateur n'a pas
renvoyé le cookie CSRF en validant le formulaire de présence.
"""
import re

from django.shortcuts import render

PRESENCE_PATH = re.compile(r'^/presence/([0-9a-fA-F-]{36})/')


def csrf_failure(request, reason=""):
    match = PRESENCE_PATH.match(request.path)
    if match:
        # Repartir de la page d'entrée du QR code : elle repose un cookie CSRF neuf
        retry_url = f"/presence/{match.group(1)}/"
    else:
        retry_url = request.get_full_path()

    return render(request, 'reunions/csrf_failure.html', {
        'retry_url': retry_url,
        'is_presence': bool(match),
    }, status=403)
