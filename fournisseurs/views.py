from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from utilisateurs.utils import enregistrer_audit
from .forms import FournisseurForm
from .models import Fournisseur


@login_required
@permission_required('fournisseurs.view_fournisseur', raise_exception=True)
def fournisseur_list(request):
    q = request.GET.get('q', '').strip()
    statut = request.GET.get('statut', 'ACTIFS').strip()

    fournisseurs = Fournisseur.objects.all()
    if q:
        fournisseurs = fournisseurs.filter(Q(raison_sociale__icontains=q) | Q(telephone__icontains=q))
    if statut == 'ACTIFS':
        fournisseurs = fournisseurs.filter(actif=True)
    elif statut == 'INACTIFS':
        fournisseurs = fournisseurs.filter(actif=False)

    paginator = Paginator(fournisseurs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'fournisseurs/liste.html', {'page_obj': page_obj, 'q': q, 'statut': statut})


@login_required
@permission_required('fournisseurs.view_fournisseur', raise_exception=True)
def fournisseur_detail(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    commandes = fournisseur.commandes.all().order_by('-date_commande')
    total_achats = commandes.aggregate(total=Sum('montant_total'))['total'] or 0
    return render(request, 'fournisseurs/detail.html', {
        'fournisseur': fournisseur,
        'commandes': commandes,
        'total_achats': total_achats,
    })


@login_required
@permission_required('fournisseurs.add_fournisseur', raise_exception=True)
def fournisseur_create(request):
    form = FournisseurForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        fournisseur = form.save()
        enregistrer_audit(request, 'CREATION_FOURNISSEUR', 'Fournisseur', fournisseur.pk, fournisseur.raison_sociale)
        messages.success(request, f"Le fournisseur « {fournisseur.raison_sociale} » a été ajouté.")
        return redirect('fournisseurs:fournisseur_list')
    return render(request, 'fournisseurs/form.html', {'form': form, 'titre': 'Nouveau fournisseur'})


@login_required
@permission_required('fournisseurs.change_fournisseur', raise_exception=True)
def fournisseur_update(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    form = FournisseurForm(request.POST or None, instance=fournisseur)
    if request.method == 'POST' and form.is_valid():
        fournisseur = form.save()
        enregistrer_audit(request, 'MODIFICATION_FOURNISSEUR', 'Fournisseur', fournisseur.pk, fournisseur.raison_sociale)
        messages.success(request, f"Le fournisseur « {fournisseur.raison_sociale} » a été mis à jour.")
        return redirect('fournisseurs:fournisseur_detail', pk=fournisseur.pk)
    return render(request, 'fournisseurs/form.html', {'form': form, 'titre': f'Modifier : {fournisseur.raison_sociale}'})


@login_required
@permission_required('fournisseurs.change_fournisseur', raise_exception=True)
def fournisseur_toggle_actif(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    if request.method == 'POST':
        fournisseur.actif = not fournisseur.actif
        fournisseur.save(update_fields=['actif'])
        etat = 'activé' if fournisseur.actif else 'désactivé'
        enregistrer_audit(request, 'STATUT_FOURNISSEUR', 'Fournisseur', fournisseur.pk, f"{fournisseur.raison_sociale} {etat}")
        messages.info(request, f"Le fournisseur « {fournisseur.raison_sociale} » a été {etat}.")
    return redirect('fournisseurs:fournisseur_list')