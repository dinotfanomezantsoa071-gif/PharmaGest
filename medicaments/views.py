from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q, ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from utilisateurs.utils import enregistrer_audit
from .forms import CategorieForm, MedicamentForm
from .models import Categorie, Medicament


# --- CATEGORIES ---

@login_required
@permission_required('medicaments.view_categorie', raise_exception=True)
def categorie_list(request):
    q = request.GET.get('q', '').strip()
    categories = Categorie.objects.all()
    if q:
        categories = categories.filter(Q(nom__icontains=q) | Q(description__icontains=q))
    paginator = Paginator(categories, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'categories/liste.html', {'page_obj': page_obj, 'q': q})


@login_required
@permission_required('medicaments.add_categorie', raise_exception=True)
def categorie_create(request):
    form = CategorieForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        categorie = form.save()
        enregistrer_audit(request, 'CREATION_CATEGORIE', 'Categorie', categorie.pk, f"Catégorie : {categorie.nom}")
        messages.success(request, f"La catégorie « {categorie.nom} » a été créée.")
        return redirect('medicaments:categorie_list')
    return render(request, 'categories/form.html', {'form': form, 'titre': 'Nouvelle catégorie'})


@login_required
@permission_required('medicaments.change_categorie', raise_exception=True)
def categorie_update(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    form = CategorieForm(request.POST or None, instance=categorie)
    if request.method == 'POST' and form.is_valid():
        categorie = form.save()
        enregistrer_audit(request, 'MODIFICATION_CATEGORIE', 'Categorie', categorie.pk, f"Catégorie : {categorie.nom}")
        messages.success(request, f"La catégorie « {categorie.nom} » a été mise à jour.")
        return redirect('medicaments:categorie_list')
    return render(request, 'categories/form.html', {'form': form, 'titre': f'Modifier : {categorie.nom}'})


@login_required
@permission_required('medicaments.delete_categorie', raise_exception=True)
def categorie_delete(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == 'POST':
        try:
            nom = categorie.nom
            categorie.delete()
            enregistrer_audit(request, 'SUPPRESSION_CATEGORIE', 'Categorie', pk, f"Catégorie supprimée : {nom}")
            messages.success(request, f"La catégorie « {nom} » a été supprimée.")
        except ProtectedError:
            messages.error(request, f"Impossible de supprimer « {categorie.nom} » : des médicaments y sont rattachés.")
    return redirect('medicaments:categorie_list')


# --- MEDICAMENTS ---

@login_required
@permission_required('medicaments.view_medicament', raise_exception=True)
def medicament_list(request):
    q = request.GET.get('q', '').strip()
    categorie_id = request.GET.get('categorie', '').strip()
    statut = request.GET.get('statut', 'ACTIF').strip()

    medicaments = Medicament.objects.select_related('categorie').all()
    if q:
        medicaments = medicaments.filter(
            Q(nom_commercial__icontains=q) |
            Q(denomination_generique__icontains=q) |
            Q(code_barres__icontains=q)
        )
    if categorie_id:
        medicaments = medicaments.filter(categorie_id=categorie_id)
    if statut in [Medicament.STATUT_ACTIF, Medicament.STATUT_ARCHIVE]:
        medicaments = medicaments.filter(statut=statut)

    paginator = Paginator(medicaments, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    categories = Categorie.objects.all()

    return render(request, 'medicaments/liste.html', {
        'page_obj': page_obj,
        'categories': categories,
        'q': q,
        'categorie_id': categorie_id,
        'statut': statut,
    })


@login_required
@permission_required('medicaments.view_medicament', raise_exception=True)
def medicament_detail(request, pk):
    medicament = get_object_or_404(Medicament.objects.select_related('categorie'), pk=pk)
    lots = medicament.lots.all().order_by('date_peremption')
    return render(request, 'medicaments/detail.html', {'medicament': medicament, 'lots': lots})


@login_required
@permission_required('medicaments.add_medicament', raise_exception=True)
def medicament_create(request):
    form = MedicamentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        med = form.save()
        enregistrer_audit(request, 'CREATION_MEDICAMENT', 'Medicament', med.pk, f"Médicament : {med.nom_commercial}")
        messages.success(request, f"Le médicament « {med.nom_commercial} » a été ajouté.")
        return redirect('medicaments:medicament_list')
    return render(request, 'medicaments/form.html', {'form': form, 'titre': 'Nouveau médicament'})


@login_required
@permission_required('medicaments.change_medicament', raise_exception=True)
def medicament_update(request, pk):
    med = get_object_or_404(Medicament, pk=pk)
    form = MedicamentForm(request.POST or None, request.FILES or None, instance=med)
    if request.method == 'POST' and form.is_valid():
        med = form.save()
        enregistrer_audit(request, 'MODIFICATION_MEDICAMENT', 'Medicament', med.pk, f"Médicament : {med.nom_commercial}")
        messages.success(request, f"Le médicament « {med.nom_commercial} » a été mis à jour.")
        return redirect('medicaments:medicament_detail', pk=med.pk)
    return render(request, 'medicaments/form.html', {'form': form, 'titre': f'Modifier : {med.nom_commercial}', 'medicament': med})


@login_required
@permission_required('medicaments.delete_medicament', raise_exception=True)
def medicament_archive_or_delete(request, pk):
    med = get_object_or_404(Medicament, pk=pk)
    if request.method == 'POST':
        a_historique = med.lots.exists() or med.lignes_achat.exists() or med.lignes_vente.exists()
        if a_historique:
            med.statut = Medicament.STATUT_ARCHIVE
            med.save(update_fields=['statut'])
            enregistrer_audit(request, 'ARCHIVAGE_MEDICAMENT', 'Medicament', med.pk, f"Archivé (historique protégé) : {med.nom_commercial}")
            messages.warning(request, f"« {med.nom_commercial} » possède un historique et a été archivé.")
        else:
            nom = med.nom_commercial
            med.delete()
            enregistrer_audit(request, 'SUPPRESSION_MEDICAMENT', 'Medicament', pk, f"Supprimé : {nom}")
            messages.success(request, f"Le médicament « {nom} » a été supprimé.")
    return redirect('medicaments:medicament_list')