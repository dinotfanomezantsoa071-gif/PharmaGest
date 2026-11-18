from django.urls import path
from . import views

app_name = 'ventes'

urlpatterns = [
    path('', views.vente_list, name='vente_list'),
    path('caisse/', views.caisse_view, name='caisse'),
    path('<int:pk>/', views.vente_detail, name='vente_detail'),
    path('ligne/<int:ligne_pk>/retour/', views.retour_create, name='retour_create'),
]