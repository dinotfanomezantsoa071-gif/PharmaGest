import json
import uuid
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from clients.models import Client
from stock.models import LotStock, MouvementStock
from utilisateurs.utils import enregistrer_audit
from .models import LigneVente, Paiement, RetourVente, Vente


def _generer_numero_vente(prefixe):
    return f"{prefixe}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"


@login_required
@permission_required('ventes.view_vente', raise_exception=True)
def vente_list(request):
    q = request.GET.get('q', '').strip()
    statut = request.GET.get('statut', '').strip()

    ventes = Vente.objects.select_related('client', 'utilisateur').all()
    if q:
        ventes = ventes.filter(Q(numero__icontains=q) | Q(client__nom__icontains=q))
    if statut:
        ventes = ventes.filter(statut=statut)

    paginator = Paginator(ventes, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'ventes/liste.html', {
        'page_obj': page_obj,
        'q': q,
        'statut': statut,
        'statuts': Vente.STATUT_CHOICES,
    })


@login_required
@permission_required('ventes.add_vente', raise_exception=True)
def caisse_view(request):
    aujourd_hui = timezone.localdate()
    # Lots délivrables triés par ordre FEFO (péremption la plus proche en premier)
    lots_disponibles = LotStock.objects.select_related('medicament', 'medicament__categorie').filter(
        medicament__statut='ACTIF',
        bloque=False,
        date_peremption__gte=aujourd_hui,
        quantite_disponible__gt=0,
    ).order_by('date_peremption', 'id')

    clients = Client.objects.filter(actif=True)

    if request.method == 'POST':
        panier_json = request.POST.get('panier_json', '[]')
        client_id = request.POST.get('client_id') or None
        mode_paiement = request.POST.get('mode_paiement', Paiement.MODE_ESPECES)
        reference_tx = request.POST.get('reference_transaction', '').strip()
        notes = request.POST.get('notes', '').strip()
        try:
            idempotency_token = uuid.UUID(request.POST.get('jeton_vente', ''))
        except (ValueError, AttributeError):
            messages.error(request, "Le jeton de vente est invalide. Rechargez la caisse avant de réessayer.")
            return redirect('ventes:caisse')

        try:
            items = json.loads(panier_json)
        except json.JSONDecodeError:
            messages.error(request, "Données du panier invalides.")
            return redirect('ventes:caisse')

        if not items:
            messages.error(request, "Le panier est vide.")
            return redirect('ventes:caisse')

        if mode_paiement == Paiement.MODE_MOBILE_MONEY:
            messages.error(
                request,
                "Le paiement Mobile Money n'est pas activé : aucune vérification automatique du prestataire n'est configurée.",
            )
            return redirect('ventes:caisse')

        existing_sale = Vente.objects.filter(jeton_idempotence=idempotency_token).first()
        if existing_sale:
            messages.info(request, f"La vente {existing_sale.numero} a déjà été enregistrée.")
            return redirect('ventes:vente_detail', pk=existing_sale.pk)

        client = get_object_or_404(Client, pk=client_id, actif=True) if client_id else None

        try:
            with transaction.atomic():
                vente = Vente.objects.create(
                    numero=_generer_numero_vente('VNT'),
                    jeton_idempotence=idempotency_token,
                    client=client,
                    utilisateur=request.user,
                    statut=Vente.STATUT_VALIDEE,
                    notes=notes,
                )
                total = Decimal('0.00')

                for item in items:
                    lot_id = int(item.get('lot_id', 0))
                    qte = int(item.get('quantite', 0))
                    if qte <= 0:
                        raise ValueError("La quantité doit être strictement positive.")

                    lot = LotStock.objects.select_for_update().select_related('medicament').get(pk=lot_id)

                    if lot.bloque or lot.date_peremption < aujourd_hui:
                        raise ValueError(f"Le lot {lot.numero_lot} ({lot.medicament.nom_commercial}) est périmé ou bloqué.")
                    if lot.quantite_disponible < qte:
                        raise ValueError(
                            f"Stock insuffisant pour {lot.medicament.nom_commercial} (Lot {lot.numero_lot} : {lot.quantite_disponible} disponible)."
                        )

                    prix_applique = lot.medicament.prix_vente
                    ligne = LigneVente.objects.create(
                        vente=vente,
                        medicament=lot.medicament,
                        lot=lot,
                        quantite=qte,
                        prix_unitaire_applique=prix_applique,
                    )
                    total += ligne.sous_total

                    avant = lot.quantite_disponible
                    lot.quantite_disponible = avant - qte
                    lot.save(update_fields=['quantite_disponible'])

                    MouvementStock.objects.create(
                        medicament=lot.medicament,
                        lot=lot,
                        utilisateur=request.user,
                        type_mouvement=MouvementStock.TYPE_SORTIE,
                        quantite=-qte,
                        stock_avant=avant,
                        stock_apres=lot.quantite_disponible,
                        reference_document=vente.numero,
                        motif="Vente comptoir",
                    )

                vente.montant_total = total
                vente.montant_paye = total
                vente.save(update_fields=['montant_total', 'montant_paye'])

                Paiement.objects.create(
                    vente=vente,
                    mode_paiement=mode_paiement,
                    montant=total,
                    statut=Paiement.STATUT_CONFIRME,
                    reference_transaction=reference_tx,
                    utilisateur=request.user,
                )

                enregistrer_audit(request, 'VALIDATION_VENTE', 'Vente', vente.pk, f"{vente.numero} — {total} Ar")

            messages.success(request, f"Vente {vente.numero} validée avec succès ({total:.0f} Ar).")
            return redirect('ventes:vente_detail', pk=vente.pk)

        except IntegrityError:
            existing_sale = Vente.objects.filter(jeton_idempotence=idempotency_token).first()
            if existing_sale is None:
                raise
            messages.info(request, f"La vente {existing_sale.numero} a déjà été enregistrée.")
            return redirect('ventes:vente_detail', pk=existing_sale.pk)
        except (ValueError, LotStock.DoesNotExist) as e:
            messages.error(request, str(e))
            return redirect('ventes:caisse')

    return render(request, 'ventes/caisse.html', {
        'lots': lots_disponibles,
        'clients': clients,
        'modes_paiement': Paiement.MODE_CHOICES,
        'jeton_vente': uuid.uuid4(),
    })


@login_required
@permission_required('ventes.view_vente', raise_exception=True)
def vente_detail(request, pk):
    vente = get_object_or_404(Vente.objects.select_related('client', 'utilisateur'), pk=pk)
    lignes = vente.lignes.select_related('medicament', 'lot').all()
    paiements = vente.paiements.all()
    retours = vente.retours.select_related('ligne_vente__medicament', 'utilisateur').all()
    return render(request, 'ventes/detail.html', {
        'vente': vente,
        'lignes': lignes,
        'paiements': paiements,
        'retours': retours,
    })


@login_required
@permission_required('ventes.add_retourvente', raise_exception=True)
def retour_create(request, ligne_pk):
    ligne = get_object_or_404(
        LigneVente.objects.select_related('vente', 'medicament', 'lot'),
        pk=ligne_pk,
    )
    if request.method == 'POST':
        try:
            qte = int(request.POST.get('quantite_retournee', 0))
        except ValueError:
            qte = 0
        motif = request.POST.get('motif', '').strip()
        reintegrer = request.POST.get('reintegrer_stock') == 'on'

        if qte <= 0:
            messages.error(request, "La quantité retournée doit être supérieure à zéro.")
            return redirect('ventes:retour_create', ligne_pk=ligne.pk)
        if not motif:
            messages.error(request, "Le motif du retour est obligatoire.")
            return redirect('ventes:retour_create', ligne_pk=ligne.pk)

        try:
            with transaction.atomic():
                vente = Vente.objects.select_for_update().get(pk=ligne.vente_id)
                ligne = LigneVente.objects.select_for_update().select_related('medicament', 'lot').get(pk=ligne.pk)
                deja_retourne = ligne.retours.aggregate(total=Sum('quantite_retournee'))['total'] or 0
                max_retournable = ligne.quantite - deja_retourne
                if qte > max_retournable:
                    raise ValueError(
                        f"La quantité retournée doit être comprise entre 1 et {max_retournable}."
                        if max_retournable > 0 else "Toute la quantité de cette ligne a déjà été retournée."
                    )

                lot = LotStock.objects.select_for_update().get(pk=ligne.lot_id)
                if reintegrer and lot.est_perime:
                    raise ValueError("Impossible de réintégrer en stock un lot désormais périmé.")

                montant_rembourse = Decimal(qte) * ligne.prix_unitaire_applique
                retour = RetourVente.objects.create(
                    numero=_generer_numero_vente('RET'),
                    vente=vente,
                    ligne_vente=ligne,
                    utilisateur=request.user,
                    quantite_retournee=qte,
                    motif=motif,
                    reintegrer_stock=reintegrer,
                    montant_rembourse=montant_rembourse,
                )

                if reintegrer:
                    avant = lot.quantite_disponible
                    lot.quantite_disponible = avant + qte
                    lot.save(update_fields=['quantite_disponible'])

                    MouvementStock.objects.create(
                        medicament=ligne.medicament,
                        lot=lot,
                        utilisateur=request.user,
                        type_mouvement=MouvementStock.TYPE_RETOUR,
                        quantite=qte,
                        stock_avant=avant,
                        stock_apres=lot.quantite_disponible,
                        reference_document=retour.numero,
                        motif=f"Retour sur vente {vente.numero}",
                    )

                total_vendu = sum(l.quantite for l in vente.lignes.all())
                total_retourne = RetourVente.objects.filter(vente=vente).aggregate(t=Sum('quantite_retournee'))['t'] or 0
                vente.statut = Vente.STATUT_ANNULEE if total_retourne >= total_vendu else Vente.STATUT_RETOUR_PARTIEL
                vente.save(update_fields=['statut'])

                enregistrer_audit(request, 'RETOUR_VENTE', 'RetourVente', retour.pk, f"{retour.numero} — {motif}")
        except ValueError as error:
            messages.error(request, str(error))
            return redirect('ventes:retour_create', ligne_pk=ligne.pk)

        messages.success(request, f"Retour {retour.numero} enregistré ({montant_rembourse:.0f} Ar).")
        return redirect('ventes:vente_detail', pk=ligne.vente.pk)

    deja_retourne = ligne.retours.aggregate(total=Sum('quantite_retournee'))['total'] or 0
    max_retournable = ligne.quantite - deja_retourne
    if max_retournable <= 0:
        messages.warning(request, "Toute la quantité de cette ligne a déjà été retournée.")
        return redirect('ventes:vente_detail', pk=ligne.vente.pk)

    return render(request, 'ventes/retour_form.html', {
        'ligne': ligne,
        'max_retournable': max_retournable,
    })