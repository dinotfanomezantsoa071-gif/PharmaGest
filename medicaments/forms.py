from django import forms
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from .models import Categorie, Medicament


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ['nom', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Antalgiques'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description facultative...'}),
        }


class MedicamentForm(forms.ModelForm):
    class Meta:
        model = Medicament
        fields = [
            'nom_commercial', 'denomination_generique', 'categorie',
            'forme_pharmaceutique', 'dosage', 'laboratoire',
            'code_barres', 'photo', 'prix_achat', 'prix_vente',
            'seuil_alerte', 'statut',
        ]
        widgets = {
            'nom_commercial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Doliprane'}),
            'denomination_generique': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Paracétamol'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'forme_pharmaceutique': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Comprimé, Sirop, Gélule...'}),
            'dosage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : 500 mg'}),
            'laboratoire': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du fabricant'}),
            'code_barres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code EAN / Code-barres unique'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'prix_achat': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'prix_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'seuil_alerte': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_code_barres(self):
        code = self.cleaned_data.get('code_barres')
        return code.strip() if code and code.strip() else None

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'size'):
            if photo.size > settings.MAX_UPLOAD_IMAGE_SIZE:
                raise forms.ValidationError("L'image dépasse la taille maximale autorisée (2 Mo).")
            try:
                img = Image.open(photo)
                img.verify()
                photo.seek(0)
            except (UnidentifiedImageError, Exception):
                raise forms.ValidationError("Le fichier envoyé n'est pas une image valide.")
        return photo

    def clean(self):
        cleaned_data = super().clean()
        prix_achat = cleaned_data.get('prix_achat')
        prix_vente = cleaned_data.get('prix_vente')
        if prix_achat and prix_vente and prix_vente < prix_achat:
            self.add_error('prix_vente', "Le prix de vente ne peut pas être inférieur au prix d'achat.")
        return cleaned_data