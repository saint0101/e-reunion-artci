from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """
    Redirige les utilisateurs connectés dont must_change_password est True
    vers la page de changement de mot de passe obligatoire.
    """

    EXEMPT_URL_NAMES = [
        'password_change_required',
        'logout',
        'login',
        'otp_verify',
        'otp_resend',
        'password_reset',
        'password_reset_done',
        'password_reset_confirm',
        'password_reset_complete',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        # Construire la liste des chemins exemptés une seule fois
        self._exempt_paths = None

    def _get_exempt_paths(self):
        if self._exempt_paths is None:
            paths = set()
            for name in self.EXEMPT_URL_NAMES:
                try:
                    paths.add(reverse(name))
                except Exception:
                    pass
            self._exempt_paths = paths
        return self._exempt_paths

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and getattr(request.user, 'must_change_password', False)
        ):
            change_url = reverse('password_change_required')
            admin_prefix = '/' + getattr(settings, 'ADMIN_URL', 'admin/')

            if (
                request.path not in self._get_exempt_paths()
                and not request.path.startswith('/static/')
                and not request.path.startswith('/media/')
                and not request.path.startswith(admin_prefix)
            ):
                return redirect(change_url)

        return self.get_response(request)
