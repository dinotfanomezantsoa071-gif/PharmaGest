from django.urls import path
from . import views

app_name = 'fournisseurs'

urlpatterns = [
    path('', views.fournisseur_list, name='fournisseur_list'),
    path('ajouter/', views.fournisseur_create, name='fournisseur_create'),
    path('<int:pk>/', views.fournisseur_detail, name='fournisseur_detail'),
    path('<int:pk>/modifier/', views.fournisseur_update, name='fournisseur_update'),
    path('<int:pk>/statut/', views.fournisseur_toggle_actif, name='fournisseur_toggle_actif'),
]