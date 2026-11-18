import sqlite3
from contextlib import closing
from pathlib import Path

from django.core.management.base import CommandError
from django.utils import timezone


def create_database_backup(source_path, output_path):
    source_path = Path(source_path)
    output_path = Path(output_path)
    if not source_path.is_file():
        raise CommandError(f"Base SQLite introuvable : {source_path}")
    if source_path.resolve() == output_path.resolve():
        raise CommandError("La destination de sauvegarde ne peut pas être la base active.")
    if output_path.exists():
        raise CommandError(f"Le fichier de destination existe déjà : {output_path}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(source_path))) as source:
            with closing(sqlite3.connect(str(output_path))) as target:
                source.backup(target)
                result = target.execute('PRAGMA integrity_check').fetchone()
                target.commit()
                if not result or result[0] != 'ok':
                    raise CommandError("La sauvegarde créée n'a pas passé le contrôle d'intégrité SQLite.")
    except CommandError:
        if output_path.exists():
            output_path.unlink()
        raise
    except sqlite3.Error as error:
        if output_path.exists():
            output_path.unlink()
        raise CommandError(f"Impossible de créer la sauvegarde : {error}") from error
    except OSError as error:
        raise CommandError(f"Impossible d'écrire la sauvegarde : {error}") from error
    return output_path


def default_backup_path(base_dir):
    timestamp = timezone.localtime().strftime('%Y%m%d-%H%M%S-%f')
    return Path(base_dir) / 'backups' / f'pharmagest-{timestamp}.sqlite3'
