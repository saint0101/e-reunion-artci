"""
Commande de restauration d'une sauvegarde.

Usage :
    python manage.py backup_restore backup_20250611_143000.tar.gz
    python manage.py backup_restore backup_20250611_143000.tar.gz --db-only
    python manage.py backup_restore backup_20250611_143000.tar.gz --media-only
"""

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Restaure une sauvegarde (base de données + médias)'

    def add_arguments(self, parser):
        parser.add_argument('backup_file', help='Nom ou chemin de la sauvegarde (.tar.gz)')
        parser.add_argument('--db-only', action='store_true', help='Restaurer uniquement la base de données')
        parser.add_argument('--media-only', action='store_true', help='Restaurer uniquement les médias')
        parser.add_argument('--yes', action='store_true', help='Confirmer sans demander')

    def handle(self, *args, **options):
        backup_root = Path(getattr(settings, 'BACKUP_ROOT', settings.BASE_DIR / 'db_backup'))
        archive = Path(options['backup_file'])

        if not archive.is_absolute():
            archive = backup_root / archive

        if not archive.exists():
            raise CommandError(f'Sauvegarde introuvable : {archive}')

        # Confirmation
        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  ATTENTION : Cette opération va écraser les données actuelles !'
                f'\n   Fichier : {archive.name}'
            ))
            confirm = input('   Continuer ? (oui/non) : ').strip().lower()
            if confirm not in ('oui', 'o', 'yes', 'y'):
                self.stdout.write('Annulé.')
                return

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self.stdout.write(f'\n📦 Extraction de {archive.name}...')

            with tarfile.open(str(archive), 'r:gz') as tar:
                tar.extractall(tmp)

            extracted = list(tmp_path.iterdir())
            if not extracted:
                raise CommandError('Archive vide ou corrompue.')
            work_dir = extracted[0]

            # Lire les métadonnées
            meta_file = work_dir / 'metadata.json'
            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                self.stdout.write(f'  📋 Sauvegarde du : {meta.get("created_at", "?")}')
                self.stdout.write(f'  📋 Base de données : {meta.get("database", "?")}')

            if not options['media_only']:
                self._restore_database(work_dir)

            if not options['db_only']:
                self._restore_media(work_dir)

            self.stdout.write(self.style.SUCCESS('\n✅ Restauration terminée avec succès.'))

    def _restore_database(self, work_dir):
        dump_file = work_dir / 'database.sql'
        if not dump_file.exists():
            self.stdout.write(self.style.WARNING('  ⚠️  Aucun dump SQL trouvé, restauration BD ignorée.'))
            return

        db = settings.DATABASES['default']
        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        self.stdout.write('  🔄 Restauration de la base de données...')

        # Supprimer et recréer la base
        drop_cmd = [
            'psql',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', 5432)),
            '-U', db.get('USER', ''),
            '-d', 'postgres',
            '--no-password',
            '-c', f'DROP DATABASE IF EXISTS "{db["NAME"]}"; CREATE DATABASE "{db["NAME"]}";',
        ]
        result = subprocess.run(drop_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise CommandError(f'Impossible de recréer la base :\n{result.stderr}')

        # Restaurer le dump
        restore_cmd = [
            'psql',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', 5432)),
            '-U', db.get('USER', ''),
            '-d', db.get('NAME', ''),
            '--no-password',
            '-f', str(dump_file),
        ]
        result = subprocess.run(restore_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise CommandError(f'psql a échoué :\n{result.stderr}')

        self.stdout.write('  ✅ Base de données restaurée')

    def _restore_media(self, work_dir):
        media_src = work_dir / 'media'
        if not media_src.exists():
            self.stdout.write('  ⚠️  Aucun dossier média dans la sauvegarde, ignoré.')
            return

        media_dest = Path(settings.MEDIA_ROOT)
        if media_dest.exists():
            shutil.rmtree(str(media_dest))
        shutil.copytree(str(media_src), str(media_dest))
        count = sum(1 for _ in media_dest.rglob('*') if _.is_file())
        self.stdout.write(f'  ✅ Médias restaurés ({count} fichier(s))')
