from django import forms
from .models import Fournisseur


class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = [
            'raison_sociale', 'telephone', 'email',
            'numero_fiscal', 'contact_principal', 'adresse', 'actif',
        ]
        widgets = {
            'raison_sociale': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom ou raison sociale'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : +261 34 00 000 00'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@fournisseur.mg'}),
            'numero_fiscal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIF / STAT'}),
            'contact_principal': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du responsable'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse complète...'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }