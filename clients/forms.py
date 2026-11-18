from django import forms
from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['nom', 'telephone', 'email', 'adresse', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du client'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone (facultatif)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'E-mail (facultatif)'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse (facultative)'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }