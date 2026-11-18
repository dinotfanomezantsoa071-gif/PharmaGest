from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Vente(models.Model):
    STATUT_BROUILLON = 'BROUILLON'
    STATUT_VALIDEE = 'VALIDEE'
    STATUT_RETOUR_PARTIEL = 'RETOUR_PARTIEL'
    STATUT_ANNULEE = 'ANNULEE'

    STATUT_CHOICES = [
        (STATUT_BROUILLON, 'Brouillon'),
        (STATUT_VALIDEE, 'Validée'),
        (STATUT_RETOUR_PARTIEL, 'Retour partiel'),
        (STATUT_ANNULEE, 'Annulée'),
    ]

    numero = models.CharField(max_length=50, unique=True, verbose_name='Numéro de vente')
    jeton_idempotence = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Jeton d'idempotence",
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes',
        verbose_name='Client',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ventes',
        verbose_name='Caissier / Vendeur',
    )
    date_vente = models.DateTimeField(auto_now_add=True, verbose_name='Date de vente')
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
    montant_paye = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Montant payé',
    )
    notes = models.TextField(blank=True, verbose_name='Notes')

    class Meta:
        verbose_name = 'Vente'
        verbose_name_plural = 'Ventes'
        ordering = ['-date_vente']

    def __str__(self):
        return f"{self.numero} — {self.montant_total} Ar"


class LigneVente(models.Model):
    vente = models.ForeignKey(
        Vente,
        on_delete=models.PROTECT,
        related_name='lignes',
        verbose_name='Vente',
    )
    medicament = models.ForeignKey(
        'medicaments.Medicament',
        on_delete=models.PROTECT,
        related_name='lignes_vente',
        verbose_name='Médicament',
    )
    lot = models.ForeignKey(
        'stock.LotStock',
        on_delete=models.PROTECT,
        related_name='lignes_vente',
        verbose_name='Lot délivré',
    )
    quantite = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Quantité',
    )
    prix_unitaire_applique = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Prix unitaire appliqué',
    )
    sous_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Sous-total',
    )

    class Meta:
        verbose_name = 'Ligne de vente'
        verbose_name_plural = 'Lignes de vente'

    def save(self, *args, **kwargs):
        self.sous_total = Decimal(self.quantite) * self.prix_unitaire_applique
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicament.nom_commercial} x {self.quantite}"


class Paiement(models.Model):
    MODE_ESPECES = 'ESPECES'
    MODE_MOBILE_MONEY = 'MOBILE_MONEY'
    MODE_CARTE = 'CARTE'
    MODE_AUTRE = 'AUTRE'

    MODE_CHOICES = [
        (MODE_ESPECES, 'Espèces'),
        (MODE_MOBILE_MONEY, 'Mobile Money (MVola / Orange / Airtel)'),
        (MODE_CARTE, 'Carte bancaire'),
        (MODE_AUTRE, 'Autre'),
    ]

    STATUT_EN_ATTENTE = 'EN_ATTENTE'
    STATUT_CONFIRME = 'CONFIRME'
    STATUT_ECHOUE = 'ECHOUE'
    STATUT_REMBOURSE = 'REMBOURSE'

    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_CONFIRME, 'Confirmé'),
        (STATUT_ECHOUE, 'Échoué'),
        (STATUT_REMBOURSE, 'Remboursé'),
    ]

    vente = models.ForeignKey(
        Vente,
        on_delete=models.PROTECT,
        related_name='paiements',
        verbose_name='Vente',
    )
    mode_paiement = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default=MODE_ESPECES,
        verbose_name='Mode de paiement',
    )
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Montant',
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_CONFIRME,
        verbose_name='Statut',
    )
    reference_transaction = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Référence transaction',
    )
    date_paiement = models.DateTimeField(auto_now_add=True, verbose_name='Date de paiement')
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='paiements_enregistres',
        verbose_name='Enregistré par',
    )

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date_paiement']

    def __str__(self):
        return f"{self.get_mode_paiement_display()} — {self.montant} Ar ({self.get_statut_display()})"


class RetourVente(models.Model):
    numero = models.CharField(max_length=50, unique=True, verbose_name='Numéro de retour')
    vente = models.ForeignKey(
        Vente,
        on_delete=models.PROTECT,
        related_name='retours',
        verbose_name="Vente d'origine",
    )
    ligne_vente = models.ForeignKey(
        LigneVente,
        on_delete=models.PROTECT,
        related_name='retours',
        verbose_name='Ligne retournée',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='retours_enregistres',
        verbose_name='Responsable',
    )
    quantite_retournee = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Quantité retournée',
    )
    motif = models.TextField(verbose_name='Motif du retour')
    reintegrer_stock = models.BooleanField(default=False, verbose_name='Réintégrer au stock')
    montant_rembourse = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Montant remboursé',
    )
    date_retour = models.DateTimeField(auto_now_add=True, verbose_name='Date du retour')

    class Meta:
        verbose_name = 'Retour de vente'
        verbose_name_plural = 'Retours de vente'
        ordering = ['-date_retour']

    def __str__(self):
        return f"{self.numero} — {self.ligne_vente.medicament.nom_commercial}"