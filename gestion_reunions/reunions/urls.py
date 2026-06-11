# reunions/urls.py - URLs corrigées
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('secretary-dashboard/', views.secretary_dashboard, name='secretary_dashboard'),
    
    # QR Code à la volée (indépendant du stockage media)
    path('reunion/<int:pk>/qr.png', views.qr_code_image_view, name='qr_code_image'),

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

    # Signature numérique
    path('presence/<uuid:uuid>/signature/<uuid:token>/', views.presence_signature, name='presence_signature'),

    # Agenda
    path('reunion/<int:reunion_id>/agenda/ajouter/', views.agenda_point_create, name='agenda_point_create'),
    path('agenda/<int:pk>/modifier/', views.agenda_point_update, name='agenda_point_update'),
    path('agenda/<int:pk>/supprimer/', views.agenda_point_delete, name='agenda_point_delete'),
    path('agenda/<int:pk>/toggle/', views.agenda_point_toggle, name='agenda_point_toggle'),
    path('reunion/<int:reunion_id>/agenda/reorder/', views.agenda_point_reorder, name='agenda_point_reorder'),
    path('agenda/<int:pk>/notes/', views.agenda_point_notes, name='agenda_point_notes'),

    # Invitations
    path('reunion/<int:reunion_id>/inviter/', views.invitation_send, name='invitation_send'),
    path('invitation/<uuid:token>/accepter/', views.invitation_accept, name='invitation_accept'),
    path('invitation/<uuid:token>/decliner/', views.invitation_decline, name='invitation_decline'),

    # Dashboard live stats
    path('api/dashboard/live-stats/', views.api_live_stats, name='api_live_stats'),

    # Statistiques par direction
    path('stats/directions/', views.stats_by_department, name='stats_by_department'),
    path('stats/directions/csv/', views.stats_by_department_csv, name='stats_by_department_csv'),

    # Tableau de bord personnel
    path('mes-diligences/', views.mes_diligences, name='mes_diligences'),

    # Stats diligences par direction
    path('stats/diligences/directions/', views.stats_diligences_directions, name='stats_diligences_directions'),

    # Diligences
    path('reunion/<int:reunion_id>/diligence/ajouter/', views.diligence_create, name='diligence_create'),
    path('diligence/<int:pk>/modifier/', views.diligence_update, name='diligence_update'),
    path('diligence/<int:pk>/supprimer/', views.diligence_delete, name='diligence_delete'),
    path('diligence/<int:pk>/status/', views.diligence_update_status, name='diligence_update_status'),
    path('diligence/<int:pk>/commenter/', views.diligence_add_comment, name='diligence_add_comment'),
    path('reunion/<int:reunion_id>/diligences/export/', views.export_diligences_view, name='export_diligences'),
]