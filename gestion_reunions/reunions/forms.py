from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Reunion, PresenceRequest, CompteRendu, CustomUser, AgendaPoint, Invitation, Diligence, DiligenceComment
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import localtime

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    role = forms.ChoiceField(choices=CustomUser.ROLES, required=True)
    phone = forms.CharField(max_length=15, required=False)
    direction = forms.CharField(max_length=100, required=False, label="Direction / Service")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'phone', 'direction', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Styling des champs
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label
            })

class ReunionForm(forms.ModelForm):
    date_debut = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
        }),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'],
        label="Date de début",
    )
    date_fin = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
        }),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'],
        label="Date de fin",
    )
    
    class Meta:
        model = Reunion
        fields = ['titre', 'description', 'date_debut', 'date_fin', 'lieu', 'secretaire', 'status', 'rappels_actives']
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Titre de la réunion'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'Description de la réunion'
            }),
            'lieu': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Lieu de la réunion'
            }),
            'secretaire': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'rappels_actives': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['secretaire'].queryset = CustomUser.objects.filter(role='secretary')
        self.fields['secretaire'].empty_label = "Sélectionner un secrétaire"
        self.fields['secretaire'].required = False

        # Pré-remplir les dates au format datetime-local (YYYY-MM-DDTHH:MM)
        # quand on édite une réunion existante
        if self.instance and self.instance.pk:
            if self.instance.date_debut:
                self.initial['date_debut'] = localtime(self.instance.date_debut).strftime('%Y-%m-%dT%H:%M')
            if self.instance.date_fin:
                self.initial['date_fin'] = localtime(self.instance.date_fin).strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin:
            if date_debut >= date_fin:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")

            # Vérifier la date dans le passé seulement à la création
            is_new = not (self.instance and self.instance.pk)
            if is_new:
                from django.utils.timezone import make_aware, is_naive
                date_debut_aware = make_aware(date_debut) if is_naive(date_debut) else date_debut
                if date_debut_aware < timezone.now():
                    raise ValidationError("La date de début ne peut pas être dans le passé.")

        return cleaned_data
    
class CompteRenduForm(forms.ModelForm):
    envoyer_automatiquement = forms.BooleanField(
        required=False,
        initial=True,
        label="Envoyer automatiquement aux participants",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = CompteRendu
        fields = ['titre', 'fichier']
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du compte-rendu'
            }),
            'fichier': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt'
            })
        }
    
    def clean_fichier(self):
        fichier = self.cleaned_data['fichier']
        if fichier:
            # Vérifier la taille du fichier (max 10MB)
            if fichier.size > 10 * 1024 * 1024:
                raise ValidationError("Le fichier ne peut pas dépasser 10MB.")
            
            # Vérifier l'extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']
            if not any(fichier.name.lower().endswith(ext) for ext in allowed_extensions):
                raise ValidationError("Format de fichier non supporté. Utilisez PDF, DOC, DOCX ou TXT.")
        
        return fichier

class SearchForm(forms.Form):

    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher une réunion...',
            'autocomplete': 'off'
        })
    )
    
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label="Date de début"
    )
    
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label="Date de fin"
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les statuts')] + list(Reunion.STATUS_CHOICES),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class PresenceDirectForm(forms.Form):
    """Formulaire pour confirmation directe (non-ARTCI) - ORDRE REQUIS"""
    
    nom = forms.CharField(
        max_length=100,
        required=True,
        label="Nom *",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom de famille'
        })
    )
    
    prenom = forms.CharField(
        max_length=100,
        required=True,
        label="Prénom *",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre prénom'
        })
    )
    
    organisation = forms.CharField(
        max_length=200,
        required=True,
        label="Structure/Organisation *",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre entreprise/organisation'
        })
    )
    
    fonction = forms.CharField(
        max_length=200,
        required=True,
        label="Fonction *",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre poste/fonction'
        })
    )
    
    contact = forms.CharField(
        max_length=20,
        required=True,
        label="Contact/Téléphone *",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre numéro de téléphone'
        })
    )
    
    email = forms.EmailField(
        label="Adresse email *",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre.email@example.com'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if email.endswith('@artci.ci'):
            raise ValidationError("Les emails ARTCI doivent passer par la validation email.")
        return email
    
    def clean_contact(self):
        contact = self.cleaned_data['contact']
        # Validation basique du numéro de téléphone
        import re
        if not re.match(r'^[\d\s\-\+\(\)\.]+$', contact):
            raise ValidationError("Format de numéro de téléphone invalide.")
        return contact

class PresenceForm(forms.Form):
    """Formulaire initial pour saisir l'email"""
    email = forms.EmailField(
        label="Adresse email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre.email@example.com',
            'required': True
        }),
        help_text="Les emails @artci.ci nécessitent une validation par email. Les autres emails sont confirmés directement."
    )
    
    """
    consent = forms.BooleanField(
        label="J'accepte l'utilisation de mes données pour cette réunion",
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    """
    
    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        return email

