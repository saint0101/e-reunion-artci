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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.template.loader import render_to_string

def manifest_json(request):
    content = render_to_string('pwa/manifest.json', {'request': request})
    return HttpResponse(content, content_type='application/manifest+json')

def service_worker_js(request):
    content = render_to_string('pwa/sw.js', {'request': request})
    return HttpResponse(content, content_type='application/javascript')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manifest.json', manifest_json, name='manifest_json'),
    path('sw.js', service_worker_js, name='service_worker'),
    path('', include('reunions.urls')),
    path('accounts/', include('accounts.urls')),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

import os
try:
    from decouple import config as _cfg
    _serve_media = _cfg('SERVE_MEDIA_FILES', default=False, cast=bool)
except Exception:
    _serve_media = os.environ.get('SERVE_MEDIA_FILES', '').lower() in ('true', '1', 'yes')

if settings.DEBUG or _serve_media:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    print("SERVE MEDIA:", settings.DEBUG, _serve_media)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

print("SERVE MEDIA 1:", settings.DEBUG, _serve_media)