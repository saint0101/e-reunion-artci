from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import CustomUser, Reunion, PresenceRequest, CompteRendu
from .models import CancellationLog
from import_export.admin import ImportExportModelAdmin


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

class PresenceRequestInline(admin.TabularInline):
    model = PresenceRequest
    extra = 0
    readonly_fields = ('email', 'validation_token', 'status', 'created_at', 'confirmed_at')
    fields = ('email', 'nom', 'prenom', 'organisation', 'status', 'confirmed_at')

class CompteRenduInline(admin.TabularInline):
    model = CompteRendu
    extra = 0
    readonly_fields = ('version', 'created_at', 'cree_par')
    fields = ('titre', 'fichier', 'version', 'cree_par', 'envoye_automatiquement')

@admin.register(Reunion)
class ReunionAdmin(ImportExportModelAdmin):
    list_display = ('titre', 'date_debut', 'lieu', 'organisateur', 'secretaire', 'status', 'participants_count', 'qr_code_link')
    list_filter = ('status', 'date_debut', 'organisateur', 'secretaire')
    search_fields = ('titre', 'description', 'lieu')
    date_hierarchy = 'date_debut'
    ordering = ('-date_debut',)
    
    inlines = [PresenceRequestInline, CompteRenduInline]
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('titre', 'description', 'lieu', 'status')
        }),
        ('Planning', {
            'fields': ('date_debut', 'date_fin')
        }),
        ('Responsables', {
            'fields': ('organisateur', 'secretaire')
        }),
        ('QR Code', {
            'fields': ('qr_code_uuid', 'qr_code_image'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('qr_code_uuid', 'created_at', 'updated_at')
    
    def participants_count(self, obj):
        count = obj.presence_requests.filter(status='confirmed').count()
        return format_html(
            '<span style="color: {};">{}</span>',
            '#28a745' if count > 0 else '#dc3545',
            count
        )
    participants_count.short_description = 'Participants'
    
    def qr_code_link(self, obj):
        if obj.qr_code_image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" width="50" height="50" /></a>',
                obj.qr_code_image.url,
                obj.qr_code_image.url
            )
        return "Pas de QR Code"
    qr_code_link.short_description = 'QR Code'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organisateur', 'secretaire').prefetch_related('presence_requests')

@admin.register(PresenceRequest)
class PresenceRequestAdmin(ImportExportModelAdmin):
    list_display = ('email', 'reunion', 'nom', 'prenom', 'status', 'created_at', 'confirmed_at')
    list_filter = ('status', 'created_at', 'reunion__date_debut')
    search_fields = ('email', 'nom', 'prenom', 'reunion__titre')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    readonly_fields = ('validation_token', 'created_at', 'confirmed_at')
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('reunion', 'email', 'status', 'consent_given')
        }),
        ('Informations personnelles', {
            'fields': ('nom', 'prenom', 'organisation')
        }),
        ('Validation', {
            'fields': ('validation_token', 'created_at', 'confirmed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('reunion')

@admin.register(CompteRendu)
class CompteRenduAdmin(ImportExportModelAdmin):
    list_display = ('titre', 'reunion', 'version', 'cree_par', 'created_at', 'envoye_automatiquement', 'download_link')
    list_filter = ('envoye_automatiquement', 'created_at', 'reunion__date_debut')
    search_fields = ('titre', 'reunion__titre')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    readonly_fields = ('version', 'created_at')
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('reunion', 'titre', 'fichier')
        }),
        ('Métadonnées', {
            'fields': ('version', 'cree_par', 'envoye_automatiquement', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def download_link(self, obj):
        if obj.fichier:
            return format_html(
                '<a href="{}" target="_blank">Télécharger</a>',
                reverse('compte_rendu_download', args=[obj.pk])
            )
        return "Pas de fichier"
    download_link.short_description = 'Fichier'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('reunion', 'cree_par')


@admin.register(CancellationLog)
class CancellationLogAdmin(ImportExportModelAdmin):
    list_display = ('presence_request', 'cancelled_at', 'cancelled_by_ip', 'secretary_notified')
    list_filter = ('secretary_notified', 'cancelled_at')
    search_fields = ('presence_request__email', 'secretary_email', 'cancellation_reason')
    date_hierarchy = 'cancelled_at'
    ordering = ('-cancelled_at',)


# Configuration de l'admin
admin.site.site_header = "Administration - Gestion des Réunions (QR Meeting)"
admin.site.site_title = "QR Meeting Admin"
admin.site.index_title = "Panneau d'administration"