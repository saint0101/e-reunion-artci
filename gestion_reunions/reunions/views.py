from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Reunion, PresenceRequest, CompteRendu, CustomUser
from .forms import ReunionForm, PresenceForm, CompteRenduForm
from .utils import generate_presence_report, send_compte_rendu_email
import json
from email.utils import formataddr




# Dashboard Views
@login_required
def dashboard(request):
    if request.user.role == 'admin':
        return admin_dashboard(request)
    elif request.user.role == 'secretary':
        return secretary_dashboard(request)
    else:
        return participant_dashboard(request)

@login_required
def admin_dashboard(request):
    reunions_stats = {
        'total': Reunion.objects.count(),
        'planned': Reunion.objects.filter(status='planned').count(),
        'ongoing': Reunion.objects.filter(status='ongoing').count(),
        'finished': Reunion.objects.filter(status='finished').count(),
    }
    
    recent_reunions = Reunion.objects.order_by('-created_at')[:5]
    users_stats = CustomUser.objects.values('role').annotate(count=Count('id'))
    
    context = {
        'reunions_stats': reunions_stats,
        'recent_reunions': recent_reunions,
        'users_stats': users_stats,
    }
    return render(request, 'reunions/admin_dashboard.html', context)

@login_required
def secretary_dashboard(request):
    mes_reunions = Reunion.objects.filter(secretaire=request.user)
    reunions_sans_cr = mes_reunions.filter(comptes_rendus__isnull=True, status='finished')
    
    context = {
        'mes_reunions': mes_reunions,
        'reunions_sans_cr': reunions_sans_cr,
        'total_reunions': mes_reunions.count(),
    }
    return render(request, 'reunions/secretary_dashboard.html', context)

@login_required
def participant_dashboard(request):
    mes_presences = PresenceRequest.objects.filter(
        email=request.user.email, 
        status='confirmed'
    )
    
    context = {
        'mes_presences': mes_presences,
        'total_presences': mes_presences.count(),
    }
    return render(request, 'reunions/participant_dashboard.html', context)

# Reunion Views
class ReunionListView(LoginRequiredMixin, ListView):
    model = Reunion
    template_name = 'reunions/reunion_list.html'
    context_object_name = 'reunions'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Reunion.objects.all()
        if self.request.user.role == 'secretary':
            queryset = queryset.filter(secretaire=self.request.user)
        return queryset

class ReunionDetailView(LoginRequiredMixin, DetailView):
    model = Reunion
    template_name = 'reunions/reunion_detail.html'
    context_object_name = 'reunion'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['presences'] = self.object.presence_requests.filter(status='confirmed')
        context['comptes_rendus'] = self.object.comptes_rendus.all()
        return context

@login_required
def reunion_create(request):
    if request.user.role not in ['admin', 'secretary']:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ReunionForm(request.POST)
        if form.is_valid():
            reunion = form.save(commit=False)
            reunion.organisateur = request.user
            reunion.save()
            messages.success(request, 'Réunion créée avec succès!')
            return redirect('reunion_detail', pk=reunion.pk)
    else:
        form = ReunionForm()
    
    return render(request, 'reunions/reunion_form.html', {'form': form})

@login_required
def reunion_update(request, pk):
    reunion = get_object_or_404(Reunion, pk=pk)
    
    if request.user.role not in ['admin'] and reunion.organisateur != request.user:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=pk)
    
    if request.method == 'POST':
        form = ReunionForm(request.POST, instance=reunion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Réunion mise à jour avec succès!')
            return redirect('reunion_detail', pk=pk)
    else:
        form = ReunionForm(instance=reunion)
    
    return render(request, 'reunions/reunion_form.html', {'form': form, 'reunion': reunion})

@login_required
def reunion_delete(request, pk):
    reunion = get_object_or_404(Reunion, pk=pk)
    
    if request.user.role not in ['admin'] and reunion.organisateur != request.user:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=pk)
    
    if request.method == 'POST':
        reunion.delete()
        messages.success(request, 'Réunion supprimée avec succès!')
        return redirect('reunion_list')
    
    return render(request, 'reunions/reunion_confirm_delete.html', {'reunion': reunion})

