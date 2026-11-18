from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class LotStock(models.Model):
    medicament = models.ForeignKey(
        'medicaments.Medicament',
        on_delete=models.PROTECT,
        related_name='lots',
        verbose_name='Médicament',
    )
    numero_lot = models.CharField(max_length=80, verbose_name='Numéro de lot')
    date_peremption = models.DateField(verbose_name='Date de péremption')
    quantite_initiale = models.PositiveIntegerField(verbose_name='Quantité initiale')
    quantite_disponible = models.PositiveIntegerField(verbose_name='Quantité disponible')
    bloque = models.BooleanField(default=False, verbose_name='Lot bloqué')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date d'entrée")

    class Meta:
        verbose_name = 'Lot de stock'
        verbose_name_plural = 'Lots de stock'
        ordering = ['date_peremption', 'id']  # Ordre FEFO par défaut
        unique_together = ('medicament', 'numero_lot')
        constraints = [
            models.CheckConstraint(
                condition=Q(quantite_disponible__gte=0),
                name='lot_quantite_disponible_gte_0',
            )
        ]

    def __str__(self):
        return f"Lot {self.numero_lot} — {self.medicament.nom_commercial} (Exp: {self.date_peremption})"

    @property
    def est_perime(self):
        return self.date_peremption < timezone.localdate()

    @property
    def est_delivrable(self):
        return not self.bloque and not self.est_perime and self.quantite_disponible > 0


class MouvementStock(models.Model):
    TYPE_ENTREE = 'ENTREE'
    TYPE_SORTIE = 'SORTIE'
    TYPE_RETOUR = 'RETOUR'
    TYPE_AJUSTEMENT = 'AJUSTEMENT'

    TYPE_CHOICES = [
        (TYPE_ENTREE, 'Entrée (Réception)'),
        (TYPE_SORTIE, 'Sortie (Vente)'),
        (TYPE_RETOUR, 'Retour client'),
        (TYPE_AJUSTEMENT, "Ajustement d'inventaire"),
    ]

    medicament = models.ForeignKey(
        'medicaments.Medicament',
        on_delete=models.PROTECT,
        related_name='mouvements',
        verbose_name='Médicament',
    )
    lot = models.ForeignKey(
        LotStock,
        on_delete=models.PROTECT,
        related_name='mouvements',
        verbose_name='Lot',
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='mouvements_stock',
        verbose_name='Utilisateur',
    )
    type_mouvement = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name='Type de mouvement',
    )
    quantite = models.IntegerField(verbose_name='Quantité (+/-)')
    stock_avant = models.PositiveIntegerField(verbose_name='Stock lot avant')
    stock_apres = models.PositiveIntegerField(verbose_name='Stock lot après')
    reference_document = models.CharField(max_length=80, blank=True, verbose_name='Référence document')
    motif = models.CharField(max_length=255, blank=True, verbose_name='Motif')
    date_mouvement = models.DateTimeField(auto_now_add=True, verbose_name='Date du mouvement')

    class Meta:
        verbose_name = 'Mouvement de stock'
        verbose_name_plural = 'Mouvements de stock'
        ordering = ['-date_mouvement']

    def __str__(self):
        return f"{self.get_type_mouvement_display()} | {self.lot.numero_lot} ({self.quantite:+d})"