from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from reunions.models import PresenceRequest

class Command(BaseCommand):
    help = 'Nettoie les anciennes demandes de présence expirées'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Nombre de jours après lesquels supprimer les demandes expirées (défaut: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les demandes qui seraient supprimées sans les supprimer',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Trouver les demandes anciennes et non confirmées
        expired_requests = PresenceRequest.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['pending', 'cancelled']
        )
        
        if not expired_requests.exists():
            self.stdout.write(
                self.style.SUCCESS(f'Aucune demande expirée de plus de {days} jours.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'MODE DRY-RUN: {expired_requests.count()} demandes seraient supprimées:')
            )
            for request in expired_requests:
                self.stdout.write(
                    f'  - {request.email} pour "{request.reunion.titre}" '
                    f'(créée le {request.created_at.strftime("%d/%m/%Y %H:%M")}, statut: {request.get_status_display()})'
                )
        else:
            deleted_count = expired_requests.count()
            expired_requests.delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'🗑️ {deleted_count} demandes expirées supprimées.')
            )