# Presence Views
def presence_qr_redirect(request, uuid):
    """Vue appelée quand on scanne le QR code"""
    try:
        reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)
        return render(request, 'reunions/presence_consent.html', {'reunion': reunion})
    except:
        messages.error(request, "QR Code invalide ou réunion introuvable.")
        return redirect('dashboard')

def is_artci_email(email):
    """Vérifie si l'email appartient au domaine ARTCI"""
    return email.lower().endswith('@artci.ci')

def presence_form(request, uuid):
    """Formulaire de demande de présence après consentement - Version améliorée"""
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)
    
    if request.method == 'POST':
        form = PresenceForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            # Vérifier si déjà enregistré
            existing_request = PresenceRequest.objects.filter(
                reunion=reunion, email=email
            ).first()
            
            if existing_request:
                messages.info(request, "Vous êtes déjà enregistré pour cette réunion.")
                return redirect('presence_status', token=existing_request.validation_token)
            
            # Créer nouvelle demande
            presence_request = PresenceRequest.objects.create(
                reunion=reunion,
                email=email,
                consent_given=True
            )
            
            # Traitement différencié selon le domaine email
            if is_artci_email(email):
                # Email ARTCI : Validation directe sans formulaire
                return handle_artci_email_validation(request, presence_request)
            else:
                # Autre email : Processus complet avec validation par email
                return handle_external_email_validation(request, presence_request)
    else:
        form = PresenceForm()
    
    return render(request, 'reunions/presence_form.html', {
        'form': form,
        'reunion': reunion
    })

def handle_artci_email_validation(request, presence_request):
    """Gestion spéciale pour les emails @artci.ci - Validation directe"""
    
    # Envoyer email de validation directe (sans formulaire)
    success = send_artci_validation_email(presence_request)
    
    if success:
        messages.success(request, 
            "Email ARTCI détecté ! Un lien de validation directe vous a été envoyé.")
    else:
        messages.error(request, 
            "Erreur lors de l'envoi de l'email de validation.")
    
    return render(request, 'reunions/presence_email_sent_artci.html', {
        'reunion': presence_request.reunion,
        'email': presence_request.email,
        'is_artci': True
    })

def handle_external_email_validation(request, presence_request):
    """Gestion pour les emails externes - Processus complet"""
    
    # Envoyer email de validation avec formulaire
    success = send_validation_email(presence_request)
    
    if success:
        messages.success(request, 
            "Email de validation envoyé ! Vérifiez votre boîte mail.")
    else:
        messages.error(request, 
            "Erreur lors de l'envoi de l'email de validation.")
    
    return render(request, 'reunions/presence_email_sent.html', {
        'reunion': presence_request.reunion,
        'email': presence_request.email,
        'is_artci': False
    })


def presence_direct_confirm(request, uuid):
    """Confirmation directe pour les emails non-ARTCI"""
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)
    
    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        nom = request.POST.get('nom', '').strip()
        prenom = request.POST.get('prenom', '').strip()
        organisation = request.POST.get('organisation', '').strip()
        
        # Validation
        if not email:
            messages.error(request, "Email requis.")
            return redirect('presence_qr_redirect', uuid=uuid)
        
        if email.endswith('@artci.ci'):
            messages.error(request, "Les emails ARTCI doivent passer par la validation email.")
            return redirect('presence_qr_redirect', uuid=uuid)
        
        # Vérifier si déjà enregistré
        existing_request = PresenceRequest.objects.filter(
            reunion=reunion, email=email
        ).first()
        
        if existing_request:
            messages.info(request, "Vous êtes déjà enregistré pour cette réunion.")
            return render(request, 'reunions/presence_confirmed.html', {
                'reunion': reunion,
                'presence_request': existing_request
            })
        
        # Créer et confirmer directement
        presence_request = PresenceRequest.objects.create(
            reunion=reunion,
            email=email,
            nom=nom,
            prenom=prenom,
            organisation=organisation,
            consent_given=True,
            status='confirmed',  # Confirmé directement
            confirmed_at=timezone.now()
        )
        
        messages.success(request, "Votre présence a été confirmée avec succès !")
        
        return render(request, 'reunions/presence_confirmed.html', {
            'reunion': reunion,
            'presence_request': presence_request,
            'direct_confirmation': True
        })
    
    return redirect('presence_qr_redirect', uuid=uuid)


