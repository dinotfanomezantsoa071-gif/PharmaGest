from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initialise les 5 rôles PharmaGest et leurs permissions Django."

    ROLES_PERMISSIONS = {
        'Administrateur': '__all__',
        'Pharmacien responsable': [
            'view_utilisateur', 'view_journalaudit',
            'add_categorie', 'change_categorie', 'view_categorie',
            'add_medicament', 'change_medicament', 'view_medicament',
            'view_fournisseur', 'view_client',
            'view_commandeachat', 'change_commandeachat', 'view_receptionachat',
            'add_lotstock', 'change_lotstock', 'view_lotstock', 'add_mouvementstock', 'view_mouvementstock',
            'add_vente', 'change_vente', 'view_vente', 'add_paiement', 'view_paiement',
            'add_retourvente', 'view_retourvente',
        ],
        'Gestionnaire de stock': [
            'view_categorie', 'add_medicament', 'view_medicament',
            'add_fournisseur', 'change_fournisseur', 'view_fournisseur',
            'add_commandeachat', 'change_commandeachat', 'view_commandeachat',
            'add_receptionachat', 'change_receptionachat', 'view_receptionachat',
            'add_lotstock', 'change_lotstock', 'view_lotstock',
            'add_mouvementstock', 'view_mouvementstock',
        ],
        'Caissier': [
            'view_medicament', 'view_lotstock',
            'add_client', 'change_client', 'view_client',
            'add_vente', 'view_vente',
            'add_paiement', 'view_paiement',
            'add_retourvente', 'view_retourvente',
        ],
        'Responsable de gestion': [
            'view_medicament', 'view_categorie', 'view_fournisseur', 'view_client',
            'view_commandeachat', 'view_receptionachat',
            'view_lotstock', 'view_mouvementstock',
            'view_vente', 'view_paiement', 'view_retourvente',
        ],
    }

    def handle(self, *args, **options):
        for role_name, perm_codes in self.ROLES_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=role_name)
            if perm_codes == '__all__':
                group.permissions.set(Permission.objects.all())
            else:
                perms = Permission.objects.filter(codename__in=perm_codes)
                group.permissions.set(perms)
            self.stdout.write(self.style.SUCCESS(f"Rôle configuré : {role_name}"))