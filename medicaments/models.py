from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Categorie(models.Model):
    nom = models.CharField(max_length=120, unique=True, verbose_name='Nom')
    description = models.TextField(blank=True, verbose_name='Description')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Medicament(models.Model):
    STATUT_ACTIF = 'ACTIF'
    STATUT_ARCHIVE = 'ARCHIVE'
    STATUT_CHOICES = [
        (STATUT_ACTIF, 'Actif'),
        (STATUT_ARCHIVE, 'Archivé'),
    ]

    nom_commercial = models.CharField(max_length=180, verbose_name='Nom commercial')
    denomination_generique = models.CharField(
        max_length=180,
        blank=True,
        verbose_name='Dénomination générique (DCI)',
    )
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,
        related_name='medicaments',
        verbose_name='Catégorie',
    )
    forme_pharmaceutique = models.CharField(max_length=80, verbose_name='Forme pharmaceutique')
    dosage = models.CharField(max_length=80, verbose_name='Dosage')
    laboratoire = models.CharField(max_length=150, blank=True, verbose_name='Laboratoire')
    code_barres = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Code-barres',
    )
    photo = models.ImageField(
        upload_to='medicaments/',
        null=True,
        blank=True,
        verbose_name='Photo',
    )
    prix_achat = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Prix d'achat",
    )
    prix_vente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Prix de vente',
    )
    seuil_alerte = models.PositiveIntegerField(default=10, verbose_name="Seuil d'alerte")
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_ACTIF,
        verbose_name='Statut',
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')
    date_modification = models.DateTimeField(auto_now=True, verbose_name='Dernière modification')

    class Meta:
        verbose_name = 'Médicament'
        verbose_name_plural = 'Médicaments'
        ordering = ['nom_commercial']

    def __str__(self):
        return f"{self.nom_commercial} ({self.dosage} — {self.forme_pharmaceutique})"

    @property
    def stock_disponible(self):
        aujourd_hui = timezone.localdate()
        total = self.lots.filter(
            bloque=False,
            date_peremption__gte=aujourd_hui,
            quantite_disponible__gt=0,
        ).aggregate(total=Sum('quantite_disponible'))['total']
        return total or 0

    @property
    def est_en_stock_faible(self):
        return self.stock_disponible <= self.seuil_alerte