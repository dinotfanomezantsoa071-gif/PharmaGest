from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from utilisateurs.management.backup import create_database_backup, default_backup_path
from ventes.models import LigneVente, Paiement, Vente


class Command(BaseCommand):
    help = 'Ajoute des médicaments, fournisseurs, clients, achats et ventes de démonstration.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirme l’ajout des données à la base active après sa sauvegarde.',
        )
        parser.add_argument(
            '--ajouter-stock-faible',
            action='store_true',
            help='Met un médicament DEMO sous son seuil et enregistre le mouvement de stock.',
        )
        parser.add_argument(
            '--ajouter-lot-perime',
            action='store_true',
            help='Ajoute un lot DEMO périmé avec du stock et enregistre son entrée.',
        )

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Cette commande de démonstration est prévue pour SQLite.')

        if options['ajouter_stock_faible']:
            self._add_low_demo_stock(database)
            return

        if options['ajouter_lot_perime']:
            self._add_expired_demo_lot(database)
            return

        if self._demo_data_exists():
            raise CommandError(
                'Des données DEMO existent déjà. Aucune nouvelle donnée n’a été ajoutée.'
            )

        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'Aucune donnée ajoutée. La base active sera modifiée si vous relancez '
                    'cette commande avec --confirm.'
                )
            )
            self.stdout.write(
                'La confirmation crée une sauvegarde, puis ajoute 3 fournisseurs, 3 catégories, '
                '6 médicaments, 3 clients, 6 commandes réceptionnées et 3 ventes.'
            )
            return

        user = get_user_model().objects.filter(is_active=True).order_by('pk').first()
        if user is None:
            raise CommandError(
                'Aucun utilisateur actif. Créez d’abord un compte avec createsuperuser.'
            )

        backup_path = create_database_backup(
            database['NAME'],
            default_backup_path(settings.BASE_DIR),
        )
        self.stdout.write(f'Sauvegarde créée : {backup_path}')
        with transaction.atomic():
            self._create_demo_data(user)

        self.stdout.write(self.style.SUCCESS('Données de démonstration ajoutées.'))
        self.stdout.write(f'Sauvegarde de la base : {backup_path}')
        self.stdout.write(
            'Les données portent le préfixe DEMO et apparaissent dans le tableau de bord '
            'et les rapports.'
        )

    @staticmethod
    def _demo_data_exists():
        return (
            Categorie.objects.filter(nom__startswith='DEMO - ').exists()
            or Medicament.objects.filter(nom_commercial__startswith='DEMO - ').exists()
            or Fournisseur.objects.filter(raison_sociale__startswith='DEMO - ').exists()
            or Client.objects.filter(nom__startswith='DEMO - ').exists()
            or Vente.objects.filter(numero__startswith='DEMO-VNT-').exists()
        )

    def _add_low_demo_stock(self, database):
        medicine = Medicament.objects.filter(
            nom_commercial='DEMO - Paracetamol 500 mg',
            statut=Medicament.STATUT_ACTIF,
        ).first()
        if medicine is None:
            raise CommandError(
                'Médicament de démonstration introuvable. '
                'Ajoutez d’abord les données avec --confirm.'
            )
        lot = LotStock.objects.filter(
            medicament=medicine,
            numero_lot='DEMO-LOT-001',
            bloque=False,
        ).first()
        if lot is None:
            raise CommandError('Lot de démonstration introuvable.')

        target_quantity = min(2, medicine.seuil_alerte)
        if lot.quantite_disponible <= target_quantity:
            self.stdout.write('Le stock DEMO est déjà sous le seuil.')
            return

        user = get_user_model().objects.filter(is_active=True).order_by('pk').first()
        if user is None:
            raise CommandError(
                'Aucun utilisateur actif. Créez d’abord un compte avec createsuperuser.'
            )

        backup_path = create_database_backup(
            database['NAME'],
            default_backup_path(settings.BASE_DIR),
        )
        self.stdout.write(f'Sauvegarde créée : {backup_path}')
        with transaction.atomic():
            lot = LotStock.objects.select_for_update().get(pk=lot.pk)
            if lot.quantite_disponible > target_quantity:
                before = lot.quantite_disponible
                lot.quantite_disponible = target_quantity
                lot.save(update_fields=['quantite_disponible'])
                MouvementStock.objects.create(
                    medicament=medicine,
                    lot=lot,
                    utilisateur=user,
                    type_mouvement=MouvementStock.TYPE_AJUSTEMENT,
                    quantite=target_quantity - before,
                    stock_avant=before,
                    stock_apres=target_quantity,
                    reference_document='DEMO-AJUST-STOCK-001',
                    motif='Ajustement DEMO : stock sous le seuil',
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Stock DEMO ajusté à {target_quantity} unités '
                f'(seuil : {medicine.seuil_alerte}).'
            )
        )
        self.stdout.write(f'Sauvegarde de la base : {backup_path}')

    def _add_expired_demo_lot(self, database):
        medicine = Medicament.objects.filter(
            nom_commercial='DEMO - Ibuprofene 200 mg',
            statut=Medicament.STATUT_ACTIF,
        ).first()
        if medicine is None:
            raise CommandError(
                'Médicament de démonstration introuvable. '
                'Ajoutez d’abord les données avec --confirm.'
            )
        lot_number = 'DEMO-LOT-EXPIRE-001'
        if LotStock.objects.filter(medicament=medicine, numero_lot=lot_number).exists():
            self.stdout.write('Le lot DEMO périmé existe déjà. Aucun changement effectué.')
            return

        user = get_user_model().objects.filter(is_active=True).order_by('pk').first()
        if user is None:
            raise CommandError(
                'Aucun utilisateur actif. Créez d’abord un compte avec createsuperuser.'
            )

        quantity = 4
        backup_path = create_database_backup(
            database['NAME'],
            default_backup_path(settings.BASE_DIR),
        )
        self.stdout.write(f'Sauvegarde créée : {backup_path}')
        with transaction.atomic():
            lot = LotStock.objects.create(
                medicament=medicine,
                numero_lot=lot_number,
                date_peremption=timezone.localdate() - timedelta(days=1),
                quantite_initiale=quantity,
                quantite_disponible=quantity,
            )
            MouvementStock.objects.create(
                medicament=medicine,
                lot=lot,
                utilisateur=user,
                type_mouvement=MouvementStock.TYPE_ENTREE,
                quantite=quantity,
                stock_avant=0,
                stock_apres=quantity,
                reference_document='DEMO-EXPIRE-001',
                motif='Entrée de lot périmé de démonstration',
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Lot DEMO périmé ajouté : {medicine.nom_commercial}, '
                f'{quantity} unités (périmé depuis hier).'
            )
        )
        self.stdout.write(f'Sauvegarde de la base : {backup_path}')

    @staticmethod
    def _create_demo_data(user):
        today = timezone.localdate()
        suppliers = [
            Fournisseur.objects.create(
                raison_sociale=f'DEMO - Fournisseur {number}',
                telephone='000000000',
                email=f'fournisseur{number}@demo.invalid',
                contact_principal='Compte de démonstration',
            )
            for number in range(1, 4)
        ]
        categories = [
            Categorie.objects.create(nom=f'DEMO - {name}')
            for name in ('Antalgiques', 'Rhume', 'Vitamines')
        ]
        clients = [
            Client.objects.create(nom=f'DEMO - Client {number}')
            for number in range(1, 4)
        ]

        products = [
            ('DEMO - Paracetamol 500 mg', 0, 'Comprime', '500 mg', 1800, 2500),
            ('DEMO - Ibuprofene 200 mg', 0, 'Comprime', '200 mg', 2200, 3200),
            ('DEMO - Sirop contre le rhume', 1, 'Sirop', '100 ml', 3500, 5000),
            ('DEMO - Pastilles pour la gorge', 1, 'Pastille', 'boite', 2000, 3000),
            ('DEMO - Vitamine C', 2, 'Comprime', '500 mg', 1500, 2300),
            ('DEMO - Multivitamines', 2, 'Gelule', '30 gelules', 4000, 6000),
        ]
        medicines = [
            Medicament.objects.create(
                nom_commercial=name,
                denomination_generique=name.removeprefix('DEMO - '),
                categorie=categories[category_index],
                forme_pharmaceutique=form,
                dosage=dosage,
                laboratoire='DEMO - Laboratoire',
                prix_achat=Decimal(purchase_price),
                prix_vente=Decimal(sale_price),
                seuil_alerte=5,
            )
            for name, category_index, form, dosage, purchase_price, sale_price in products
        ]

        stock_lots = []
        for index, medicine in enumerate(medicines):
            supplier = suppliers[index // 2]
            purchase_order = CommandeAchat.objects.create(
                numero=f'DEMO-CMD-{index + 1:03d}',
                fournisseur=supplier,
                utilisateur=user,
                statut=CommandeAchat.STATUT_COMMANDEE,
                notes='Données de démonstration PharmaGest.',
            )
            purchase_line = LigneAchat.objects.create(
                commande=purchase_order,
                medicament=medicine,
                quantite_commandee=30,
                prix_unitaire_achat=medicine.prix_achat,
            )
            purchase_order.montant_total = purchase_line.sous_total
            purchase_order.save(update_fields=['montant_total'])

            reception = ReceptionAchat.objects.create(
                numero=f'DEMO-REC-{index + 1:03d}',
                commande=purchase_order,
                utilisateur=user,
                observations='Réception de démonstration.',
                validee=True,
            )
            lot = LotStock.objects.create(
                medicament=medicine,
                numero_lot=f'DEMO-LOT-{index + 1:03d}',
                date_peremption=today + timedelta(days=365),
                quantite_initiale=30,
                quantite_disponible=30,
            )
            LigneReception.objects.create(
                reception=reception,
                ligne_achat=purchase_line,
                lot=lot,
                quantite_recue=30,
                numero_lot=lot.numero_lot,
                date_peremption=lot.date_peremption,
            )
            purchase_line.quantite_recue = 30
            purchase_line.save(update_fields=['quantite_recue'])
            purchase_order.statut = CommandeAchat.STATUT_RECUE
            purchase_order.save(update_fields=['statut'])
            MouvementStock.objects.create(
                medicament=medicine,
                lot=lot,
                utilisateur=user,
                type_mouvement=MouvementStock.TYPE_ENTREE,
                quantite=30,
                stock_avant=0,
                stock_apres=30,
                reference_document=reception.numero,
                motif='Réception de démonstration',
            )
            stock_lots.append(lot)

        for index in range(3):
            medicine = medicines[index * 2]
            lot = stock_lots[index * 2]
            quantity = index + 1
            total = medicine.prix_vente * quantity
            sale = Vente.objects.create(
                numero=f'DEMO-VNT-{index + 1:03d}',
                client=clients[index],
                utilisateur=user,
                statut=Vente.STATUT_VALIDEE,
                montant_total=total,
                montant_paye=total,
                notes='Vente de démonstration PharmaGest.',
            )
            LigneVente.objects.create(
                vente=sale,
                medicament=medicine,
                lot=lot,
                quantite=quantity,
                prix_unitaire_applique=medicine.prix_vente,
            )
            stock_before = lot.quantite_disponible
            lot.quantite_disponible -= quantity
            lot.save(update_fields=['quantite_disponible'])
            MouvementStock.objects.create(
                medicament=medicine,
                lot=lot,
                utilisateur=user,
                type_mouvement=MouvementStock.TYPE_SORTIE,
                quantite=-quantity,
                stock_avant=stock_before,
                stock_apres=lot.quantite_disponible,
                reference_document=sale.numero,
                motif='Vente de démonstration',
            )
            Paiement.objects.create(
                vente=sale,
                mode_paiement=Paiement.MODE_ESPECES,
                montant=total,
                statut=Paiement.STATUT_CONFIRME,
                utilisateur=user,
            )
