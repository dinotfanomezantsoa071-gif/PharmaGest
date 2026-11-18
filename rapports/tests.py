from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from pathlib import Path

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from achats.models import CommandeAchat
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from rapports.views import dashboard_view
from stock.models import LotStock, MouvementStock
from utilisateurs.models import Utilisateur
from ventes.models import LigneVente, Paiement, Vente


class DashboardAndPdfTests(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_superuser(
            username='report-admin',
            email='reports@example.test',
            password='SafeReportPass!928',
        )
        self.client.force_login(self.user)
        self.client_record = Client.objects.create(nom='Client réel')
        supplier = Fournisseur.objects.create(
            raison_sociale='Fournisseur test',
            telephone='000000000',
        )
        self.purchase = CommandeAchat.objects.create(
            numero='CMD-REPORT',
            fournisseur=supplier,
            utilisateur=self.user,
            statut=CommandeAchat.STATUT_RECUE,
            montant_total=Decimal('50.00'),
        )
        category = Categorie.objects.create(nom='Test')
        self.medicine = Medicament.objects.create(
            nom_commercial='Produit test',
            denomination_generique='Molécule test',
            categorie=category,
            forme_pharmaceutique='Comprimé',
            dosage='500 mg',
            prix_achat=Decimal('5.00'),
            prix_vente=Decimal('10.00'),
            seuil_alerte=5,
        )
        self.lot = LotStock.objects.create(
            medicament=self.medicine,
            numero_lot='LOT-REPORT',
            date_peremption=timezone.localdate() + timedelta(days=10),
            quantite_initiale=3,
            quantite_disponible=3,
        )
        sale = Vente.objects.create(
            numero='VNT-REPORT',
            utilisateur=self.user,
            statut=Vente.STATUT_VALIDEE,
            montant_total=Decimal('20.00'),
            montant_paye=Decimal('20.00'),
        )
        LigneVente.objects.create(
            vente=sale,
            medicament=self.medicine,
            lot=self.lot,
            quantite=2,
            prix_unitaire_applique=Decimal('10.00'),
        )
        Paiement.objects.create(
            vente=sale,
            mode_paiement=Paiement.MODE_ESPECES,
            montant=Decimal('20.00'),
            statut=Paiement.STATUT_CONFIRME,
            utilisateur=self.user,
        )
        self.sale = sale

    def test_dashboard_uses_database_values_and_permissions(self):
        request = RequestFactory().get(reverse('dashboard'))
        request.user = self.user
        with patch('rapports.views.render', return_value=HttpResponse('ok')) as render:
            response = dashboard_view(request)
        context = render.call_args.args[2]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(context['kpi']['medicaments_actifs'], 1)
        self.assertEqual(context['kpi']['ventes_jour'], Decimal('20.00'))
        self.assertEqual(context['kpi']['encaissements_jour'], Decimal('20.00'))
        self.assertEqual(context['kpi']['stocks_faibles'], 1)
        self.assertEqual(context['kpi']['peremptions_proches'], 1)
        self.assertEqual(context['kpi']['clients_actifs'], 1)
        self.assertEqual(context['sales_values'][-1], 20.0)
        self.assertEqual(context['sales_category_labels'], ['Test'])
        self.assertEqual(context['sales_category_values'], [2])
        self.assertEqual(context['stock_status_labels'], ['En stock', 'Stock faible', 'Rupture'])
        self.assertEqual(context['stock_status_values'], [0, 1, 0])
        self.assertEqual(context['purchase_supplier_labels'], ['Fournisseur test'])
        self.assertEqual(context['purchase_supplier_values'], [50.0])

    def test_dashboard_sales_data_returns_current_chart_values(self):
        response = self.client.get(reverse('dashboard_sales_data'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('no-store', response['Cache-Control'])
        data = response.json()
        self.assertEqual(len(data['labels']), 7)
        self.assertEqual(len(data['values']), 7)
        self.assertEqual(data['values'][-1], 20.0)
        self.assertEqual(data['categories'], {'labels': ['Test'], 'values': [2]})
        self.assertEqual(data['stock'], {
            'labels': ['En stock', 'Stock faible', 'Rupture'],
            'values': [0, 1, 0],
        })
        self.assertEqual(data['purchases'], {'labels': ['Fournisseur test'], 'values': [50.0]})

    def test_dashboard_sales_data_is_available_to_stock_only_users(self):
        self.user.is_superuser = False
        self.user.is_staff = False
        self.user.user_permissions.set([
            Permission.objects.get(codename='view_lotstock'),
        ])
        self.user.save()

        response = self.client.get(reverse('dashboard_sales_data'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'stock': {
                'labels': ['En stock', 'Stock faible', 'Rupture'],
                'values': [0, 1, 0],
            },
        })

    def test_dashboard_sales_data_is_available_to_purchase_only_users(self):
        self.user.is_superuser = False
        self.user.is_staff = False
        self.user.user_permissions.set([
            Permission.objects.get(codename='view_commandeachat'),
        ])
        self.user.save()

        response = self.client.get(reverse('dashboard_sales_data'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'purchases': {'labels': ['Fournisseur test'], 'values': [50.0]},
        })

    def test_demo_data_command_requires_confirmation_and_creates_related_records(self):
        output = StringIO()
        call_command('charger_donnees_demo', stdout=output)
        self.assertEqual(Medicament.objects.filter(nom_commercial__startswith='DEMO - ').count(), 0)

        with patch(
            'utilisateurs.management.commands.charger_donnees_demo.create_database_backup',
            return_value=Path('demo-backup.sqlite3'),
        ):
            call_command('charger_donnees_demo', confirm=True, stdout=output)

        demo_medicines = Medicament.objects.filter(nom_commercial__startswith='DEMO - ')
        self.assertEqual(demo_medicines.count(), 6)
        self.assertEqual(Client.objects.filter(nom__startswith='DEMO - ').count(), 3)
        self.assertEqual(Fournisseur.objects.filter(raison_sociale__startswith='DEMO - ').count(), 3)
        self.assertEqual(Vente.objects.filter(numero__startswith='DEMO-VNT-').count(), 3)
        self.assertFalse(
            CommandeAchat.objects.filter(numero__startswith='DEMO-CMD-')
            .exclude(statut=CommandeAchat.STATUT_RECUE)
            .exists()
        )
        chart_response = self.client.get(reverse('dashboard_sales_data'))
        chart_data = chart_response.json()
        self.assertEqual(chart_response.status_code, 200)
        self.assertTrue(any(label.startswith('DEMO - ') for label in chart_data['categories']['labels']))
        self.assertTrue(any(label.startswith('DEMO - ') for label in chart_data['purchases']['labels']))
        self.assertTrue(any(value > 0 for value in chart_data['stock']['values']))

        with self.assertRaisesMessage(CommandError, 'Des données DEMO existent déjà'):
            call_command('charger_donnees_demo', confirm=True, stdout=output)

    def test_demo_stock_command_adds_a_low_stock_and_records_adjustment(self):
        output = StringIO()
        with patch(
            'utilisateurs.management.commands.charger_donnees_demo.create_database_backup',
            return_value=Path('demo-backup.sqlite3'),
        ):
            call_command('charger_donnees_demo', confirm=True, stdout=output)
            call_command('charger_donnees_demo', ajouter_stock_faible=True, stdout=output)

        medicine = Medicament.objects.get(nom_commercial='DEMO - Paracetamol 500 mg')
        lot = LotStock.objects.get(medicament=medicine, numero_lot='DEMO-LOT-001')
        self.assertEqual(lot.quantite_disponible, 2)
        self.assertLessEqual(lot.quantite_disponible, medicine.seuil_alerte)
        self.assertTrue(
            lot.mouvements.filter(
                type_mouvement=MouvementStock.TYPE_AJUSTEMENT,
                motif='Ajustement DEMO : stock sous le seuil',
            ).exists()
        )

        request = RequestFactory().get(reverse('dashboard'))
        request.user = self.user
        with patch('rapports.views.render', return_value=HttpResponse('ok')) as render:
            dashboard_view(request)
        context = render.call_args.args[2]
        self.assertEqual(context['stock_status_values'], [5, 2, 0])
        self.assertIn(medicine, context['alertes_stock'])

        with patch(
            'utilisateurs.management.commands.charger_donnees_demo.create_database_backup',
        ) as backup:
            call_command('charger_donnees_demo', ajouter_stock_faible=True, stdout=output)
        backup.assert_not_called()
        self.assertEqual(lot.mouvements.filter(type_mouvement=MouvementStock.TYPE_AJUSTEMENT).count(), 1)

    def test_demo_expired_lot_command_updates_dashboard_and_is_idempotent(self):
        output = StringIO()
        with patch(
            'utilisateurs.management.commands.charger_donnees_demo.create_database_backup',
            return_value=Path('demo-backup.sqlite3'),
        ) as backup:
            call_command('charger_donnees_demo', confirm=True, stdout=output)
            call_command('charger_donnees_demo', ajouter_lot_perime=True, stdout=output)

            medicine = Medicament.objects.get(nom_commercial='DEMO - Ibuprofene 200 mg')
            lot = LotStock.objects.get(
                medicament=medicine,
                numero_lot='DEMO-LOT-EXPIRE-001',
            )
            self.assertLess(lot.date_peremption, timezone.localdate())
            self.assertEqual(lot.quantite_disponible, 4)
            self.assertTrue(
                lot.mouvements.filter(
                    type_mouvement=MouvementStock.TYPE_ENTREE,
                    reference_document='DEMO-EXPIRE-001',
                ).exists()
            )

            request = RequestFactory().get(reverse('dashboard'))
            request.user = self.user
            with patch('rapports.views.render', return_value=HttpResponse('ok')) as render:
                dashboard_view(request)
            context = render.call_args.args[2]
            self.assertEqual(context['kpi']['lots_perimes'], 1)

            backup.reset_mock()
            call_command('charger_donnees_demo', ajouter_lot_perime=True, stdout=output)

        backup.assert_not_called()
        self.assertEqual(
            LotStock.objects.filter(numero_lot='DEMO-LOT-EXPIRE-001').count(),
            1,
        )

    def test_dashboard_sales_data_reflects_new_sales(self):
        self.sale.montant_total = Decimal('35.00')
        self.sale.save(update_fields=['montant_total'])

        response = self.client.get(reverse('dashboard_sales_data'))

        self.assertEqual(response.json()['values'][-1], 35.0)

    def test_dashboard_sales_data_refreshes_category_quantities(self):
        line = self.sale.lignes.get()
        line.quantite = 4
        line.save()

        response = self.client.get(reverse('dashboard_sales_data'))

        self.assertEqual(response.json()['categories'], {'labels': ['Test'], 'values': [4]})

    def test_dashboard_sales_data_has_no_example_values_without_recent_sales(self):
        Vente.objects.filter(pk=self.sale.pk).update(
            date_vente=timezone.now() - timedelta(days=31),
        )

        response = self.client.get(reverse('dashboard_sales_data'))
        data = response.json()

        self.assertEqual(data['values'], [0.0] * 7)
        self.assertEqual(data['categories'], {'labels': [], 'values': []})

    def test_dashboard_sales_data_requires_sales_permission(self):
        self.user.is_superuser = False
        self.user.is_staff = False
        self.user.user_permissions.clear()
        self.user.groups.clear()
        self.user.save()

        self.assertEqual(self.client.get(reverse('dashboard_sales_data')).status_code, 403)

    def test_sale_receipt_returns_a_pdf(self):
        response = self.client.get(reverse('vente_recu_pdf', args=[self.sale.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_reports_require_the_corresponding_permission(self):
        self.user.is_superuser = False
        self.user.is_staff = False
        self.user.user_permissions.clear()
        self.user.groups.clear()
        self.user.save()

        self.assertEqual(self.client.get(reverse('ventes_pdf')).status_code, 403)
