# reunions/tasks.py (si vous utilisez Celery pour les tâches asynchrones)
from celery import shared_task
from django.utils import timezone
from .models import PresenceRequest
import logging

logger = logging.getLogger(__name__)

@shared_task
def auto_confirm_pending_presences():
    """
    Tâche Celery pour confirmer automatiquement les présences en attente
    À programmer pour s'exécuter toutes les minutes
    """
    pending_requests = PresenceRequest.objects.filter(
        status='pending',
        auto_confirm_at__lte=timezone.now()
    )
    
    confirmed_count = 0
    for request in pending_requests:
        try:
            request.status = 'confirmed'
            request.confirmed_at = timezone.now()
            request.save()
            confirmed_count += 1
            
            logger.info(
                f"Auto-confirmed presence: {request.email} for {request.reunion.titre}"
            )
            
            # Optionnel: Envoyer un email de confirmation finale
            # send_final_confirmation_email(request)
            
        except Exception as e:
            logger.error(
                f"Error auto-confirming presence {request.id}: {str(e)}"
            )
    
    if confirmed_count > 0:
        logger.info(f"Auto-confirmed {confirmed_count} pending presences")
    
    return confirmed_count

@shared_task
def backup_database():
    """
    Sauvegarde automatique quotidienne de la base et des médias.
    Programmée à 02h00 via CELERY_BEAT_SCHEDULE dans settings.py.
    """
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    try:
        call_command('backup_create', keep=7, stdout=out)
        logger.info(f'Sauvegarde automatique réussie :\n{out.getvalue()}')
        return True
    except Exception as exc:
        logger.error(f'Échec de la sauvegarde automatique : {exc}')
        return False


@shared_task
def cleanup_expired_requests():
    """
    Tâche Celery pour nettoyer les anciennes demandes expirées
    À programmer pour s'exécuter quotidiennement
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=30)
    
    expired_requests = PresenceRequest.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['pending', 'cancelled']
    )
    
    deleted_count = expired_requests.count()
    if deleted_count > 0:
        expired_requests.delete()
        logger.info(f"Cleaned up {deleted_count} expired presence requests")
    
    return deleted_count
