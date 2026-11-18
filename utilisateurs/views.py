from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordResetConfirmView as DjangoPasswordResetConfirmView
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import UtilisateurForm
from .models import JournalAudit, Utilisateur
from .utils import enregistrer_audit


class PasswordResetConfirmView(DjangoPasswordResetConfirmView):
    def form_valid(self, form):
        response = super().form_valid(form)
        JournalAudit.objects.create(
            utilisateur=self.user,
            action='REINITIALISATION_MOT_DE_PASSE',
            modele_cible='Utilisateur',
            objet_id=str(self.user.pk),
            details='Mot de passe réinitialisé via le lien sécurisé.',
        )
        return response


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form_error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                form_error = "Ce compte est désactivé. Contactez l'administrateur."
            else:
                login(request, user)
                messages.success(request, f"Bienvenue, {user.get_full_name() or user.username}.")
                next_url = request.GET.get('next') or 'dashboard'
                return redirect(next_url)
        else:
            form_error = "Nom d'utilisateur ou mot de passe incorrect."

    return render(request, 'authentication/login.html', {'form_error': form_error})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté avec succès.")
    return redirect('login')


@login_required
@permission_required('utilisateurs.view_utilisateur', raise_exception=True)
def utilisateur_list(request):
    q = request.GET.get('q', '').strip()
    utilisateurs = Utilisateur.objects.all()
    if q:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )
    page_obj = Paginator(utilisateurs, 15).get_page(request.GET.get('page'))
    return render(request, 'utilisateurs/liste.html', {'page_obj': page_obj, 'q': q})


@login_required
@permission_required('utilisateurs.add_utilisateur', raise_exception=True)
def utilisateur_create(request):
    form = UtilisateurForm(request.POST or None, is_create=True)
    if request.method == 'POST' and form.is_valid():
        utilisateur = form.save()
        enregistrer_audit(
            request, 'CREATION_UTILISATEUR', 'Utilisateur', utilisateur.pk,
            f"Compte créé : {utilisateur.username} ({utilisateur.get_role_display()})",
        )
        messages.success(request, f"Le compte « {utilisateur.username} » a été créé.")
        return redirect('utilisateur_list')
    return render(request, 'utilisateurs/form.html', {'form': form, 'titre': 'Nouvel utilisateur'})


@login_required
@permission_required('utilisateurs.change_utilisateur', raise_exception=True)
def utilisateur_update(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    if utilisateur.is_superuser:
        messages.error(request, "Un superutilisateur doit être géré depuis l'administration Django.")
        return redirect('utilisateur_list')
    form = UtilisateurForm(request.POST or None, instance=utilisateur)
    if request.method == 'POST' and form.is_valid():
        utilisateur = form.save()
        enregistrer_audit(
            request, 'MODIFICATION_UTILISATEUR', 'Utilisateur', utilisateur.pk,
            f"Compte modifié : {utilisateur.username} ({utilisateur.get_role_display()})",
        )
        messages.success(request, f"Le compte « {utilisateur.username} » a été mis à jour.")
        return redirect('utilisateur_list')
    return render(request, 'utilisateurs/form.html', {
        'form': form,
        'titre': f'Modifier : {utilisateur.username}',
        'utilisateur': utilisateur,
    })


@login_required
@permission_required('utilisateurs.change_utilisateur', raise_exception=True)
@require_POST
def utilisateur_toggle_actif(request, pk):
    utilisateur = get_object_or_404(Utilisateur, pk=pk)
    if utilisateur == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
    elif utilisateur.is_superuser:
        messages.error(request, "Un superutilisateur ne peut pas être désactivé depuis cette page.")
    else:
        utilisateur.is_active = not utilisateur.is_active
        utilisateur.save(update_fields=['is_active'])
        etat = 'activé' if utilisateur.is_active else 'désactivé'
        enregistrer_audit(
            request, 'STATUT_UTILISATEUR', 'Utilisateur', utilisateur.pk,
            f"Compte {utilisateur.username} {etat}",
        )
        messages.success(request, f"Le compte « {utilisateur.username} » a été {etat}.")
    return redirect('utilisateur_list')


@login_required
def password_change_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        enregistrer_audit(request, 'CHANGEMENT_MOT_DE_PASSE', 'Utilisateur', user.pk)
        messages.success(request, "Votre mot de passe a été modifié.")
        return redirect('dashboard')
    return render(request, 'utilisateurs/password_change.html', {'form': form})