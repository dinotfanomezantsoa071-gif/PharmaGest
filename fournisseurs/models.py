from django.db import models


class Fournisseur(models.Model):
    raison_sociale = models.CharField(max_length=180, verbose_name='Raison sociale')
    adresse = models.TextField(blank=True, verbose_name='Adresse')
    telephone = models.CharField(max_length=30, verbose_name='Téléphone')
    email = models.EmailField(blank=True, verbose_name='Adresse e-mail')
    numero_fiscal = models.CharField(
        max_length=80,
        blank=True,
        verbose_name='Numéro fiscal (NIF / STAT)',
    )
    contact_principal = models.CharField(max_length=120, blank=True, verbose_name='Contact principal')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')

    class Meta:
        verbose_name = 'Fournisseur'
        verbose_name_plural = 'Fournisseurs'
        ordering = ['raison_sociale']

    def __str__(self):
        return self.raison_sociale