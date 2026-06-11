# reunions/tasks.py (si vous utilisez Celery pour les tâches asynchrones)
from celery import shared_task
from django.utils import timezone
from .models import PresenceRequest, Reunion, Diligence
import logging
from datetime import timedelta

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


@shared_task
def send_reminder_j_minus_1():
    """
    Envoie un rappel email J-1 aux participants confirmés des réunions planifiées.
    À exécuter toutes les heures via Celery Beat.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings

    now = timezone.now()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)

    reunions = Reunion.objects.filter(
        status='planned',
        rappels_actives=True,
        rappel_j1_envoye=False,
        date_debut__range=(window_start, window_end),
    )

    sent_count = 0
    for reunion in reunions:
        participants = PresenceRequest.objects.filter(reunion=reunion, status='confirmed')
        if not participants.exists():
            reunion.rappel_j1_envoye = True
            reunion.save(update_fields=['rappel_j1_envoye'])
            continue

        agenda_points = reunion.agenda_points.all()
        subject = f"Rappel : {reunion.titre} — demain à {reunion.date_debut.strftime('%H:%M')}"

        for participant in participants:
            context = {
                'reunion': reunion,
                'participant': participant,
                'agenda_points': agenda_points,
                'cancellation_url': _build_base_url() + f'/cancel/{participant.cancellation_token}/',
            }
            try:
                html_content = render_to_string('reunions/email_rappel_j1.html', context)
            except Exception:
                html_content = None

            text_content = (
                f"Bonjour,\n\n"
                f"Rappel : la réunion « {reunion.titre} » a lieu demain "
                f"le {reunion.date_debut.strftime('%d/%m/%Y à %H:%M')} — {reunion.lieu}.\n\n"
                f"Cordialement,\nL'équipe QR Meeting\n"
            )

            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[participant.email],
                )
                if html_content:
                    email.attach_alternative(html_content, "text/html")
                email.send()
                sent_count += 1
            except Exception as e:
                logger.error(f"Erreur rappel J-1 pour {participant.email}: {e}")

        reunion.rappel_j1_envoye = True
        reunion.save(update_fields=['rappel_j1_envoye'])
        logger.info(f"Rappel J-1 envoyé pour réunion {reunion.pk} ({participants.count()} participants)")

    return sent_count


@shared_task
def notify_participants_reunion_annulee(reunion_id):
    """
    Notifie tous les participants confirmés que la réunion a été annulée.
    Appelé depuis update_reunion_status quand le statut passe à 'cancelled'.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    try:
        reunion = Reunion.objects.get(pk=reunion_id)
    except Reunion.DoesNotExist:
        logger.error(f"notify_participants_reunion_annulee: réunion {reunion_id} introuvable")
        return 0

    participants = PresenceRequest.objects.filter(reunion=reunion, status='confirmed')
    sent_count = 0

    subject = f"Annulation — {reunion.titre}"
    for participant in participants:
        text_content = (
            f"Bonjour,\n\n"
            f"Nous vous informons que la réunion « {reunion.titre} » prévue le "
            f"{reunion.date_debut.strftime('%d/%m/%Y à %H:%M')} a été annulée.\n\n"
            f"Nous vous prions de nous excuser pour la gêne occasionnée.\n\n"
            f"Cordialement,\nL'équipe QR Meeting\n"
        )
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[participant.email],
            )
            email.send()
            sent_count += 1
        except Exception as e:
            logger.error(f"Erreur notification annulation pour {participant.email}: {e}")

    logger.info(f"Notifications annulation envoyées pour réunion {reunion_id} ({sent_count} emails)")
    return sent_count