def presence_validation(request, token):
    """Validation de la présence via email - ARTCI"""
    presence_request = get_object_or_404(PresenceRequest, validation_token=token)
    
    # Vérifier si c'est un email ARTCI
    is_artci = is_artci_email(presence_request.email)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirm':
            presence_request.status = 'confirmed'
            presence_request.confirmed_at = timezone.now()
            
            """
            if is_artci:
                # Pour ARTCI : Juste confirmer sans données supplémentaires
                # Extraire automatiquement nom/prénom depuis l'email si possible
                email_prefix = presence_request.email.split('@')[0]
                if '.' in email_prefix:
                    parts = email_prefix.split('.')
                    presence_request.prenom = parts[0].capitalize()
                    presence_request.nom = parts[1].capitalize() if len(parts) > 1 else ''
                presence_request.organisation = 'ARTCI'

            """
            if is_artci:
                # Pour ARTCI : Juste confirmer sans données supplémentaires

                def format_nom(nom):
                    """Met en majuscule la première lettre de chaque partie du nom (apostrophes, tirets, etc.)"""
                    nom = nom.replace("'", "' ")
                    return '-'.join(part.capitalize() for part in nom.split('-')).replace("' ", "'")

                email_prefix = presence_request.email.split('@')[0]

                if '.' in email_prefix:
                    parts = email_prefix.split('.')
                    presence_request.prenom = format_nom(parts[1]) if len(parts) > 1 else ''
                    presence_request.nom = format_nom(parts[0])
                else:
                    presence_request.prenom = format_nom(email_prefix)
                    presence_request.nom = ''

                presence_request.organisation = 'ARTCI'
                            
                messages.success(request, 
                    "Présence confirmée automatiquement ! Bienvenue à la réunion.")
            else:
                # Pour externes : Récupérer les infos du formulaire
                presence_request.nom = request.POST.get('nom', '')
                presence_request.prenom = request.POST.get('prenom', '')
                presence_request.organisation = request.POST.get('organisation', '')
                
                messages.success(request, 
                    "Présence confirmée avec succès ! Merci d'avoir complété vos informations.")
            
            presence_request.save()
            
        elif action == 'cancel':
            presence_request.status = 'cancelled'
            presence_request.save()
            messages.info(request, "Présence annulée.")
    
    return render(request, 'reunions/presence_validation.html', {
        'presence_request': presence_request,
        'is_artci': is_artci
    })


def build_validation_url_artci(token):
    """
    Construit l'URL de validation à envoyer par email.
    Priorise SITE_URL défini dans .env, sinon utilise le premier host autorisé.
    """
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'

    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        base_url = site_url
    else:
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        host = allowed_hosts[0] if allowed_hosts and allowed_hosts[0] != '*' else '196.216.227.105:80'
        base_url = f"{protocol}://{host}"

    return f"{base_url}/validation/{token}/"


def send_artci_validation_email(presence_request):
    """
    Envoie un email contenant un lien de validation de présence à une réunion.
    """
    subject = f"Validation de présence - {presence_request.reunion.titre}"
    validation_url = build_validation_url_artci(presence_request.validation_token)

    print(f"🔗 URL de validation générée: {validation_url}")

    # Contexte du template
    context = {
        'presence_request': presence_request,
        'validation_url': validation_url,
        'reunion': presence_request.reunion,
    }

    # Essayer de rendre le contenu HTML
    try:
        html_content = render_to_string('reunions/email_validation.html', context)
    except Exception as e:
        print(f"⚠️ Erreur lors du rendu du template HTML : {e}")
        html_content = None

    # Contenu texte brut (fallback)
    text_content = f"""
Bonjour,

Vous avez demandé à confirmer votre présence à la réunion « {presence_request.reunion.titre} ».

📅 Date : {presence_request.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
📍 Lieu : {presence_request.reunion.lieu}
👤 Organisateur : {presence_request.reunion.organisateur.first_name} {presence_request.reunion.organisateur.last_name}

👉 Cliquez sur le lien suivant pour confirmer votre présence :
{validation_url}

(Si le lien ne fonctionne pas, copiez-le dans votre navigateur.)

En cas de désistement, vous pourrez également le signaler depuis cette page. 

Merci,
L’équipe de QR Meeting

---
Ce message est automatique. Merci de ne pas y répondre.
"""

    # Envoi de l'email
    try:
        print(f"📧 Envoi de l'email à : {presence_request.email}")
        print(f"📤 Backend configuré : {settings.EMAIL_BACKEND}")

        # Création du nom d'expéditeur avec formataddr
        sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=sender_name,
            #from_email=settings.DEFAULT_FROM_EMAIL,
            to=[presence_request.email]
        )

        if html_content:
            email.attach_alternative(html_content, "text/html")

        result = email.send()
        print(f"✅ Email envoyé avec succès à {presence_request.email} (résultat : {result})")
        return True

    except Exception as e:
        print(f"❌ Erreur lors de l’envoi de l’email : {e}")
        print(f"   Destinataire : {presence_request.email}")
        #print(f"   Expéditeur : {settings.DEFAULT_FROM_EMAIL}")
        print(f"   Expéditeur : {sender_name}")

        return False
    

