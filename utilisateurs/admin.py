from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import JournalAudit, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations PharmaGest', {'fields': ('role', 'telephone')}),
    )


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ('date_action', 'utilisateur', 'action', 'modele_cible', 'objet_id')
    list_filter = ('modele_cible', 'action')
    search_fields = ('utilisateur__username', 'details', 'objet_id')
    readonly_fields = ('utilisateur', 'action', 'modele_cible', 'objet_id', 'details', 'adresse_ip', 'date_action')