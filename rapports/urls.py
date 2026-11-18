from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('api/dashboard/ventes/', views.dashboard_sales_data, name='dashboard_sales_data'),
    path('rapports/', views.rapports_index, name='rapports_index'),
    path('rapports/ventes.pdf', views.ventes_pdf, name='ventes_pdf'),
    path('rapports/achats.pdf', views.achats_pdf, name='achats_pdf'),
    path('rapports/stock.pdf', views.stock_pdf, name='stock_pdf'),
    path('rapports/peremptions.pdf', views.peremptions_pdf, name='peremptions_pdf'),
    path('ventes/<int:pk>/recu.pdf', views.vente_recu_pdf, name='vente_recu_pdf'),
    path('achats/<int:pk>/commande.pdf', views.commande_achat_pdf, name='commande_achat_pdf'),
    path('receptions/<int:pk>/bon.pdf', views.reception_pdf, name='reception_pdf'),
]