def presence_status(request, token):
    """Affiche le statut d'une demande de présence"""
    presence_request = get_object_or_404(PresenceRequest, validation_token=token)
    return render(request, 'reunions/presence_status.html', {
        'presence_request': presence_request
    })

# Compte Rendu Views
@login_required
def compte_rendu_create(request, reunion_id):
    reunion = get_object_or_404(Reunion, pk=reunion_id)
    
    if request.user.role not in ['secretary', 'admin'] or reunion.secretaire != request.user:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_id)
    
    if request.method == 'POST':
        form = CompteRenduForm(request.POST, request.FILES)
        if form.is_valid():
            compte_rendu = form.save(commit=False)
            compte_rendu.reunion = reunion
            compte_rendu.cree_par = request.user
            compte_rendu.save()
            
            # Envoi automatique aux participants
            if form.cleaned_data.get('envoyer_automatiquement'):
                send_compte_rendu_email(compte_rendu)
                compte_rendu.envoye_automatiquement = True
                compte_rendu.save()
            
            messages.success(request, 'Compte-rendu ajouté avec succès!')
            return redirect('reunion_detail', pk=reunion_id)
    else:
        form = CompteRenduForm()
    
    return render(request, 'reunions/compte_rendu_form.html', {
        'form': form,
        'reunion': reunion
    })

@login_required
def compte_rendu_update(request, pk):
    compte_rendu = get_object_or_404(CompteRendu, pk=pk)
    
    if request.user.role not in ['secretary', 'admin'] or compte_rendu.cree_par != request.user:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=compte_rendu.reunion.pk)
    
    if request.method == 'POST':
        form = CompteRenduForm(request.POST, request.FILES, instance=compte_rendu)
        if form.is_valid():
            form.save()
            messages.success(request, 'Compte-rendu mis à jour avec succès!')
            return redirect('reunion_detail', pk=compte_rendu.reunion.pk)
    else:
        form = CompteRenduForm(instance=compte_rendu)
    
    return render(request, 'reunions/compte_rendu_form.html', {
        'form': form,
        'compte_rendu': compte_rendu,
        'reunion': compte_rendu.reunion
    })

@login_required
def compte_rendu_delete(request, pk):
    compte_rendu = get_object_or_404(CompteRendu, pk=pk)
    reunion_pk = compte_rendu.reunion.pk
    
    if request.user.role not in ['admin'] and compte_rendu.cree_par != request.user:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_pk)
    
    if request.method == 'POST':
        compte_rendu.delete()
        messages.success(request, 'Compte-rendu supprimé avec succès!')
        return redirect('reunion_detail', pk=reunion_pk)
    
    return render(request, 'reunions/compte_rendu_confirm_delete.html', {
        'compte_rendu': compte_rendu
    })

# Export Views
@login_required
def export_presence_list(request, reunion_id):
    reunion = get_object_or_404(Reunion, pk=reunion_id)
    
    if request.user.role not in ['admin', 'secretary']:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_id)
    
    format_type = request.GET.get('format', 'pdf')
    
    if format_type == 'pdf':
        return generate_presence_report(reunion, 'pdf')
    elif format_type == 'excel':
        return generate_presence_report(reunion, 'excel')
    elif format_type == 'word':
        return generate_presence_report(reunion, 'word')
    
    messages.error(request, "Format d'export non supporté.")
    return redirect('reunion_detail', pk=reunion_id)