class PresenceValidationForm(forms.Form):
    """Formulaire de validation pour emails ARTCI (optionnel)"""
    nom = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom (optionnel)'
        })
    )
    prenom = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre prénom (optionnel)'
        })
    )
    organisation = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre service/direction (optionnel)'
        })
    )
    fonction = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre fonction (optionnel)'
        })
    )
    contact = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre téléphone (optionnel)'
        })
    )


class PresenceARTCIFallbackForm(PresenceDirectForm):
    """
    Formulaire pour les agents ARTCI non trouvés dans l'Active Directory.
    Identique à PresenceDirectForm mais autorise les emails @artci.ci.
    """

    def clean_email(self):
        return self.cleaned_data['email'].lower()

    def clean_contact(self):
        contact = self.cleaned_data['contact']
        import re
        if not re.match(r'^[\d\s\-\+\(\)\.]+$', contact):
            raise ValidationError("Format de numéro de téléphone invalide.")
        return contact


class AgendaPointForm(forms.ModelForm):
    class Meta:
        model = AgendaPoint
        fields = ['ordre', 'titre', 'description', 'duree_minutes', 'responsable_interne', 'responsable_externe', 'notes_seance']
        widgets = {
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'titre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre du point'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description optionnelle'}),
            'duree_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Ex: 30'}),
            'responsable_interne': forms.Select(attrs={'class': 'form-control'}),
            'responsable_externe': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du responsable externe'}),
            'notes_seance': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Notes prises durant la réunion sur ce point…'}),
        }
        labels = {
            'duree_minutes': 'Durée',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['responsable_interne'].queryset = CustomUser.objects.all().order_by('last_name', 'first_name')
        self.fields['responsable_interne'].empty_label = "— Aucun —"
        self.fields['responsable_interne'].required = False


class InvitationBulkForm(forms.Form):
    emails = forms.CharField(
        label="Adresses email",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Un email par ligne, ou séparés par des virgules\nex: jean.dupont@example.com\nmarie.martin@example.com',
        }),
        help_text="Saisissez un ou plusieurs emails (un par ligne ou séparés par des virgules)."
    )

    def clean_emails(self):
        import re
        raw = self.cleaned_data['emails']
        # Normaliser : remplacer virgules et espaces multiples par retours à la ligne
        entries = re.split(r'[,\n\r]+', raw)
        valid_emails = []
        invalid = []
        seen = set()
        for entry in entries:
            email = entry.strip().lower()
            if not email:
                continue
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                invalid.append(email)
            elif email not in seen:
                valid_emails.append(email)
                seen.add(email)
        if invalid:
            raise ValidationError(f"Adresses invalides : {', '.join(invalid)}")
        if not valid_emails:
            raise ValidationError("Veuillez saisir au moins une adresse email valide.")
        return valid_emails


class DiligenceForm(forms.ModelForm):
    class Meta:
        model = Diligence
        fields = ['titre', 'description', 'responsable_interne', 'responsable_externe', 'echeance', 'priorite']
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Intitulé de la diligence',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description détaillée (optionnel)',
            }),
            'responsable_interne': forms.Select(attrs={'class': 'form-control'}),
            'responsable_externe': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du responsable externe',
            }),
            'echeance': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'priorite': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['responsable_interne'].queryset = CustomUser.objects.all().order_by('last_name', 'first_name')
        self.fields['responsable_interne'].empty_label = "— Aucun —"
        self.fields['responsable_interne'].required = False


class DiligenceCommentForm(forms.Form):
    contenu = forms.CharField(
        label="Commentaire",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Ajouter un commentaire (optionnel)',
        }),
    )
    nouveau_status = forms.ChoiceField(
        label="Changer le statut",
        choices=[('', '— Conserver le statut actuel —')] + Diligence.STATUS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )