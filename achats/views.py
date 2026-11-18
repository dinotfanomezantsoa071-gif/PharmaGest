from datetime import date
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from fournisseurs.models import Fournisseur
from medicaments.models import Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.utils import enregistrer_audit
from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


def _generer_numero(prefixe):
    horodatage = timezone.now().strftime('%Y%m%d%H%M%S')
    return f"{prefixe}-{horodatage}"


@login_required
@permission_required('achats.view_commandeachat', raise_exception=True)
def achat_list(request):
    statut = request.GET.get('statut', '').strip()
    commandes = CommandeAchat.objects.select_related('fournisseur', 'utilisateur').all()
    if statut:
        commandes = commandes.filter(statut=statut)

    paginator = Paginator(commandes, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'achats/liste.html', {
        'page_obj': page_obj,
        'statut': statut,
        'statuts': CommandeAchat.STATUT_CHOICES,
    })


@login_required
@permission_required('achats.add_commandeachat', raise_exception=True)
def achat_create(request):
    fournisseurs = Fournisseur.objects.filter(actif=True)
    medicaments = Medicament.objects.filter(statut=Medicament.STATUT_ACTIF)

    if request.method == 'POST':
        fournisseur_id = request.POST.get('fournisseur')
        notes = request.POST.get('notes', '').strip()
        med_ids = request.POST.getlist('medicament_id[]')
        quantites = request.POST.getlist('quantite[]')
        prix_list = request.POST.getlist('prix_achat[]')

        if not fournisseur_id or not med_ids:
            messages.error(request, "Sélectionnez un fournisseur et au moins un médicament.")
            return redirect('achats:achat_create')

        fournisseur = get_object_or_404(Fournisseur, pk=fournisseur_id, actif=True)

        with transaction.atomic():
            commande = CommandeAchat.objects.create(
                numero=_generer_numero('CMD'),
                fournisseur=fournisseur,
                utilisateur=request.user,
                statut=CommandeAchat.STATUT_BROUILLON,
                notes=notes,
            )
            total = Decimal('0.00')
            lignes_creees = 0

            for m_id, q_str, p_str in zip(med_ids, quantites, prix_list):
                if not m_id:
                    continue
                try:
                    qte = int(q_str)
                    prix = Decimal(p_str)
                except (ValueError, InvalidOperation):
                    continue
                if qte <= 0 or prix <= 0:
                    continue

                med = get_object_or_404(Medicament, pk=m_id)
                ligne = LigneAchat.objects.create(
                    commande=commande,
                    medicament=med,
                    quantite_commandee=qte,
                    prix_unitaire_achat=prix,
                )
                total += ligne.sous_total
                lignes_creees += 1

            if lignes_creees == 0:
                raise ValueError("Aucune ligne valide.")

            commande.montant_total = total
            commande.save(update_fields=['montant_total'])
            enregistrer_audit(request, 'CREATION_COMMANDE', 'CommandeAchat', commande.pk, commande.numero)

        messages.success(request, f"Commande {commande.numero} enregistrée en brouillon (stock inchangé).")
        return redirect('achats:achat_detail', pk=commande.pk)

    return render(request, 'achats/form.html', {
        'fournisseurs': fournisseurs,
        'medicaments': medicaments,
    })


@login_required
@permission_required('achats.view_commandeachat', raise_exception=True)
def achat_detail(request, pk):
    commande = get_object_or_404(
        CommandeAchat.objects.select_related('fournisseur', 'utilisateur'),
        pk=pk,
    )
    lignes = commande.lignes.select_related('medicament').all()
    receptions = commande.receptions.select_related('utilisateur').all()
    return render(request, 'achats/detail.html', {
        'commande': commande,
        'lignes': lignes,
        'receptions': receptions,
    })


