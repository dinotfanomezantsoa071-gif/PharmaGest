from django.contrib import admin
from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 1


@admin.register(CommandeAchat)
class CommandeAchatAdmin(admin.ModelAdmin):
    list_display = ('numero', 'fournisseur', 'date_commande', 'statut', 'montant_total', 'utilisateur')
    list_filter = ('statut', 'fournisseur')
    search_fields = ('numero', 'fournisseur__raison_sociale')
    inlines = [LigneAchatInline]


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(admin.ModelAdmin):
    list_display = ('numero', 'commande', 'date_reception', 'validee', 'utilisateur')
    list_filter = ('validee',)


admin.site.register(LigneReception)