import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from utilisateurs.management.backup import create_database_backup, default_backup_path


class Command(BaseCommand):
    help = 'Restaure une sauvegarde SQLite après validation et sauvegarde de la base actuelle.'

    def add_arguments(self, parser):
        parser.add_argument('source', help='Chemin du fichier SQLite de sauvegarde.')
        parser.add_argument('--confirm', action='store_true', help='Confirme le remplacement de la base active.')

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Cette commande ne prend en charge que SQLite.')
        if not options['confirm']:
            raise CommandError('Ajoutez --confirm pour autoriser le remplacement de la base active.')

        source = Path(options['source']).resolve()
        database_path = Path(database['NAME']).resolve()
        if not source.is_file():
            raise CommandError(f'Fichier de sauvegarde introuvable : {source}')
        if source == database_path:
            raise CommandError('Le fichier source est déjà la base active.')
        try:
            with closing(sqlite3.connect(str(source))) as db:
                integrity = db.execute('PRAGMA integrity_check').fetchone()
            if not integrity or integrity[0] != 'ok':
                raise CommandError('La sauvegarde source est invalide ou endommagée.')
        except sqlite3.Error as error:
            raise CommandError(f'Impossible de vérifier la sauvegarde : {error}') from error

        snapshot = default_backup_path(settings.BASE_DIR)
        create_database_backup(database_path, snapshot)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f'{database_path.stem}-restore-',
                suffix=database_path.suffix,
                dir=str(database_path.parent),
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
            with closing(sqlite3.connect(str(source))) as source_db:
                with closing(sqlite3.connect(str(temporary_path))) as target_db:
                    source_db.backup(target_db)
                    integrity = target_db.execute('PRAGMA integrity_check').fetchone()
                    target_db.commit()
            if not integrity or integrity[0] != 'ok':
                raise CommandError('La copie temporaire restaurée est invalide.')
            connections.close_all()
            os.replace(temporary_path, database_path)
            temporary_path = None
        except (OSError, sqlite3.Error) as error:
            raise CommandError(f'Échec de la restauration : {error}') from error
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()
        self.stdout.write(self.style.SUCCESS(f'Base restaurée. Sauvegarde de sécurité : {snapshot}'))
