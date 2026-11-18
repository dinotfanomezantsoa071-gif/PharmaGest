from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class CommandeAchat(models.Model):
    STATUT_BROUILLON = 'BROUILLON'
    STATUT_COMMANDEE = 'COMMANDEE'
    STATUT_PARTIELLE = 'PARTIELLE'
    STATUT_RECUE = 'RECUE'
    STATUT_ANNULEE = 'ANNULEE'

    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_COMMANDEE, 'Commandée'),
        (STATUT_PARTIELLE, 'Partiellement réceptionnée'),
        (STATUT_RECUE, 'Entièrement réceptionnée'),
        (STATUT_ANNULEE, 'Annulée'),
    ]

    numero = models.CharField(max_length=50, unique=True, verbose_name='Numéro de commande')
    fournisseur = models.ForeignKey(
        'fournisseurs.Fournisseur',
        on_delete=models.PROTECT,
        related_name='commandes',
        verbose_name='Fournisseur',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='commandes_achat',
        verbose_name='Créée par',
    )
    date_commande = models.DateTimeField(auto_now_add=True, verbose_name='Date de commande')
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_BROUILLON,
        verbose_name='Statut',
    )
    montant_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Montant total',
    )
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = "Commande d'achat"
        verbose_name_plural = "Commandes d'achat"
        ordering = ['-date_commande']

    def __str__(self):
        return f"{self.numero} — {self.fournisseur.raison_sociale}"


class LigneAchat(models.Model):
    commande = models.ForeignKey(
        CommandeAchat,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Commande',
    )
    medicament = models.ForeignKey(
        'medicaments.Medicament',
        on_delete=models.PROTECT,
        related_name='lignes_achat',
        verbose_name='Médicament',
    )
    quantite_commandee = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Quantité commandée',
    )
    quantite_recue = models.PositiveIntegerField(default=0, verbose_name='Quantité reçue')
    prix_unitaire_achat = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Prix unitaire d'achat",
    )
    sous_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Sous-total',
    )

    class Meta:
        verbose_name = "Ligne d'achat"
        verbose_name_plural = "Lignes d'achat"

    def save(self, *args, **kwargs):
        self.sous_total = Decimal(self.quantite_commandee) * self.prix_unitaire_achat
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicament.nom_commercial} x {self.quantite_commandee}"


class ReceptionAchat(models.Model):
    numero = models.CharField(max_length=50, unique=True, verbose_name='Numéro de réception')
    commande = models.ForeignKey(
        CommandeAchat,
        on_delete=models.PROTECT,
        related_name='receptions',
        verbose_name='Commande associée',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='receptions_achat',
        verbose_name='Réceptionnée par',
    )
    date_reception = models.DateTimeField(auto_now_add=True, verbose_name='Date de réception')
    observations = models.TextField(blank=True, verbose_name='Observations')
    validee = models.BooleanField(default=False, verbose_name='Validée')

    class Meta:
        verbose_name = "Réception d'achat"
        verbose_name_plural = "Réceptions d'achat"
        ordering = ['-date_reception']

    def __str__(self):
        return f"{self.numero} (Cmd: {self.commande.numero})"


class LigneReception(models.Model):
    reception = models.ForeignKey(
        ReceptionAchat,
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name='Réception',
    )
    ligne_achat = models.ForeignKey(
        LigneAchat,
        on_delete=models.PROTECT,
        related_name='receptions',
        verbose_name="Ligne d'achat",
    )
    lot = models.ForeignKey(
        'stock.LotStock',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='lignes_reception',
        verbose_name='Lot généré / alimenté',
    )
    quantite_recue = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Quantité reçue',
    )
    numero_lot = models.CharField(max_length=80, verbose_name='Numéro de lot')
    date_peremption = models.DateField(verbose_name='Date de péremption')

    class Meta:
        verbose_name = 'Ligne de réception'
        verbose_name_plural = 'Lignes de réception'

    def __str__(self):
        return f"{self.ligne_achat.medicament.nom_commercial} — Lot {self.numero_lot} ({self.quantite_recue})"