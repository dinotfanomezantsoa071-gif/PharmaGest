from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

urlpatterns = [
    path('connexion/', views.login_view, name='login'),
    path('deconnexion/', views.logout_view, name='logout'),
    path('mot-de-passe/', views.password_change_view, name='password_change'),
    path(
        'mot-de-passe/oublie/',
        auth_views.PasswordResetView.as_view(
            template_name='authentication/password_reset_form.html',
            email_template_name='authentication/password_reset_email.txt',
            subject_template_name='authentication/password_reset_subject.txt',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'mot-de-passe/envoye/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='authentication/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'mot-de-passe/reinitialiser/<uidb64>/<token>/',
        views.PasswordResetConfirmView.as_view(
            template_name='authentication/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'mot-de-passe/termine/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='authentication/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('utilisateurs/', views.utilisateur_list, name='utilisateur_list'),
    path('utilisateurs/nouveau/', views.utilisateur_create, name='utilisateur_create'),
    path('utilisateurs/<int:pk>/modifier/', views.utilisateur_update, name='utilisateur_update'),
    path('utilisateurs/<int:pk>/statut/', views.utilisateur_toggle_actif, name='utilisateur_toggle_actif'),
]