@login_required
def export_data(request):
    """Export général des données"""
    if request.user.role != 'admin':
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    # Logic pour export général
    return render(request, 'reunions/export_data.html')

# Ajax Views
@login_required
def update_reunion_status(request, pk):
    """Mise à jour AJAX du statut d'une réunion"""
    if request.method == 'POST':
        reunion = get_object_or_404(Reunion, pk=pk)
        new_status = request.POST.get('status')
        
        if new_status in ['planned', 'ongoing', 'finished', 'cancelled']:
            reunion.status = new_status
            reunion.save()
            return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@login_required
def send_compte_rendu(request, pk):
    """Envoi AJAX d'un compte-rendu"""
    if request.method == 'POST':
        compte_rendu = get_object_or_404(CompteRendu, pk=pk)
        
        if send_compte_rendu_email(compte_rendu):
            compte_rendu.envoye_automatiquement = True
            compte_rendu.save()
            return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})


"""
def build_validation_url_ext(token):
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'

    if getattr(settings, 'SITE_URL', ''):
        base_url = settings.SITE_URL.rstrip('/')
    else:
        host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*' else 'localhost:8000'
        base_url = f"{protocol}://{host}"

    return f"{base_url}/validation/{token}/"
"""


def build_validation_url_ext(token):
    """
    Construit l'URL complète de validation pour les QR codes
    en forçant l'IP publique et le port correct.
    """
    # On force le protocole (http ou https)
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'

    # Si SITE_URL est défini, on l'utilise
    if getattr(settings, 'SITE_URL', ''):
        base_url = settings.SITE_URL.rstrip('/')
    else:
        # Sinon, on force l'IP publique et le port désiré
        public_ip = '196.216.227.105'
        port = '80'  # ou '80' si tu passes Gunicorn sur le port 80
        base_url = f"{protocol}://{public_ip}:{port}"

    return f"{base_url}/validation/{token}/"


# Fonction corrigée pour l'envoi d'emails de validation
def send_validation_email(presence_request):
    """Envoie l'e-mail de validation de présence pour un participant externe"""
    
    subject = f"Validation de présence - {presence_request.reunion.titre}"
    validation_url = build_validation_url_ext(presence_request.validation_token)

    print(f"🌐 URL de validation externe générée: {validation_url}")

    # Contexte du mail
    context = {
        'presence_request': presence_request,
        'validation_url': validation_url,
        'reunion': presence_request.reunion,
    }

    # Tentative de rendu HTML
    try:
        html_content = render_to_string('reunions/email_validation.html', context)
    except Exception as e:
        print(f"⚠️ Erreur lors du rendu du template HTML : {e}")
        html_content = None

    # Contenu texte brut
    text_content = f"""
Bonjour,

Vous avez demandé à confirmer votre présence à la réunion « {presence_request.reunion.titre} ».

Détails :
- Date : {presence_request.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
- Lieu : {presence_request.reunion.lieu}
- Organisateur : {presence_request.reunion.organisateur.first_name} {presence_request.reunion.organisateur.last_name}

Pour confirmer votre présence, cliquez sur ce lien :
{validation_url}

(Si le lien ne fonctionne pas, copiez-collez-le dans votre navigateur.)

Si vous ne souhaitez plus participer, vous pourrez l’indiquer sur la page de validation.

Merci,
L’équipe dE QR Meeting

---
Ce message a été généré automatiquement. Merci de ne pas y répondre.
"""

    # Envoi de l'e-mail
    try:
        print(f"📧 Envoi à : {presence_request.email}")

        sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))


        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=sender_name,
            to=[presence_request.email]
        )

        if html_content:
            email.attach_alternative(html_content, "text/html")

        result = email.send()

        print(f"✅ Email envoyé avec succès à {presence_request.email} (result: {result})")
        return True

    except Exception as e:
        print(f"❌ Erreur lors de l’envoi : {e}")
        print(f"   À : {presence_request.email}")
        print(f"   De : {settings.DEFAULT_FROM_EMAIL}")
        print(f"   De : {sender_name}")

        return False
    

