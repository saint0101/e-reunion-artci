"""
URL configuration for gestion_reunions project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

# gestion_reunions/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

# L'URL de l'admin est définie dans settings.ADMIN_URL (variable d'environnement)
# Par défaut : artci-qrmeeting-admin-2025/
urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('', include('reunions.urls')),
    path('accounts/', include('accounts.urls')),
]

# Seuls les QR codes sont publics. Les comptes-rendus passent par la vue
# compte_rendu_download qui contrôle les droits (P7.2 / R1).
urlpatterns += [
    re_path(r'^media/(?P<path>qr_codes/.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)