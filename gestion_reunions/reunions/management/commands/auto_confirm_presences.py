from django.core.management.base import BaseCommand
from django.utils import timezone
from reunions.models import PresenceRequest

class Command(BaseCommand):
    help = 'Confirme automatiquement les demandes de présence après 5 minutes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les demandes qui seraient confirmées sans les modifier',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Trouver les demandes à confirmer automatiquement
        pending_requests = PresenceRequest.objects.filter(
            status='pending',
            auto_confirm_at__lte=timezone.now()
        )
        
        if not pending_requests.exists():
            self.stdout.write(
                self.style.SUCCESS('Aucune demande en attente de confirmation automatique.')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'MODE DRY-RUN: {pending_requests.count()} demandes seraient confirmées:')
            )
            for request in pending_requests:
                self.stdout.write(
                    f'  - {request.email} pour "{request.reunion.titre}" '
                    f'(créée le {request.created_at.strftime("%d/%m/%Y %H:%M")})'
                )
        else:
            confirmed_count = 0
            for request in pending_requests:
                request.status = 'confirmed'
                request.confirmed_at = timezone.now()
                request.save()
                confirmed_count += 1
                
                self.stdout.write(
                    f'✅ Confirmé: {request.email} pour "{request.reunion.titre}"'
                )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ {confirmed_count} demandes confirmées automatiquement.')
            )