# Fonction corrigée pour l'envoi des comptes-rendus
def send_compte_rendu_email_fixed(compte_rendu):
    """Envoie le compte-rendu aux participants confirmés"""
    reunion = compte_rendu.reunion
    participants = reunion.presence_requests.filter(status='confirmed')
    
    if not participants.exists():
        print("❌ Aucun participant confirmé pour l'envoi du compte-rendu")
        return False
    
    subject = f"Compte-rendu - {reunion.titre}"
    
    # URL de base
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'
    if hasattr(settings, 'SITE_URL') and settings.SITE_URL:
        base_url = settings.SITE_URL.rstrip('/')
    else:
        if hasattr(settings, 'ALLOWED_HOSTS') and settings.ALLOWED_HOSTS:
            host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS[0] != '*' else '192.168.100.13:8000'
        else:
            host = '192.168.100.13:8000'
        base_url = f"{protocol}://{host}"
    
    # Créer le contexte pour le template
    context = {
        'reunion': reunion,
        'compte_rendu': compte_rendu,
        'participant_count': participants.count(),
        'base_url': base_url,
    }
    
    # Rendu du template HTML
    try:
        html_content = render_to_string('reunions/email_compte_rendu.html', context)
    except Exception as e:
        print(f"⚠️ Erreur template HTML compte-rendu: {e}")
        html_content = None
    
    text_content = f"""
Bonjour,

Vous trouverez en pièce jointe le compte-rendu de la réunion "{reunion.titre}" 
qui s'est tenue le {reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}.

Détails de la réunion :
- Lieu : {reunion.lieu}
- Organisateur : {reunion.organisateur.first_name} {reunion.organisateur.last_name}
- Nombre de participants : {participants.count()}

Document joint : {compte_rendu.titre} (Version {compte_rendu.version})
Créé par : {compte_rendu.cree_par.first_name} {compte_rendu.cree_par.last_name}

Cordialement,
{compte_rendu.cree_par.first_name} {compte_rendu.cree_par.last_name}
Secrétaire de la réunion

---
Cet email a été envoyé automatiquement par QR Meeting.
"""
    
    # Préparer la liste des emails
    recipient_list = [p.email for p in participants]
    
    try:
        print(f"📧 Tentative d'envoi compte-rendu à {len(recipient_list)} participants")
        print(f"📤 Backend email: {settings.EMAIL_BACKEND}")

        # Création du nom d'expéditeur avec formataddr
        sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))

        
        # Créer l'email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=sender_name,
            to=recipient_list
        )
        
        # Attacher la version HTML si disponible
        if html_content:
            email.attach_alternative(html_content, "text/html")
        
        # Attacher le fichier du compte-rendu
        if compte_rendu.fichier:
            try:
                # Vérifier que le fichier existe
                if compte_rendu.fichier.name and hasattr(compte_rendu.fichier, 'path'):
                    import os
                    if os.path.exists(compte_rendu.fichier.path):
                        email.attach_file(compte_rendu.fichier.path)
                        print(f"📎 Fichier attaché: {compte_rendu.fichier.name}")
                    else:
                        print(f"⚠️ Fichier introuvable: {compte_rendu.fichier.path}")
                else:
                    print(f"⚠️ Aucun fichier associé au compte-rendu")
            except Exception as e:
                print(f"⚠️ Erreur lors de l'attachement du fichier: {e}")
        
        # Envoyer l'email
        result = email.send()
        
        print(f"✅ Compte-rendu envoyé avec succès à {len(recipient_list)} participants (result: {result})")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi du compte-rendu: {e}")
        print(f"   Destinataires: {recipient_list}")
        print(f"   From: {settings.DEFAULT_FROM_EMAIL}")
        return False