@login_required
@permission_required('achats.change_commandeachat', raise_exception=True)
def achat_valider(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if request.method == 'POST' and commande.statut == CommandeAchat.STATUT_BROUILLON:
        commande.statut = CommandeAchat.STATUT_COMMANDEE
        commande.save(update_fields=['statut'])
        enregistrer_audit(request, 'VALIDATION_COMMANDE', 'CommandeAchat', commande.pk, commande.numero)
        messages.success(request, f"La commande {commande.numero} est désormais validée (Commandée).")
    return redirect('achats:achat_detail', pk=commande.pk)


@login_required
@permission_required('achats.change_commandeachat', raise_exception=True)
def achat_annuler(request, pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if request.method == 'POST':
        if commande.receptions.filter(validee=True).exists():
            messages.error(request, "Impossible d'annuler une commande ayant déjà fait l'objet d'une réception.")
        else:
            commande.statut = CommandeAchat.STATUT_ANNULEE
            commande.save(update_fields=['statut'])
            enregistrer_audit(request, 'ANNULATION_COMMANDE', 'CommandeAchat', commande.pk, commande.numero)
            messages.warning(request, f"La commande {commande.numero} a été annulée.")
    return redirect('achats:achat_detail', pk=commande.pk)


@login_required
@permission_required('achats.add_receptionachat', raise_exception=True)
def reception_create(request, commande_pk):
    commande = get_object_or_404(CommandeAchat, pk=commande_pk)
    if commande.statut not in [CommandeAchat.STATUT_COMMANDEE, CommandeAchat.STATUT_PARTIELLE]:
        messages.error(request, "Cette commande n'est pas en attente de réception.")
        return redirect('achats:achat_detail', pk=commande.pk)

    lignes_restantes = []
    for ligne in commande.lignes.select_related('medicament').all():
        reste = ligne.quantite_commandee - ligne.quantite_recue
        if reste > 0:
            lignes_restantes.append({'ligne': ligne, 'reste': reste})

    if request.method == 'POST':
        observations = request.POST.get('observations', '').strip()
        aujourd_hui = timezone.localdate()

        try:
            with transaction.atomic():
                cmd_locked = CommandeAchat.objects.select_for_update().get(pk=commande.pk)
                reception = ReceptionAchat.objects.create(
                    numero=_generer_numero('REC'),
                    commande=cmd_locked,
                    utilisateur=request.user,
                    observations=observations,
                    validee=True,
                )

                nb_lignes_recues = 0
                for item in lignes_restantes:
                    ligne = LigneAchat.objects.select_for_update().get(pk=item['ligne'].pk)
                    qte_str = request.POST.get(f"qte_{ligne.pk}", "0")
                    num_lot = request.POST.get(f"lot_{ligne.pk}", "").strip()
                    date_per_str = request.POST.get(f"peremption_{ligne.pk}", "").strip()

                    qte = int(qte_str or 0)
                    if qte <= 0:
                        continue

                    reste_actuel = ligne.quantite_commandee - ligne.quantite_recue
                    if qte > reste_actuel:
                        raise ValueError(f"Quantité reçue supérieure au reste à livrer pour {ligne.medicament.nom_commercial}.")
                    if not num_lot or not date_per_str:
                        raise ValueError(f"Numéro de lot et date de péremption requis pour {ligne.medicament.nom_commercial}.")

                    date_per = date.fromisoformat(date_per_str)
                    if date_per <= aujourd_hui:
                        raise ValueError(f"Impossible de réceptionner un lot déjà périmé ({ligne.medicament.nom_commercial}).")

                    lot, created = LotStock.objects.select_for_update().get_or_create(
                        medicament=ligne.medicament,
                        numero_lot=num_lot,
                        defaults={
                            'date_peremption': date_per,
                            'quantite_initiale': qte,
                            'quantite_disponible': 0,
                        },
                    )
                    avant = lot.quantite_disponible
                    lot.quantite_disponible = avant + qte
                    lot.date_peremption = date_per
                    lot.save(update_fields=['quantite_disponible', 'date_peremption'])

                    ligne.quantite_recue += qte
                    ligne.save(update_fields=['quantite_recue'])

                    LigneReception.objects.create(
                        reception=reception,
                        ligne_achat=ligne,
                        lot=lot,
                        quantite_recue=qte,
                        numero_lot=num_lot,
                        date_peremption=date_per,
                    )

                    MouvementStock.objects.create(
                        medicament=ligne.medicament,
                        lot=lot,
                        utilisateur=request.user,
                        type_mouvement=MouvementStock.TYPE_ENTREE,
                        quantite=qte,
                        stock_avant=avant,
                        stock_apres=lot.quantite_disponible,
                        reference_document=reception.numero,
                        motif=f"Réception commande {cmd_locked.numero}",
                    )
                    nb_lignes_recues += 1

                if nb_lignes_recues == 0:
                    raise ValueError("Saisissez au moins une quantité reçue supérieure à zéro.")

                tout_recu = all(
                    l.quantite_recue >= l.quantite_commandee
                    for l in cmd_locked.lignes.all()
                )
                cmd_locked.statut = CommandeAchat.STATUT_RECUE if tout_recu else CommandeAchat.STATUT_PARTIELLE
                cmd_locked.save(update_fields=['statut'])
                enregistrer_audit(request, 'RECEPTION_ACHAT', 'ReceptionAchat', reception.pk, f"{reception.numero} ({cmd_locked.numero})")

            messages.success(request, f"Réception {reception.numero} validée : les lots et stocks ont été mis à jour.")
            return redirect('achats:achat_detail', pk=commande.pk)

        except ValueError as e:
            messages.error(request, str(e))

    return render(request, 'achats/reception_form.html', {
        'commande': commande,
        'lignes_restantes': lignes_restantes,
    })