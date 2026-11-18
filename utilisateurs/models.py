from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    ROLE_ADMIN = 'ADMIN'
    ROLE_PHARMACIEN = 'PHARMACIEN'
    ROLE_GESTIONNAIRE_STOCK = 'GESTIONNAIRE_STOCK'
    ROLE_CAISSIER = 'CAISSIER'
    ROLE_RESPONSABLE_GESTION = 'RESPONSABLE_GESTION'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrateur'),
        (ROLE_PHARMACIEN, 'Pharmacien responsable'),
        (ROLE_GESTIONNAIRE_STOCK, 'Gestionnaire de stock'),
        (ROLE_CAISSIER, 'Caissier'),
        (ROLE_RESPONSABLE_GESTION, 'Responsable de gestion'),
    ]

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default=ROLE_CAISSIER,
        verbose_name='Rôle principal',
    )
    telephone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['username']

    def __str__(self):
        nom = self.get_full_name()
        return f"{nom} ({self.get_role_display()})" if nom else f"{self.username} ({self.get_role_display()})"


class JournalAudit(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audits',
        verbose_name='Utilisateur',
    )
    action = models.CharField(max_length=100, verbose_name='Action')
    modele_cible = models.CharField(max_length=100, verbose_name='Modèle cible')
    objet_id = models.CharField(max_length=50, blank=True, verbose_name='ID objet')
    details = models.TextField(blank=True, verbose_name='Détails')
    adresse_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='Adresse IP')
    date_action = models.DateTimeField(auto_now_add=True, verbose_name='Date')

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ['-date_action']

    def __str__(self):
        return f"{self.date_action:%Y-%m-%d %H:%M} — {self.action} ({self.modele_cible})"