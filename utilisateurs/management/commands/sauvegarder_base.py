from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from utilisateurs.management.backup import create_database_backup, default_backup_path


class Command(BaseCommand):
    help = 'Crée une sauvegarde cohérente de la base SQLite PharmaGest.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Chemin complet du fichier de sauvegarde.')

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Cette commande ne prend en charge que SQLite.')
        output = options['output'] or default_backup_path(settings.BASE_DIR)
        path = create_database_backup(database['NAME'], output)
        self.stdout.write(self.style.SUCCESS(f'Sauvegarde créée : {path}'))
