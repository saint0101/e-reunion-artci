# reunions/urls.py - URLs corrigées
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('secretary-dashboard/', views.secretary_dashboard, name='secretary_dashboard'),
    
    # Reunions
    path('reunions/', views.ReunionListView.as_view(), name='reunion_list'),
    path('reunion/<int:pk>/', views.ReunionDetailView.as_view(), name='reunion_detail'),
    path('reunion/create/', views.reunion_create, name='reunion_create'),
    path('reunion/<int:pk>/edit/', views.reunion_update, name='reunion_update'),
    path('reunion/<int:pk>/delete/', views.reunion_delete, name='reunion_delete'),
    
    # Presence via QR Code - FLUX SIMPLIFIÉ
    path('presence/<uuid:uuid>/', views.presence_qr_redirect, name='presence_qr_redirect'),
    path('presence/<uuid:uuid>/form/', views.presence_form, name='presence_form'),
    path('presence/<uuid:uuid>/external/', views.presence_external_form, name='presence_external_form'),
    path('presence/<uuid:uuid>/artci-fallback/', views.presence_artci_fallback_form, name='presence_artci_fallback_form'),
    path('cancel/<uuid:token>/', views.presence_cancel, name='presence_cancel'),
    path('presence/status/<uuid:token>/', views.presence_status, name='presence_status'),
    
    # Comptes-Rendus
    path('reunion/<int:reunion_id>/compte-rendu/create/', views.compte_rendu_create, name='compte_rendu_create'),
    path('compte-rendu/<int:pk>/update/', views.compte_rendu_update, name='compte_rendu_update'),
    path('compte-rendu/<int:pk>/delete/', views.compte_rendu_delete, name='compte_rendu_delete'),
    
    # Export
    path('reunion/<int:reunion_id>/export-presence/', views.export_presence_list, name='export_presence_list'),
    path('export/data/', views.export_data, name='export_data'),
    
    # Ajax endpoints
    path('api/reunion/<int:pk>/status/', views.update_reunion_status, name='update_reunion_status'),
    path('api/send-compte-rendu/<int:pk>/', views.send_compte_rendu, name='send_compte_rendu'),

    path('cancel/<str:cancel_token>/', views.presence_cancel_by_token, name='presence_cancel'),
    path('debug/secretary-notification/', views.debug_secretary_notification, name='debug_secretary_notification'),

     # URLs d'annulation
    path('cancel/<str:token>/', views.presence_cancel, name='presence_cancel'),
    
    # URL de debug (à supprimer en production)
    path('debug/secretary-notification/', views.debug_secretary_notification, name='debug_secretary_notification'),


]