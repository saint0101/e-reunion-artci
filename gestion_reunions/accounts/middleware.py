from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Redirige les utilisateurs connectés dont must_change_password est True
    vers la page de changement de mot de passe obligatoire.
    """

    EXEMPT_URLS = [
        'password_change_required',
        'logout',
        'login',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'must_change_password', False)
        ):
            change_url = reverse('password_change_required')
            logout_url = reverse('logout')
            # Laisser passer les URLs exemptées et les URLs statiques/media
            if (
                request.path != change_url
                and request.path != logout_url
                and not request.path.startswith('/static/')
                and not request.path.startswith('/media/')
                and not request.path.startswith('/admin/')
            ):
                return redirect(change_url)

        return self.get_response(request)
