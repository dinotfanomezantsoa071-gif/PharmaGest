import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.models import Utilisateur
from .models import LigneVente, Paiement, RetourVente, Vente


class CaisseIdempotencyTests(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_superuser(
            username='cashier-admin',
            email='cashier@example.test',
            password='SafeCashierPass!928',
        )
        self.client.force_login(self.user)
        category = Categorie.objects.create(nom='Caisse test')
        medicine = Medicament.objects.create(
            nom_commercial='Produit caisse',
            categorie=category,
            forme_pharmaceutique='Comprimé',
            dosage='250 mg',
            prix_achat=Decimal('5.00'),
            prix_vente=Decimal('10.00'),
            seuil_alerte=1,
        )
        self.lot = LotStock.objects.create(
            medicament=medicine,
            numero_lot='LOT-CAISSE',
            date_peremption=timezone.localdate() + timedelta(days=90),
            quantite_initiale=5,
            quantite_disponible=5,
        )
        self.token = str(uuid.uuid4())
        self.payload = {
            'panier_json': json.dumps([{'lot_id': self.lot.pk, 'quantite': 2}]),
            'jeton_vente': self.token,
            'mode_paiement': Paiement.MODE_ESPECES,
        }

    def test_reposting_same_checkout_token_does_not_decrement_stock_twice(self):
        url = reverse('ventes:caisse')
        first_response = self.client.post(url, self.payload)
        second_response = self.client.post(url, self.payload)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(Vente.objects.filter(jeton_idempotence=self.token).count(), 1)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite_disponible, 3)
        self.assertEqual(MouvementStock.objects.filter(type_mouvement=MouvementStock.TYPE_SORTIE).count(), 1)

    def test_mobile_money_cannot_be_confirmed_without_provider_verification(self):
        response = self.client.post(reverse('ventes:caisse'), {
            **self.payload,
            'mode_paiement': Paiement.MODE_MOBILE_MONEY,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Vente.objects.count(), 0)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite_disponible, 5)


class RetourVenteTests(TestCase):
    def setUp(self):
        self.user = Utilisateur.objects.create_superuser(
            username='return-admin',
            email='return@example.test',
            password='SafeReturnPass!928',
        )
        self.client.force_login(self.user)
        category = Categorie.objects.create(nom='Retour test')
        medicine = Medicament.objects.create(
            nom_commercial='Produit retour',
            categorie=category,
            forme_pharmaceutique='Comprimé',
            dosage='250 mg',
            prix_achat=Decimal('5.00'),
            prix_vente=Decimal('10.00'),
        )
        self.lot = LotStock.objects.create(
            medicament=medicine,
            numero_lot='LOT-RETOUR',
            date_peremption=timezone.localdate() - timedelta(days=1),
            quantite_initiale=2,
            quantite_disponible=0,
        )
        self.vente = Vente.objects.create(
            numero='VNT-RETOUR',
            utilisateur=self.user,
            statut=Vente.STATUT_VALIDEE,
            montant_total=Decimal('10.00'),
            montant_paye=Decimal('10.00'),
        )
        self.ligne = LigneVente.objects.create(
            vente=self.vente,
            medicament=medicine,
            lot=self.lot,
            quantite=1,
            prix_unitaire_applique=Decimal('10.00'),
        )

    def test_expired_lot_return_is_rejected_without_server_error(self):
        response = self.client.post(reverse('ventes:retour_create', args=[self.ligne.pk]), {
            'quantite_retournee': '1',
            'motif': 'Produit retourné',
            'reintegrer_stock': 'on',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(RetourVente.objects.filter(vente=self.vente).count(), 0)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.quantite_disponible, 0)
