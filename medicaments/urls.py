from django.urls import path
from . import views

app_name = 'medicaments'

urlpatterns = [
    path('categories/', views.categorie_list, name='categorie_list'),
    path('categories/ajouter/', views.categorie_create, name='categorie_create'),
    path('categories/<int:pk>/modifier/', views.categorie_update, name='categorie_update'),
    path('categories/<int:pk>/supprimer/', views.categorie_delete, name='categorie_delete'),

    path('', views.medicament_list, name='medicament_list'),
    path('ajouter/', views.medicament_create, name='medicament_create'),
    path('<int:pk>/', views.medicament_detail, name='medicament_detail'),
    path('<int:pk>/modifier/', views.medicament_update, name='medicament_update'),
    path('<int:pk>/archiver/', views.medicament_archive_or_delete, name='medicament_delete'),
]