def debug_email_config(request):
    """Debug de la configuration email"""
    
    config_info = {
        'EMAIL_BACKEND': getattr(settings, 'EMAIL_BACKEND', 'Non défini'),
        'EMAIL_HOST': getattr(settings, 'EMAIL_HOST', 'Non défini'),
        'EMAIL_PORT': getattr(settings, 'EMAIL_PORT', 'Non défini'),
        'EMAIL_USE_TLS': getattr(settings, 'EMAIL_USE_TLS', 'Non défini'),
        'EMAIL_USE_SSL': getattr(settings, 'EMAIL_USE_SSL', 'Non défini'),
        'EMAIL_HOST_USER': getattr(settings, 'EMAIL_HOST_USER', 'Non défini'),
        'EMAIL_HOST_PASSWORD': '***masqué***' if getattr(settings, 'EMAIL_HOST_PASSWORD', None) else 'Non défini',
        'DEFAULT_FROM_EMAIL': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Non défini'),
        'EMAIL_TIMEOUT': getattr(settings, 'EMAIL_TIMEOUT', 'Non défini'),
    }
    
    # Variables d'environnement
    env_vars = {
        'EMAIL_HOST': os.environ.get('EMAIL_HOST', 'Non défini'),
        'EMAIL_PORT': os.environ.get('EMAIL_PORT', 'Non défini'),
        'EMAIL_HOST_USER': os.environ.get('EMAIL_HOST_USER', 'Non défini'),
        'EMAIL_HOST_PASSWORD': '***masqué***' if os.environ.get('EMAIL_HOST_PASSWORD') else 'Non défini',
        'DEFAULT_FROM_EMAIL': os.environ.get('DEFAULT_FROM_EMAIL', 'Non défini'),
    }
    
    return JsonResponse({
        'django_settings': config_info,
        'environment_variables': env_vars,
        'settings_file_path': settings.__file__ if hasattr(settings, '__file__') else 'Inconnu'
    }, json_dumps_params={'indent': 2})




# Modifiez temporairement votre fonction send_artci_validation_email pour plus de debug
def send_artci_validation_email_debug(presence_request):
    """Version debug de l'envoi d'email"""
    
    print("=== DEBUG EMAIL CONFIGURATION ===")
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"EMAIL_USE_SSL: {getattr(settings, 'EMAIL_USE_SSL', 'Non défini')}")
    print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"EMAIL_HOST_PASSWORD: {'***défini***' if settings.EMAIL_HOST_PASSWORD else '***NON DÉFINI***'}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print("=====================================")
    
    subject = f"Validation de présence - {presence_request.reunion.titre}"
    validation_url = build_validation_url_artci(presence_request.validation_token)

    print(f"🔗 URL de validation générée: {validation_url}")

    # Contexte du template
    context = {
        'presence_request': presence_request,
        'validation_url': validation_url,
        'reunion': presence_request.reunion,
    }

    # Essayer de rendre le contenu HTML
    try:
        html_content = render_to_string('reunions/email_validation.html', context)
    except Exception as e:
        print(f"⚠️ Erreur lors du rendu du template HTML : {e}")
        html_content = None

    # Contenu texte brut (fallback)
    text_content = f"""
Bonjour,

Vous avez demandé à confirmer votre présence à la réunion « {presence_request.reunion.titre} ».

📅 Date : {presence_request.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
📍 Lieu : {presence_request.reunion.lieu}
👤 Organisateur : {presence_request.reunion.organisateur.first_name} {presence_request.reunion.organisateur.last_name}

👉 Cliquez sur le lien suivant pour confirmer votre présence :
{validation_url}

(Si le lien ne fonctionne pas, copiez-le dans votre navigateur.)

En cas de désistement, vous pourrez également le signaler depuis cette page.

Merci,
L'équipe de QR Meeting

---
Ce message est automatique. Merci de ne pas y répondre.
"""

    # Test de connexion SMTP avant envoi
    import smtplib
    try:
        print("🔗 Test de connexion SMTP...")
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.quit()
        print("✅ Connexion SMTP réussie")
    except Exception as smtp_error:
        print(f"❌ Erreur de connexion SMTP : {smtp_error}")
        return False

    # Envoi de l'email
    try:
        print(f"📧 Envoi de l'email à : {presence_request.email}")
        print(f"📤 Backend configuré : {settings.EMAIL_BACKEND}")

        # Création du nom d'expéditeur avec formataddr
        sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))


        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=sender_name,
            to=[presence_request.email]
        )

        if html_content:
            email.attach_alternative(html_content, "text/html")

        result = email.send()
        print(f"✅ Email envoyé avec succès à {presence_request.email} (résultat : {result})")
        return True

    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email : {e}")
        print(f"   Destinataire : {presence_request.email}")
        print(f"   Expéditeur : {settings.DEFAULT_FROM_EMAIL}")
        return False