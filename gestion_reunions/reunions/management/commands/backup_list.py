"""
Affiche la liste des sauvegardes disponibles.

Usage :
    python manage.py backup_list
"""

import json
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Liste les sauvegardes disponibles'

    def handle(self, *args, **options):
        backup_root = Path(getattr(settings, 'BACKUP_ROOT', settings.BASE_DIR / 'db_backup'))

        if not backup_root.exists():
            self.stdout.write(self.style.WARNING('Aucun dossier de sauvegarde trouvé.'))
            return

        backups = sorted(backup_root.glob('backup_*.tar.gz'), reverse=True)

        if not backups:
            self.stdout.write(self.style.WARNING('Aucune sauvegarde disponible.'))
            return

        self.stdout.write(f'\n📦 Sauvegardes disponibles ({len(backups)}) — {backup_root}')
        self.stdout.write('─' * 70)
        self.stdout.write(f'  {"Fichier":<35} {"Taille":>10}  {"Date":<20}  Médias')
        self.stdout.write('─' * 70)

        for archive in backups:
            size_mb = archive.stat().st_size / (1024 * 1024)
            includes_media = '✅'

            # Lire les métadonnées si disponibles
            created_at = '—'
            try:
                with tarfile.open(str(archive), 'r:gz') as tar:
                    meta_member = next(
                        (m for m in tar.getmembers() if m.name.endswith('metadata.json')),
                        None
                    )
                    if meta_member:
                        f = tar.extractfile(meta_member)
                        meta = json.loads(f.read().decode())
                        created_at = meta.get('created_at', '—')[:19].replace('T', ' ')
                        includes_media = '✅' if meta.get('includes_media') else '❌'
            except Exception:
                pass

            self.stdout.write(
                f'  {archive.name:<35} {size_mb:>8.1f} Mo  {created_at:<20}  {includes_media}'
            )

        self.stdout.write('─' * 70)
        self.stdout.write(f'\nPour restaurer : python manage.py backup_restore <nom_fichier>\n')
