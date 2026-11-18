from django.contrib import admin
from .models import Categorie, Medicament


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'date_creation')
    search_fields = ('nom',)


@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = ('nom_commercial', 'categorie', 'dosage', 'forme_pharmaceutique', 'prix_vente', 'seuil_alerte', 'statut')
    list_filter = ('statut', 'categorie', 'forme_pharmaceutique')
    search_fields = ('nom_commercial', 'denomination_generique', 'code_barres', 'laboratoire')