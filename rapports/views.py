from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import F, Q, Sum
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET

from achats.models import CommandeAchat, ReceptionAchat
from clients.models import Client
from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import Paiement, RetourVente, Vente

from .pdf import build_pdf_response


@login_required
def rapports_index(request):
    return render(request, 'rapports/index.html', {
        'can_view_sales': request.user.has_perm('ventes.view_vente'),
        'can_view_purchases': request.user.has_perm('achats.view_commandeachat'),
        'can_view_stock': request.user.has_perm('stock.view_lotstock'),
    })


def _date_range(request):
    start = parse_date(request.GET.get('debut', ''))
    end = parse_date(request.GET.get('fin', ''))
    if request.GET.get('debut') and start is None:
        return None, None, HttpResponseBadRequest("La date de début est invalide.")
    if request.GET.get('fin') and end is None:
        return None, None, HttpResponseBadRequest("La date de fin est invalide.")
    if start and end and start > end:
        return None, None, HttpResponseBadRequest("La date de début doit précéder la date de fin.")
    return start, end, None


def _apply_date_range(queryset, field, start, end):
    if start:
        queryset = queryset.filter(**{f'{field}__date__gte': start})
    if end:
        queryset = queryset.filter(**{f'{field}__date__lte': end})
    return queryset


