from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
    path('', views.stock_list, name='stock_list'),
    path('mouvements/', views.mouvement_list, name='mouvement_list'),
    path('lot/<int:pk>/bloquer/', views.lot_toggle_bloque, name='lot_toggle_bloque'),
    path('lot/<int:pk>/ajuster/', views.inventaire_ajustement, name='inventaire_ajustement'),
]