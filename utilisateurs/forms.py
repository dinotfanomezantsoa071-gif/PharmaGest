from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group

from .models import Utilisateur


ROLE_GROUPS = dict(Utilisateur.ROLE_CHOICES)


class UtilisateurForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(
        label='Permissions de rôles supplémentaires',
        choices=Utilisateur.ROLE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Les permissions des profils sélectionnés sont cumulées avec le rôle principal.',
    )
    mot_de_passe = forms.CharField(
        label='Mot de passe',
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Obligatoire à la création. Laisser vide pour conserver le mot de passe actuel.',
    )

    class Meta:
        model = Utilisateur
        fields = ['username', 'first_name', 'last_name', 'email', 'telephone', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.is_create = kwargs.pop('is_create', False)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            current_roles = [
                role for role, group_name in ROLE_GROUPS.items()
                if self.instance.groups.filter(name=group_name).exists()
            ]
            self.fields['roles'].initial = current_roles or [self.instance.role]
        if self.is_create:
            self.fields['mot_de_passe'].required = True
        self.fields['is_active'].label = 'Compte actif'
        self.order_fields([
            'username', 'first_name', 'last_name', 'email', 'telephone',
            'role', 'roles', 'is_active', 'mot_de_passe',
        ])

    def clean_mot_de_passe(self):
        password = self.cleaned_data.get('mot_de_passe')
        if password:
            password_validation.validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('mot_de_passe')
        if password:
            user.set_password(password)
        if commit:
            preserved_groups = (
                list(user.groups.exclude(name__in=ROLE_GROUPS.values()))
                if user.pk else []
            )
            user.save()
            role_values = set(self.cleaned_data.get('roles', []))
            role_values.add(user.role)
            role_groups = [
                Group.objects.get_or_create(name=ROLE_GROUPS[role])[0]
                for role in role_values
            ]
            user.groups.set([*preserved_groups, *role_groups])
        return user