@shared_task
def send_weekly_summary():
    """
    Envoie un récapitulatif hebdomadaire aux admins et secrétaires chaque lundi à 8h.
    Couvre du lundi au dimanche de la semaine précédente.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    from .models import CustomUser
    from django.db.models import Count

    now = timezone.now()
    # Lundi précédent 00:00
    start = (now - timedelta(days=now.weekday() + 7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(days=7)

    reunions_semaine = Reunion.objects.filter(
        status='finished',
        date_debut__gte=start,
        date_debut__lt=end,
    ).prefetch_related('presence_requests')

    total_participants = PresenceRequest.objects.filter(
        status='confirmed',
        confirmed_at__gte=start,
        confirmed_at__lt=end,
    ).count()

    top_organisations = (
        PresenceRequest.objects.filter(
            status='confirmed',
            confirmed_at__gte=start,
            confirmed_at__lt=end,
        )
        .exclude(organisation='')
        .values('organisation')
        .annotate(n=Count('id'))
        .order_by('-n')[:5]
    )

    prochaines_reunions = Reunion.objects.filter(
        status='planned',
        date_debut__gte=now,
        date_debut__lt=now + timedelta(days=7),
    ).order_by('date_debut')

    reunions_data = []
    for reunion in reunions_semaine:
        nb = reunion.presence_requests.filter(status='confirmed').count()
        reunions_data.append({'reunion': reunion, 'nb_participants': nb})

    destinataires = list(
        CustomUser.objects.filter(
            role__in=['admin', 'secretary'],
            email__isnull=False,
        ).exclude(email='').values_list('email', flat=True)
    )

    if not destinataires:
        logger.info("send_weekly_summary: aucun destinataire trouvé")
        return 0

    context = {
        'start': start,
        'end': end - timedelta(seconds=1),
        'reunions_data': reunions_data,
        'total_participants': total_participants,
        'top_organisations': top_organisations,
        'prochaines_reunions': prochaines_reunions,
    }

    subject = f"Récapitulatif hebdomadaire — semaine du {start.strftime('%d/%m')} au {(end - timedelta(days=1)).strftime('%d/%m/%Y')}"

    try:
        html_content = render_to_string('reunions/email_weekly_summary.html', context)
    except Exception as e:
        logger.error(f"send_weekly_summary: erreur rendu template: {e}")
        html_content = None

    text_content = (
        f"Récapitulatif de la semaine du {start.strftime('%d/%m/%Y')} "
        f"au {(end - timedelta(days=1)).strftime('%d/%m/%Y')}.\n\n"
        f"Réunions tenues : {len(reunions_data)}\n"
        f"Total participants : {total_participants}\n\n"
        f"Cordialement,\nL'équipe QR Meeting\n"
    )

    sent_count = 0
    for email_addr in destinataires:
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_addr],
            )
            if html_content:
                email.attach_alternative(html_content, "text/html")
            email.send()
            sent_count += 1
        except Exception as e:
            logger.error(f"send_weekly_summary: erreur envoi à {email_addr}: {e}")

    logger.info(f"send_weekly_summary: {sent_count} emails envoyés")
    return sent_count


@shared_task
def send_diligence_reminders():
    """
    Envoie des rappels email aux responsables des diligences dont l'échéance approche.
    - J-3 : rappel à 3 jours de l'échéance
    - J-1 : rappel la veille de l'échéance
    Exécuté quotidiennement à 7h via Celery Beat.
    """
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    from datetime import date

    today = timezone.now().date()
    j1 = today + timedelta(days=1)
    j3 = today + timedelta(days=3)

    sent_count = 0

    def _get_email_for_diligence(diligence):
        """Retourne l'email du responsable ou du créateur."""
        if diligence.responsable_interne and diligence.responsable_interne.email:
            return diligence.responsable_interne.email
        if diligence.created_by and diligence.created_by.email:
            return diligence.created_by.email
        return None

    def _send_rappel(diligence, horizon_label):
        dest_email = _get_email_for_diligence(diligence)
        if not dest_email:
            return False

        responsable_nom = diligence.get_responsable_display()
        context = {
            'diligence': diligence,
            'reunion': diligence.reunion,
            'horizon_label': horizon_label,
            'responsable_nom': responsable_nom,
            'base_url': _build_base_url(),
        }
        subject = f"Rappel diligence ({horizon_label}) — {diligence.titre}"

        try:
            html_content = render_to_string('reunions/email_rappel_diligence.html', context)
        except Exception:
            html_content = None

        text_content = (
            f"Bonjour {responsable_nom},\n\n"
            f"Rappel : la diligence « {diligence.titre} » issue de la réunion "
            f"« {diligence.reunion.titre} » arrive à échéance {horizon_label} "
            f"(le {diligence.echeance.strftime('%d/%m/%Y')}).\n\n"
            f"Statut actuel : {diligence.get_status_display()}\n\n"
            f"Merci de traiter cette action dans les délais impartis.\n\n"
            f"Cordialement,\nL'équipe QR Meeting\n"
        )

        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[dest_email],
            )
            if html_content:
                email.attach_alternative(html_content, "text/html")
            email.send()
            logger.info(f"Rappel diligence {diligence.pk} ({horizon_label}) → {dest_email}")
            return True
        except Exception as e:
            logger.error(f"Erreur rappel diligence {diligence.pk} ({horizon_label}): {e}")
            return False

    # ── Rappels J-3 ──────────────────────────────────────────────────────────
    diligences_j3 = Diligence.objects.filter(
        echeance=j3,
        rappel_j3_envoye=False,
        status__in=['open', 'in_progress'],
    ).select_related('responsable_interne', 'created_by', 'reunion')

    for d in diligences_j3:
        if _send_rappel(d, "dans 3 jours"):
            sent_count += 1
        d.rappel_j3_envoye = True
        d.save(update_fields=['rappel_j3_envoye'])

    # ── Rappels J-1 ──────────────────────────────────────────────────────────
    diligences_j1 = Diligence.objects.filter(
        echeance=j1,
        rappel_j1_envoye=False,
        status__in=['open', 'in_progress'],
    ).select_related('responsable_interne', 'created_by', 'reunion')

    for d in diligences_j1:
        if _send_rappel(d, "demain"):
            sent_count += 1
        d.rappel_j1_envoye = True
        d.save(update_fields=['rappel_j1_envoye'])

    logger.info(f"send_diligence_reminders: {sent_count} rappel(s) envoyé(s)")
    return sent_count


def _build_base_url():
    """URL de base du site (utilisée dans les tâches Celery sans request)."""
    from django.conf import settings
    protocol = getattr(settings, 'SITE_PROTOCOL', 'https://')
    address = getattr(settings, 'SITE_ADDRESS', 'meeting.artci.ci')
    port = getattr(settings, 'SITE_PORT', '')
    if port:
        return f"{protocol}{address}:{port}"
    return f"{protocol}{address}"
