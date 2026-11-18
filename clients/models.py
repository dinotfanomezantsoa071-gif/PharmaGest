from django.db import models


class Client(models.Model):
    nom = models.CharField(max_length=150, verbose_name='Nom complet')
    telephone = models.CharField(max_length=30, blank=True, verbose_name='Téléphone')
    email = models.EmailField(blank=True, verbose_name='Adresse e-mail')
    adresse = models.TextField(blank=True, verbose_name='Adresse')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name='Date de création')

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.telephone})" if self.telephone else self.nom