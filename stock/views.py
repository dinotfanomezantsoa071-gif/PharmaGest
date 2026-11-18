from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from medicaments.models import Medicament
from utilisateurs.utils import enregistrer_audit
from .models import LotStock, MouvementStock


@login_required
@permission_required('stock.view_lotstock', raise_exception=True)
def stock_list(request):
    q = request.GET.get('q', '').strip()
    filtre = request.GET.get('filtre', 'TOUS').strip()
    aujourd_hui = timezone.localdate()
    limite_proche = aujourd_hui + timedelta(days=30)

    lots = LotStock.objects.select_related('medicament', 'medicament__categorie').all()

    if q:
        lots = lots.filter(
            Q(numero_lot__icontains=q) |
            Q(medicament__nom_commercial__icontains=q) |
            Q(medicament__code_barres__icontains=q)
        )

    if filtre == 'DISPONIBLES':
        lots = lots.filter(bloque=False, date_peremption__gte=aujourd_hui, quantite_disponible__gt=0)
    elif filtre == 'PROCHES':
        lots = lots.filter(
            bloque=False,
            date_peremption__gte=aujourd_hui,
            date_peremption__lte=limite_proche,
            quantite_disponible__gt=0,
        )
    elif filtre == 'PERIMES':
        lots = lots.filter(date_peremption__lt=aujourd_hui, quantite_disponible__gt=0)
    elif filtre == 'BLOQUES':
        lots = lots.filter(bloque=True)

    # Indicateurs globaux
    lots_perimes_count = LotStock.objects.filter(date_peremption__lt=aujourd_hui, quantite_disponible__gt=0).count()
    lots_proches_count = LotStock.objects.filter(
        bloque=False,
        date_peremption__gte=aujourd_hui,
        date_peremption__lte=limite_proche,
        quantite_disponible__gt=0,
    ).count()
    meds_actifs = Medicament.objects.filter(statut=Medicament.STATUT_ACTIF)
    stocks_faibles_count = sum(1 for m in meds_actifs if m.est_en_stock_faible)

    paginator = Paginator(lots, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'stock/liste.html', {
        'page_obj': page_obj,
        'q': q,
        'filtre': filtre,
        'aujourd_hui': aujourd_hui,
        'limite_proche': limite_proche,
        'lots_perimes_count': lots_perimes_count,
        'lots_proches_count': lots_proches_count,
        'stocks_faibles_count': stocks_faibles_count,
    })


@login_required
@permission_required('stock.view_mouvementstock', raise_exception=True)
def mouvement_list(request):
    type_mvt = request.GET.get('type', '').strip()
    q = request.GET.get('q', '').strip()

    mouvements = MouvementStock.objects.select_related('medicament', 'lot', 'utilisateur').all()
    if type_mvt:
        mouvements = mouvements.filter(type_mouvement=type_mvt)
    if q:
        mouvements = mouvements.filter(
            Q(medicament__nom_commercial__icontains=q) |
            Q(lot__numero_lot__icontains=q) |
            Q(reference_document__icontains=q)
        )

    paginator = Paginator(mouvements, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'stock/mouvements.html', {
        'page_obj': page_obj,
        'type_mvt': type_mvt,
        'q': q,
        'types': MouvementStock.TYPE_CHOICES,
    })


@login_required
@permission_required('stock.change_lotstock', raise_exception=True)
def lot_toggle_bloque(request, pk):
    lot = get_object_or_404(LotStock, pk=pk)
    if request.method == 'POST':
        lot.bloque = not lot.bloque
        lot.save(update_fields=['bloque'])
        etat = 'bloqué' if lot.bloque else 'débloqué'
        enregistrer_audit(request, 'STATUT_LOT', 'LotStock', lot.pk, f"Lot {lot.numero_lot} {etat}")
        messages.info(request, f"Le lot {lot.numero_lot} a été {etat}.")
    return redirect('stock:stock_list')


@login_required
@permission_required('stock.change_lotstock', raise_exception=True)
def inventaire_ajustement(request, pk):
    lot = get_object_or_404(LotStock.objects.select_related('medicament'), pk=pk)

    if request.method == 'POST':
        try:
            nouvelle_qte = int(request.POST.get('nouvelle_quantite', ''))
        except ValueError:
            messages.error(request, "Veuillez saisir un entier valide.")
            return redirect('stock:inventaire_ajustement', pk=lot.pk)

        motif = request.POST.get('motif', '').strip()
        if nouvelle_qte < 0:
            messages.error(request, "Le stock ne peut pas être négatif.")
            return redirect('stock:inventaire_ajustement', pk=lot.pk)
        if not motif:
            messages.error(request, "Un motif d'inventaire est obligatoire.")
            return redirect('stock:inventaire_ajustement', pk=lot.pk)

        with transaction.atomic():
            lot_locked = LotStock.objects.select_for_update().get(pk=lot.pk)
            avant = lot_locked.quantite_disponible
            diff = nouvelle_qte - avant
            if diff == 0:
                messages.info(request, "Aucune variation de quantité constatée.")
                return redirect('stock:stock_list')

            lot_locked.quantite_disponible = nouvelle_qte
            lot_locked.save(update_fields=['quantite_disponible'])

            MouvementStock.objects.create(
                medicament=lot_locked.medicament,
                lot=lot_locked,
                utilisateur=request.user,
                type_mouvement=MouvementStock.TYPE_AJUSTEMENT,
                quantite=diff,
                stock_avant=avant,
                stock_apres=nouvelle_qte,
                reference_document='INVENTAIRE',
                motif=motif,
            )
            enregistrer_audit(
                request,
                'AJUSTEMENT_INVENTAIRE',
                'LotStock',
                lot_locked.pk,
                f"Lot {lot_locked.numero_lot}: {avant} -> {nouvelle_qte} ({motif})",
            )

        messages.success(request, f"Inventaire enregistré pour le lot {lot.numero_lot}.")
        return redirect('stock:stock_list')

    return render(request, 'stock/ajustement.html', {'lot': lot})