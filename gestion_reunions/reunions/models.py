# reunions/models.py (version complète et finalisée)
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.urls import reverse
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image
import os

class CustomUser(AbstractUser):
    ROLES = (
        ('admin', 'Administrateur'),
        ('secretary', 'Secrétaire de réunion'),
        ('participant', 'Participant'),
    )
    role = models.CharField(max_length=20, choices=ROLES, default='participant')
    phone = models.CharField(max_length=15, blank=True)
    
    # Résoudre les conflits de reverse accessor
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="customuser_set",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="customuser_set",
        related_query_name="customuser",
    )
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})" if self.first_name else self.username

class Reunion(models.Model):
    STATUS_CHOICES = (
        ('planned', 'Planifiée'),
        ('ongoing', 'En cours'),
        ('finished', 'Terminée'),
        ('cancelled', 'Annulée'),
    )
    
    titre = models.CharField(max_length=200)
    description = models.TextField()
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    lieu = models.CharField(max_length=200)
    organisateur = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reunions_organisees')
    secretaire = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                  limit_choices_to={'role': 'secretary'})
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    qr_code_uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    qr_code_image = models.ImageField(upload_to='qr_codes/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_debut']
        verbose_name = 'Réunion'
        verbose_name_plural = 'Réunions'
    
    def __str__(self):
        return f"{self.titre} - {self.date_debut.strftime('%d/%m/%Y %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Sauvegarder d'abord pour avoir un ID
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Générer le QR code après la première sauvegarde
        if is_new or not self.qr_code_image:
            self.generate_qr_code()
    

    def generate_qr_code(self):
        """Génère le QR code pour cette réunion"""
        try:
            from django.conf import settings
        
             # ✅ CORRECTION: Utiliser l'IP publique configurée
            site_protocol = getattr(settings, 'SITE_PROTOCOL', 'http://')
            site_address = getattr(settings, 'SITE_ADDRESS', 'www.meeting.artci.ci')
            site_port = getattr(settings, 'SITE_PORT', '')
            
            # Construire l'URL de base
            if site_port:
                base_url = f"{site_protocol}{site_address}:{site_port}"
            else:
                base_url = f"{site_protocol}{site_address}"
            
            # URL complète pour le QR code avec l'IP publique
            qr_url = f"{base_url}/presence/{self.qr_code_uuid}/"
            
            print(f"🔗 Génération QR code avec URL: {qr_url}")  # Debug
            
            # Créer le QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # Créer l'image
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # Sauvegarder dans un buffer
            buffer = BytesIO()
            qr_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # Sauvegarder le fichier
            filename = f'qr_reunion_{self.id}_{self.qr_code_uuid.hex[:8]}.png'
            self.qr_code_image.save(
                filename,
                File(buffer),
                save=False
            )
            
            # Sauvegarder seulement le champ image
            super().save(update_fields=['qr_code_image'])
            
            print(f"✅ QR code généré avec succès: {filename}")  # Debug
            
        except Exception as e:
            print(f"❌ Erreur lors de la génération du QR code: {e}")
            import traceback
            traceback.print_exc()  # Debug détaillé

    
    def get_absolute_url(self):
        return reverse('reunion_detail', args=[str(self.id)])
    
    def get_presence_url(self):
        """Retourne l'URL pour confirmer la présence"""
        return reverse('presence_qr_redirect', args=[str(self.qr_code_uuid)])
    
    def get_participants_count(self):
        """Retourne le nombre de participants confirmés"""
        return self.presence_requests.filter(status='confirmed').count()
    
    def get_pending_requests_count(self):
        """Retourne le nombre de demandes en attente"""
        return self.presence_requests.filter(status='pending').count()
    
    def get_cancelled_requests_count(self):
        """Retourne le nombre de demandes annulées"""
        return self.presence_requests.filter(status='cancelled').count()
    
    def is_past(self):
        """Vérifie si la réunion est passée"""
        from django.utils import timezone
        return self.date_fin < timezone.now()
    
    def is_ongoing(self):
        """Vérifie si la réunion est en cours"""
        from django.utils import timezone
        now = timezone.now()
        return self.date_debut <= now <= self.date_fin
    
    def get_duration(self):
        """Retourne la durée de la réunion"""
        duration = self.date_fin - self.date_debut
        hours = duration.total_seconds() // 3600
        minutes = (duration.total_seconds() % 3600) // 60
        if hours > 0:
            return f"{int(hours)}h{int(minutes):02d}min"
        else:
            return f"{int(minutes)}min"

