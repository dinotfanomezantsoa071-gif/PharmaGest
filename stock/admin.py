from django.contrib import admin
from .models import LotStock, MouvementStock


@admin.register(LotStock)
class LotStockAdmin(admin.ModelAdmin):
    list_display = ('numero_lot', 'medicament', 'date_peremption', 'quantite_disponible', 'bloque')
    list_filter = ('bloque', 'date_peremption')
    search_fields = ('numero_lot', 'medicament__nom_commercial')


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ('date_mouvement', 'type_mouvement', 'medicament', 'lot', 'quantite', 'stock_apres', 'utilisateur')
    list_filter = ('type_mouvement',)
    search_fields = ('reference_document', 'lot__numero_lot', 'medicament__nom_commercial')