from django.urls import path
from . import views

app_name = 'achats'

urlpatterns = [
    path('', views.achat_list, name='achat_list'),
    path('nouvelle/', views.achat_create, name='achat_create'),
    path('<int:pk>/', views.achat_detail, name='achat_detail'),
    path('<int:pk>/valider/', views.achat_valider, name='achat_valider'),
    path('<int:pk>/annuler/', views.achat_annuler, name='achat_annuler'),
    path('<int:commande_pk>/receptionner/', views.reception_create, name='reception_create'),
]