def _sales_chart_data(today):
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    values = []
    for day in days:
        amount = Vente.objects.filter(
            date_vente__date=day,
            statut__in=[Vente.STATUT_VALIDEE, Vente.STATUT_RETOUR_PARTIEL],
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0.00')
        refunded = RetourVente.objects.filter(
            date_retour__date=day,
        ).aggregate(total=Sum('montant_rembourse'))['total'] or Decimal('0.00')
        values.append(float(amount - refunded))
    return [day.strftime('%d/%m') for day in days], values


def _sales_category_data(today):
    from ventes.models import LigneVente

    sales = LigneVente.objects.filter(
        vente__date_vente__date__gte=today - timedelta(days=29),
        vente__date_vente__date__lte=today,
        vente__statut__in=[Vente.STATUT_VALIDEE, Vente.STATUT_RETOUR_PARTIEL],
    ).values(
        'medicament__categorie__nom',
    ).annotate(
        quantity=Sum('quantite'),
    ).order_by('-quantity', 'medicament__categorie__nom')
    return {
        'labels': [item['medicament__categorie__nom'] for item in sales],
        'values': [item['quantity'] for item in sales],
    }


def _stock_status_data(medicines):
    return {
        'labels': ['En stock', 'Stock faible', 'Rupture'],
        'values': [
            medicines.filter(quantite_stock_dashboard__gt=F('seuil_alerte')).count(),
            medicines.filter(
                quantite_stock_dashboard__gt=0,
                quantite_stock_dashboard__lte=F('seuil_alerte'),
            ).count(),
            medicines.filter(
                Q(quantite_stock_dashboard__isnull=True) | Q(quantite_stock_dashboard=0),
            ).count(),
        ],
    }


def _purchases_supplier_data(today):
    purchases = CommandeAchat.objects.filter(
        date_commande__date__gte=today - timedelta(days=29),
        date_commande__date__lte=today,
    ).exclude(statut=CommandeAchat.STATUT_ANNULEE).values(
        'fournisseur__raison_sociale',
    ).annotate(
        total=Sum('montant_total'),
    ).order_by('-total', 'fournisseur__raison_sociale')
    return {
        'labels': [item['fournisseur__raison_sociale'] for item in purchases],
        'values': [float(item['total'] or Decimal('0.00')) for item in purchases],
    }


@login_required
def dashboard_view(request):
    today = timezone.localdate()
    soon = today + timedelta(days=30)
    can_view_sales = request.user.has_perm('ventes.view_vente')
    can_view_purchases = request.user.has_perm('achats.view_commandeachat')
    can_view_stock = request.user.has_perm('stock.view_lotstock')
    can_view_catalog = request.user.has_perm('medicaments.view_medicament')
    can_view_clients = request.user.has_perm('clients.view_client')

    medicines = Medicament.objects.filter(statut=Medicament.STATUT_ACTIF).annotate(
        quantite_stock_dashboard=Sum(
            'lots__quantite_disponible',
            filter=Q(
                lots__bloque=False,
                lots__date_peremption__gte=today,
            ),
        ),
    )
    stocks_faibles = medicines.filter(
        Q(quantite_stock_dashboard__isnull=True) | Q(quantite_stock_dashboard__lte=F('seuil_alerte'))
    ).count()
    peremptions_proches = LotStock.objects.filter(
        medicament__statut=Medicament.STATUT_ACTIF,
        bloque=False,
        date_peremption__gte=today,
        date_peremption__lte=soon,
        quantite_disponible__gt=0,
    ).count()
    lots_perimes = LotStock.objects.filter(
        medicament__statut=Medicament.STATUT_ACTIF,
        date_peremption__lt=today,
        quantite_disponible__gt=0,
    ).count()

    sales_labels, sales_values = _sales_chart_data(today) if can_view_sales else ([], [])
    sales_by_category = _sales_category_data(today) if can_view_sales else {'labels': [], 'values': []}
    stock_status = _stock_status_data(medicines) if can_view_stock else {'labels': [], 'values': []}
    purchases_by_supplier = _purchases_supplier_data(today) if can_view_purchases else {'labels': [], 'values': []}

    ventes_jour = Decimal('0.00')
    encaissements_jour = Decimal('0.00')
    achats_semaine = Decimal('0.00')
    produits_populaires = []
    if can_view_sales:
        ventes_jour = Vente.objects.filter(
            date_vente__date=today,
            statut__in=[Vente.STATUT_VALIDEE, Vente.STATUT_RETOUR_PARTIEL],
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0.00')
        remboursements_jour = RetourVente.objects.filter(
            date_retour__date=today,
        ).aggregate(total=Sum('montant_rembourse'))['total'] or Decimal('0.00')
        ventes_jour -= remboursements_jour
        encaissements_jour = Paiement.objects.filter(
            date_paiement__date=today,
            statut=Paiement.STATUT_CONFIRME,
        ).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
        from ventes.models import LigneVente
        produits_populaires = list(
            LigneVente.objects.filter(vente__date_vente__date__gte=today - timedelta(days=29))
            .values('medicament__nom_commercial')
            .annotate(quantite=Sum('quantite'))
            .order_by('-quantite')[:5]
        )
    if can_view_purchases:
        achats_semaine = CommandeAchat.objects.filter(
            date_commande__date__gte=today - timedelta(days=6),
            date_commande__date__lte=today,
        ).exclude(statut=CommandeAchat.STATUT_ANNULEE).aggregate(
            total=Sum('montant_total'),
        )['total'] or Decimal('0.00')

    alertes_stock = []
    alertes_peremption = []
    if can_view_stock:
        alertes_stock = list(medicines.filter(
            Q(quantite_stock_dashboard__isnull=True) | Q(quantite_stock_dashboard__lte=F('seuil_alerte'))
        ).order_by('nom_commercial')[:6])
        alertes_peremption = list(
            LotStock.objects.filter(
                medicament__statut=Medicament.STATUT_ACTIF,
                bloque=False,
                date_peremption__gte=today,
                date_peremption__lte=soon,
                quantite_disponible__gt=0,
            ).select_related('medicament').order_by('date_peremption')[:6]
        )

    context = {
        'kpi': {
            'medicaments_actifs': (
                Medicament.objects.filter(statut=Medicament.STATUT_ACTIF).count()
                if can_view_catalog else None
            ),
            'clients_actifs': Client.objects.filter(actif=True).count() if can_view_clients else None,
            'ventes_jour': ventes_jour,
            'encaissements_jour': encaissements_jour,
            'achats_semaine': achats_semaine,
            'stocks_faibles': stocks_faibles,
            'peremptions_proches': peremptions_proches,
            'lots_perimes': lots_perimes,
        },
        'sales_labels': sales_labels,
        'sales_values': sales_values,
        'sales_category_labels': sales_by_category['labels'],
        'sales_category_values': sales_by_category['values'],
        'stock_status_labels': stock_status['labels'],
        'stock_status_values': stock_status['values'],
        'purchase_supplier_labels': purchases_by_supplier['labels'],
        'purchase_supplier_values': purchases_by_supplier['values'],
        'produits_populaires': produits_populaires,
        'alertes_stock': alertes_stock,
        'alertes_peremption': alertes_peremption,
        'can_view_sales': can_view_sales,
        'can_view_purchases': can_view_purchases,
        'can_view_stock': can_view_stock,
        'can_view_catalog': can_view_catalog,
        'can_view_clients': can_view_clients,
    }
    return render(request, 'dashboard/index.html', context)


@login_required
@require_GET
def dashboard_sales_data(request):
    can_view_sales = request.user.has_perm('ventes.view_vente')
    can_view_stock = request.user.has_perm('stock.view_lotstock')
    can_view_purchases = request.user.has_perm('achats.view_commandeachat')
    if not can_view_sales and not can_view_stock and not can_view_purchases:
        return HttpResponseForbidden()

    today = timezone.localdate()
    data = {}
    if can_view_sales:
        labels, values = _sales_chart_data(today)
        data.update({
            'labels': labels,
            'values': values,
            'categories': _sales_category_data(today),
        })
    if can_view_stock:
        medicines = Medicament.objects.filter(statut=Medicament.STATUT_ACTIF).annotate(
            quantite_stock_dashboard=Sum(
                'lots__quantite_disponible',
                filter=Q(
                    lots__bloque=False,
                    lots__date_peremption__gte=today,
                ),
            ),
        )
        data['stock'] = _stock_status_data(medicines)
    if can_view_purchases:
        data['purchases'] = _purchases_supplier_data(today)
    response = JsonResponse(data)
    patch_cache_control(response, no_cache=True, no_store=True)
    return response


@login_required
@permission_required('ventes.view_vente', raise_exception=True)
def vente_recu_pdf(request, pk):
    vente = get_object_or_404(
        Vente.objects.select_related('client', 'utilisateur').prefetch_related(
            'lignes__medicament',
            'lignes__lot',
            'paiements',
            'retours__ligne_vente__medicament',
            'retours__ligne_vente__lot',
        ),
        pk=pk,
    )
    rows = [
        [
            line.medicament.nom_commercial,
            line.lot.numero_lot,
            line.quantite,
            f'{line.prix_unitaire_applique:.2f} Ar',
            f'{line.sous_total:.2f} Ar',
        ]
        for line in vente.lignes.all()
    ]
    retours = [
        [
            retour.numero,
            timezone.localtime(retour.date_retour).strftime('%d/%m/%Y %H:%M'),
            retour.ligne_vente.medicament.nom_commercial,
            retour.ligne_vente.lot.numero_lot,
            retour.quantite_retournee,
            f'{retour.montant_rembourse:.2f} Ar',
            'Oui' if retour.reintegrer_stock else 'Non',
            retour.motif,
        ]
        for retour in vente.retours.all()
    ]

    total_rembourse = sum((retour.montant_rembourse for retour in vente.retours.all()), Decimal('0'))
    summary = (
        f"Date : {timezone.localtime(vente.date_vente):%d/%m/%Y %H:%M} | "
        f"Client : {vente.client.nom if vente.client else 'Comptoir anonyme'} | "
        f"Caissier : {vente.utilisateur.get_full_name() or vente.utilisateur.username} | "
        f"Total : {vente.montant_total:.2f} Ar | Payé : {vente.montant_paye:.2f} Ar"
    )
    if retours:
        summary += f" | Retours : {len(retours)} | Remboursé : {total_rembourse:.2f} Ar"

    sections = []
    if retours:
        sections.append((
            'Retours enregistrés',
            ['N° retour', 'Date', 'Médicament', 'Lot', 'Qté', 'Remboursé', 'Stock réintégré', 'Motif'],
            retours,
        ))

    return build_pdf_response(
        f'recu-{vente.numero}.pdf',
        f'Reçu de vente {vente.numero}',
        ['Médicament', 'Lot', 'Qté', 'Prix unitaire', 'Sous-total'],
        rows,
        summary,
        wide=True,
        sections=sections,
    )


@login_required
@permission_required('ventes.view_vente', raise_exception=True)
def ventes_pdf(request):
    start, end, error = _date_range(request)
    if error:
        return error
    queryset = _apply_date_range(
        Vente.objects.select_related('client').filter(
            statut__in=[Vente.STATUT_VALIDEE, Vente.STATUT_RETOUR_PARTIEL],
        ),
        'date_vente',
        start,
        end,
    )
    rows = [
        [
            sale.numero,
            timezone.localtime(sale.date_vente).strftime('%d/%m/%Y %H:%M'),
            sale.client.nom if sale.client else 'Comptoir anonyme',
            sale.get_statut_display(),
            f'{sale.montant_total:.2f} Ar',
        ]
        for sale in queryset
    ]
    return build_pdf_response('rapport-ventes.pdf', 'Rapport des ventes',
                              ['N° vente', 'Date', 'Client', 'Statut', 'Montant'], rows,
                              f"Période : {start or 'début'} au {end or 'aujourd’hui'}", wide=True)


@login_required
@permission_required('achats.view_commandeachat', raise_exception=True)
def achats_pdf(request):
    start, end, error = _date_range(request)
    if error:
        return error
    queryset = _apply_date_range(
        CommandeAchat.objects.select_related('fournisseur').exclude(statut=CommandeAchat.STATUT_ANNULEE),
        'date_commande',
        start,
        end,
    )
    rows = [
        [
            order.numero,
            timezone.localtime(order.date_commande).strftime('%d/%m/%Y %H:%M'),
            order.fournisseur.raison_sociale,
            order.get_statut_display(),
            f'{order.montant_total:.2f} Ar',
        ]
        for order in queryset
    ]
    return build_pdf_response('rapport-achats.pdf', 'Rapport des achats',
                              ['N° commande', 'Date', 'Fournisseur', 'Statut', 'Montant'], rows,
                              f"Période : {start or 'début'} au {end or 'aujourd’hui'}", wide=True)


@login_required
@permission_required('stock.view_lotstock', raise_exception=True)
def stock_pdf(request):
    lots = LotStock.objects.select_related('medicament').order_by('medicament__nom_commercial', 'date_peremption')
    rows = [
        [
            lot.medicament.nom_commercial,
            lot.numero_lot,
            lot.date_peremption.strftime('%d/%m/%Y'),
            lot.quantite_disponible,
            'Bloqué' if lot.bloque else ('Périmé' if lot.est_perime else 'Disponible'),
        ]
        for lot in lots
    ]
    return build_pdf_response('rapport-stock.pdf', 'Rapport du stock',
                              ['Médicament', 'Lot', 'Péremption', 'Quantité', 'État'], rows,
                              f"Généré le {timezone.localtime():%d/%m/%Y %H:%M}", wide=True)


@login_required
@permission_required('stock.view_lotstock', raise_exception=True)
def peremptions_pdf(request):
    today = timezone.localdate()
    limit = today + timedelta(days=30)
    lots = LotStock.objects.filter(
        date_peremption__gte=today,
        date_peremption__lte=limit,
        quantite_disponible__gt=0,
        bloque=False,
    ).select_related('medicament').order_by('date_peremption')
    rows = [
        [
            lot.medicament.nom_commercial,
            lot.numero_lot,
            lot.date_peremption.strftime('%d/%m/%Y'),
            lot.quantite_disponible,
            (lot.date_peremption - today).days,
        ]
        for lot in lots
    ]
    return build_pdf_response('produits-proches-peremption.pdf', 'Produits proches de la péremption',
                              ['Médicament', 'Lot', 'Péremption', 'Quantité', 'Jours restants'], rows,
                              f"Lots qui expirent dans les 30 jours à partir du {today:%d/%m/%Y}.", wide=True)


@login_required
@permission_required('achats.view_commandeachat', raise_exception=True)
def commande_achat_pdf(request, pk):
    order = get_object_or_404(
        CommandeAchat.objects.select_related('fournisseur', 'utilisateur').prefetch_related('lignes__medicament'),
        pk=pk,
    )
    rows = [
        [
            line.medicament.nom_commercial,
            line.quantite_commandee,
            f'{line.prix_unitaire_achat:.2f} Ar',
            f'{line.sous_total:.2f} Ar',
        ]
        for line in order.lignes.all()
    ]
    return build_pdf_response(
        f'commande-{order.numero}.pdf',
        f'Bon de commande {order.numero}',
        ['Médicament', 'Quantité', 'Prix unitaire', 'Sous-total'],
        rows,
        f"Fournisseur : {order.fournisseur.raison_sociale} | "
        f"Date : {timezone.localtime(order.date_commande):%d/%m/%Y} | "
        f"Statut : {order.get_statut_display()} | Total : {order.montant_total:.2f} Ar",
    )


@login_required
@permission_required('achats.view_receptionachat', raise_exception=True)
def reception_pdf(request, pk):
    reception = get_object_or_404(
        ReceptionAchat.objects.select_related('commande__fournisseur', 'utilisateur').prefetch_related('lignes__ligne_achat__medicament'),
        pk=pk,
    )
    rows = [
        [
            line.ligne_achat.medicament.nom_commercial,
            line.numero_lot,
            line.date_peremption.strftime('%d/%m/%Y'),
            line.quantite_recue,
        ]
        for line in reception.lignes.all()
    ]
    return build_pdf_response(
        f'reception-{reception.numero}.pdf',
        f'Bon de réception {reception.numero}',
        ['Médicament', 'Lot', 'Péremption', 'Quantité reçue'],
        rows,
        f"Commande : {reception.commande.numero} | Fournisseur : {reception.commande.fournisseur.raison_sociale} | "
        f"Date : {timezone.localtime(reception.date_reception):%d/%m/%Y %H:%M}",
    )