import sqlite3
import tempfile
from pathlib import Path

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from .forms import ROLE_GROUPS
from .models import JournalAudit, Utilisateur


class UtilisateurManagementTests(TestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            username='admin-test',
            email='admin@example.test',
            password='SafeAdminPass!928',
        )
        self.client.force_login(self.admin)

    def test_create_user_hashes_password_and_assigns_role_group(self):
        response = self.client.post(reverse('utilisateur_create'), {
            'username': 'caissier-test',
            'first_name': 'Test',
            'last_name': 'Caissier',
            'email': 'cashier@example.test',
            'telephone': '',
            'role': Utilisateur.ROLE_CAISSIER,
            'roles': [Utilisateur.ROLE_GESTIONNAIRE_STOCK],
            'is_active': 'on',
            'mot_de_passe': 'UniquePass!9284',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('utilisateur_list'))
        user = Utilisateur.objects.get(username='caissier-test')
        self.assertTrue(user.check_password('UniquePass!9284'))
        self.assertFalse(user.password == 'UniquePass!9284')
        self.assertIn(ROLE_GROUPS[Utilisateur.ROLE_CAISSIER], user.groups.values_list('name', flat=True))
        self.assertIn(ROLE_GROUPS[Utilisateur.ROLE_GESTIONNAIRE_STOCK], user.groups.values_list('name', flat=True))

    def test_user_list_requires_permission(self):
        self.admin.is_superuser = False
        self.admin.is_staff = False
        self.admin.save()
        self.assertEqual(self.client.get(reverse('utilisateur_list')).status_code, 403)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            username='reset-test',
            email='reset@example.test',
            password='OldSafePass!9284',
        )

    def test_password_reset_email_completes_password_change(self):
        response = self.client.post(reverse('password_reset'), {'email': self.user.email})

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        reset_path = mail.outbox[0].body.split('http://testserver', 1)[1].split()[0]
        response = self.client.get(reset_path)
        self.assertEqual(response.status_code, 302)

        response = self.client.post(response.url, {
            'new_password1': 'NewSafePass!9284',
            'new_password2': 'NewSafePass!9284',
        })
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSafePass!9284'))
        self.assertTrue(JournalAudit.objects.filter(
            utilisateur=self.user,
            action='REINITIALISATION_MOT_DE_PASSE',
        ).exists())

    def test_unknown_email_does_not_reveal_account_existence(self):
        response = self.client.post(reverse('password_reset'), {'email': 'unknown@example.test'})

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)


class DatabaseBackupCommandTests(TestCase):
    def test_backup_command_creates_integrity_checked_sqlite_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.sqlite3'
            output = Path(directory) / 'pharmagest-backup.sqlite3'
            database = sqlite3.connect(str(source))
            try:
                database.execute('CREATE TABLE backup_probe (value TEXT)')
                database.execute("INSERT INTO backup_probe VALUES ('ok')")
                database.commit()
            finally:
                database.close()
            with patch('utilisateurs.management.commands.sauvegarder_base.settings.DATABASES', {
                'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(source)},
            }):
                call_command('sauvegarder_base', output=str(output))
            self.assertTrue(output.is_file())
            backup = sqlite3.connect(str(output))
            try:
                self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(backup.execute('SELECT value FROM backup_probe').fetchone()[0], 'ok')
            finally:
                backup.close()

    def test_restore_command_requires_explicit_confirmation(self):
        with self.assertRaisesMessage(CommandError, '--confirm'):
            call_command('restaurer_base', 'backup.sqlite3')
