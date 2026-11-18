from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from utilisateurs.utils import enregistrer_audit
from .forms import ClientForm
from .models import Client


@login_required
@permission_required('clients.view_client', raise_exception=True)
def client_list(request):
    q = request.GET.get('q', '').strip()
    clients = Client.objects.all()
    if q:
        clients = clients.filter(Q(nom__icontains=q) | Q(telephone__icontains=q) | Q(email__icontains=q))
    paginator = Paginator(clients, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'clients/liste.html', {'page_obj': page_obj, 'q': q})


@login_required
@permission_required('clients.view_client', raise_exception=True)
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    ventes = client.ventes.all().order_by('-date_vente')
    return render(request, 'clients/detail.html', {'client': client, 'ventes': ventes})


@login_required
@permission_required('clients.add_client', raise_exception=True)
def client_create(request):
    form = ClientForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        client = form.save()
        enregistrer_audit(request, 'CREATION_CLIENT', 'Client', client.pk, client.nom)
        messages.success(request, f"Le client « {client.nom} » a été ajouté.")
        return redirect('clients:client_list')
    return render(request, 'clients/form.html', {'form': form, 'titre': 'Nouveau client'})


@login_required
@permission_required('clients.change_client', raise_exception=True)
def client_update(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == 'POST' and form.is_valid():
        client = form.save()
        enregistrer_audit(request, 'MODIFICATION_CLIENT', 'Client', client.pk, client.nom)
        messages.success(request, f"Le client « {client.nom} » a été mis à jour.")
        return redirect('clients:client_detail', pk=client.pk)
    return render(request, 'clients/form.html', {'form': form, 'titre': f'Modifier : {client.nom}'})


@login_required
@permission_required('clients.change_client', raise_exception=True)
def client_toggle_actif(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        client.actif = not client.actif
        client.save(update_fields=['actif'])
        etat = 'activé' if client.actif else 'désactivé'
        enregistrer_audit(request, 'STATUT_CLIENT', 'Client', client.pk, f"{client.nom} {etat}")
        messages.info(request, f"Le client « {client.nom} » a été {etat}.")
    return redirect('clients:client_list')