class CompteRendu(models.Model):

    reunion = models.ForeignKey(Reunion, on_delete=models.CASCADE, related_name='comptes_rendus')
    titre = models.CharField(max_length=200)
    fichier = models.FileField(upload_to='comptes_rendus/')
    version = models.PositiveIntegerField(default=1)
    cree_par = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    envoye_automatiquement = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-version', '-created_at']
        unique_together = ('reunion', 'version')
        verbose_name = 'Compte-rendu'
        verbose_name_plural = 'Comptes-rendus'
    
    def __str__(self):
        return f"{self.reunion.titre} - CR v{self.version}"
    
    def save(self, *args, **kwargs):
        if not self.pk:
            # Nouveau compte-rendu, incrémenter la version
            last_version = CompteRendu.objects.filter(reunion=self.reunion).aggregate(
                models.Max('version'))['version__max'] or 0
            self.version = last_version + 1
        super().save(*args, **kwargs)
    
    def get_file_size(self):
        """Retourne la taille du fichier en format lisible"""
        if self.fichier:
            try:
                size = self.fichier.size
                if size < 1024:
                    return f"{size} B"
                elif size < 1024 * 1024:
                    return f"{size // 1024} KB"
                else:
                    return f"{size // (1024 * 1024)} MB"
            except:
                return "Taille inconnue"
        return "0 B"
    
    def get_file_extension(self):
        """Retourne l'extension du fichier"""
        if self.fichier:
            return os.path.splitext(self.fichier.name)[1].upper().replace('.', '')
        return ""
    
    def get_file_icon(self):
        """Retourne l'icône FontAwesome appropriée selon le type de fichier"""
        ext = self.get_file_extension().lower()
        icons = {
            'pdf': 'fas fa-file-pdf text-danger',
            'doc': 'fas fa-file-word text-primary',
            'docx': 'fas fa-file-word text-primary',
            'txt': 'fas fa-file-alt text-secondary',
            'rtf': 'fas fa-file-alt text-info',
        }
        return icons.get(ext, 'fas fa-file text-muted')
    
    def get_file_name(self):
        """Retourne le nom du fichier sans le chemin"""
        if self.fichier:
            return os.path.basename(self.fichier.name)
        return ""
    
    def is_latest_version(self):
        """Vérifie si c'est la dernière version pour cette réunion"""
        latest = CompteRendu.objects.filter(reunion=self.reunion).order_by('-version').first()
        return latest and latest.pk == self.pk
    
    def get_previous_version(self):
        """Retourne la version précédente si elle existe"""
        if self.version > 1:
            return CompteRendu.objects.filter(
                reunion=self.reunion, 
                version=self.version - 1
            ).first()
        return None
    
    def get_next_version(self):
        """Retourne la version suivante si elle existe"""
        return CompteRendu.objects.filter(
            reunion=self.reunion, 
            version=self.version + 1
        ).first()
    
    def can_be_deleted(self):
        """Vérifie si le compte-rendu peut être supprimé"""
        # Seul le créateur ou un admin peut supprimer
        # Et seulement si c'est la dernière version
        return self.is_latest_version()
    
    def delete(self, *args, **kwargs):
        """Suppression personnalisée pour gérer le fichier"""
        # Supprimer le fichier physique
        if self.fichier:
            try:
                if os.path.isfile(self.fichier.path):
                    os.remove(self.fichier.path)
            except Exception as e:
                print(f"Erreur lors de la suppression du fichier: {e}")
        
        # Appeler la suppression par défaut
        super().delete(*args, **kwargs)

class PresenceRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('cancelled', 'Annulée'),
        ('auto_cancelled', 'Annulée automatiquement'),  # NOUVEAU
    )
    
    reunion = models.ForeignKey(Reunion, on_delete=models.CASCADE, related_name='presence_requests')
    email = models.EmailField()
    nom = models.CharField(max_length=100, blank=True)
    prenom = models.CharField(max_length=100, blank=True)
    organisation = models.CharField(max_length=200, blank=True)
    fonction = models.CharField(max_length=200, blank=True)  # NOUVEAU
    contact = models.CharField(max_length=20, blank=True)   # NOUVEAU
    validation_token = models.UUIDField(default=uuid.uuid4, unique=True)
    cancellation_token = models.UUIDField(default=uuid.uuid4, unique=True)  # NOUVEAU
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    consent_given = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    auto_confirm_at = models.DateTimeField(null=True, blank=True)  # NOUVEAU: Heure de confirmation automatique
    
    class Meta:
        unique_together = ('reunion', 'email')
        verbose_name = 'Demande de présence'
        verbose_name_plural = 'Demandes de présence'
        ordering = ['-created_at']
    
    def __str__(self):
        validation_type = "ARTCI" if self.is_artci_email() else "EXT"
        return f"[{validation_type}] {self.email} - {self.reunion.titre} ({self.get_status_display()})"
    
    def get_full_name(self):
        """Retourne le nom complet si disponible"""
        if self.prenom and self.nom:
            return f"{self.prenom} {self.nom}"
        elif self.prenom:
            return self.prenom
        elif self.nom:
            return self.nom
        else:
            return self.email
    
    def is_artci_email(self):
        """Vérifie si c'est un email ARTCI"""
        return self.email.lower().endswith('@artci.ci')
    
    def get_cancellation_url(self):
        """Retourne l'URL d'annulation"""
        from django.urls import reverse
        return reverse('presence_cancel', args=[str(self.cancellation_token)])
    
    def should_auto_confirm(self):
        """Vérifie si la demande doit être confirmée automatiquement (5 min écoulées)"""
        if self.status != 'pending' or not self.auto_confirm_at:
            return False
        from django.utils import timezone
        return timezone.now() >= self.auto_confirm_at
    
    def auto_confirm(self):
        """Confirmation automatique après 5 minutes"""
        if self.should_auto_confirm():
            self.status = 'confirmed'
            self.confirmed_at = timezone.now()
            self.save()
            return True
        return False


class CancellationLog(models.Model):
    """
    Modèle optionnel pour tracer toutes les annulations
    """
    presence_request = models.ForeignKey(PresenceRequest, on_delete=models.CASCADE)
    cancelled_at = models.DateTimeField(auto_now_add=True)
    cancelled_by_ip = models.GenericIPAddressField(blank=True, null=True)
    secretary_notified = models.BooleanField(default=False)
    secretary_email = models.EmailField(blank=True)
    cancellation_reason = models.TextField(blank=True, help_text="Raison optionnelle")
    
    class Meta:
        verbose_name = 'Log d\'annulation'
        verbose_name_plural = 'Logs d\'annulation'
        ordering = ['-cancelled_at']
    
    def __str__(self):
        return f"Annulation - {self.presence_request.email} - {self.cancelled_at.strftime('%d/%m/%Y %H:%M')}"
