from django.contrib import admin
from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ('raison_sociale', 'telephone', 'email', 'numero_fiscal', 'actif')
    list_filter = ('actif',)
    search_fields = ('raison_sociale', 'telephone', 'numero_fiscal')