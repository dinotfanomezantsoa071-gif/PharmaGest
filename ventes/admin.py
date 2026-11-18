from django.contrib import admin
from .models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ('numero', 'client', 'date_vente', 'statut', 'montant_total', 'montant_paye', 'utilisateur')
    list_filter = ('statut', 'date_vente')
    search_fields = ('numero', 'client__nom')
    inlines = [LigneVenteInline]


admin.site.register(Paiement)
admin.site.register(RetourVente)