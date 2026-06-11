"""
Commande de sauvegarde complète : base de données PostgreSQL + fichiers médias.

Usage :
    python manage.py backup_create
    python manage.py backup_create --no-media
    python manage.py backup_create --keep 14
"""

import json
import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crée une sauvegarde complète (base de données PostgreSQL + médias)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-media',
            action='store_true',
            help='Sauvegarder uniquement la base de données (pas les fichiers médias)',
        )
        parser.add_argument(
            '--keep',
            type=int,
            default=7,
            help='Nombre de sauvegardes à conserver (défaut : 7)',
        )

    def handle(self, *args, **options):
        backup_root = Path(getattr(settings, 'BACKUP_ROOT', settings.BASE_DIR / 'db_backup'))
        backup_root.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'backup_{ts}'
        work_dir = backup_root / backup_name  # dossier temporaire de travail
        work_dir.mkdir()

        try:
            self.stdout.write(f'\n🔄 Démarrage de la sauvegarde : {backup_name}')
            self.stdout.write('─' * 50)

            self._dump_database(work_dir)

            if not options['no_media']:
                self._backup_media(work_dir)
            else:
                self.stdout.write('  ⏭️  Médias ignorés (--no-media)')

            self._write_metadata(work_dir, options)

            archive_path = backup_root / f'{backup_name}.tar.gz'
            self._compress(work_dir, archive_path)

            self._clean_old(backup_root, options['keep'])

            size_mb = archive_path.stat().st_size / (1024 * 1024)
            self.stdout.write('─' * 50)
            self.stdout.write(self.style.SUCCESS(
                f'✅ Sauvegarde terminée : {archive_path.name} ({size_mb:.1f} Mo)'
            ))
            return str(archive_path)

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'\n❌ Erreur : {exc}'))
            raise

        finally:
            if work_dir.exists():
                shutil.rmtree(work_dir)

    # ── Étapes ────────────────────────────────────────────────────────────────

    def _dump_database(self, work_dir):
        db = settings.DATABASES['default']
        env = os.environ.copy()
        env['PGPASSWORD'] = db.get('PASSWORD', '')

        dump_file = work_dir / 'database.sql'
        cmd = [
            'pg_dump',
            '-h', db.get('HOST', 'localhost'),
            '-p', str(db.get('PORT', 5432)),
            '-U', db.get('USER', ''),
            '-d', db.get('NAME', ''),
            '--no-password',
            '-f', str(dump_file),
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise CommandError(f'pg_dump a échoué :\n{result.stderr}')

        size_kb = dump_file.stat().st_size // 1024
        self.stdout.write(f'  ✅ Base de données exportée ({size_kb} Ko)')

    def _backup_media(self, work_dir):
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write('  ⚠️  Dossier média introuvable, ignoré')
            return

        dest = work_dir / 'media'
        shutil.copytree(str(media_root), str(dest))
        count = sum(1 for _ in dest.rglob('*') if _.is_file())
        self.stdout.write(f'  ✅ Médias sauvegardés ({count} fichier(s))')

    def _write_metadata(self, work_dir, options):
        import django
        meta = {
            'created_at': datetime.now().isoformat(),
            'django_version': django.__version__,
            'database': settings.DATABASES['default'].get('NAME', ''),
            'includes_media': not options['no_media'],
        }
        (work_dir / 'metadata.json').write_text(
            json.dumps(meta, indent=2, ensure_ascii=False)
        )
        self.stdout.write('  ✅ Métadonnées écrites')

    def _compress(self, source_dir, dest_path):
        with tarfile.open(str(dest_path), 'w:gz') as tar:
            tar.add(str(source_dir), arcname=source_dir.name)
        self.stdout.write('  ✅ Archive compressée')

    def _clean_old(self, backup_root, keep):
        backups = sorted(backup_root.glob('backup_*.tar.gz'))
        to_delete = backups[:-keep] if len(backups) > keep else []
        for old in to_delete:
            old.unlink()
            self.stdout.write(f'  🗑️  Ancienne sauvegarde supprimée : {old.name}')
