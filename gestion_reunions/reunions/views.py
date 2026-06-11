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
from .models import Reunion, PresenceRequest, CompteRendu, CustomUser, AgendaPoint, Invitation, Diligence, DiligenceComment
from .forms import ReunionForm, PresenceForm, CompteRenduForm, PresenceDirectForm, PresenceForm, PresenceValidationForm, PresenceARTCIFallbackForm, AgendaPointForm, InvitationBulkForm, DiligenceForm, DiligenceCommentForm
from .utils import generate_presence_report, send_compte_rendu_email
import json
import io
import qrcode
from email.utils import formataddr
from datetime import timedelta
import uuid

from .service_ad import ActiveDirectoryService
import logging, os
from dotenv import load_dotenv
from pathlib import Path


logger = logging.getLogger(__name__)


# Charger le fichier .env depuis la racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent  # ← dossier gestion_reunions/
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path)
logger.info(f"✅ Chargement du .env depuis : {dotenv_path}")


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
def api_live_stats(request):
    from datetime import date as date_type
    today = timezone.now().date()
    now = timezone.now()
    week_num = today.isocalendar()[1]
    year = today.year

    reunions_today = Reunion.objects.filter(date_debut__date=today).count()
    reunions_ongoing = Reunion.objects.filter(status='ongoing').count()
    reunions_planned = Reunion.objects.filter(status='planned').count()
    participants_today = PresenceRequest.objects.filter(
        status='confirmed', confirmed_at__date=today
    ).count()
    pending_requests = PresenceRequest.objects.filter(status='pending').count()
    reunions_this_week = Reunion.objects.filter(
        date_debut__week=week_num, date_debut__year=year
    ).count()
    participants_this_week = PresenceRequest.objects.filter(
        status='confirmed',
        confirmed_at__week=week_num,
        confirmed_at__year=year,
    ).count()
    reunions_by_status = {
        'planned': Reunion.objects.filter(status='planned').count(),
        'ongoing': Reunion.objects.filter(status='ongoing').count(),
        'finished': Reunion.objects.filter(status='finished').count(),
        'cancelled': Reunion.objects.filter(status='cancelled').count(),
    }

    return JsonResponse({
        'reunions_planned': reunions_planned,
        'reunions_ongoing': reunions_ongoing,
        'reunions_today': reunions_today,
        'participants_today': participants_today,
        'pending_requests': pending_requests,
        'reunions_this_week': reunions_this_week,
        'participants_this_week': participants_this_week,
        'reunions_by_status': reunions_by_status,
        'last_updated': now.strftime('%H:%M:%S'),
    })


@login_required
def admin_dashboard(request):
    from datetime import date as date_type
    today = timezone.now().date()
    week_num = today.isocalendar()[1]
    year = today.year

    reunions_today = Reunion.objects.filter(date_debut__date=today).count()
    reunions_this_week = Reunion.objects.filter(
        date_debut__week=week_num, date_debut__year=year
    ).count()
    participants_today = PresenceRequest.objects.filter(
        status='confirmed', confirmed_at__date=today
    ).count()
    participants_this_week = PresenceRequest.objects.filter(
        status='confirmed',
        confirmed_at__week=week_num,
        confirmed_at__year=year,
    ).count()
    reunions_by_status = {
        'planned': Reunion.objects.filter(status='planned').count(),
        'ongoing': Reunion.objects.filter(status='ongoing').count(),
        'finished': Reunion.objects.filter(status='finished').count(),
        'cancelled': Reunion.objects.filter(status='cancelled').count(),
    }
    top_organisations = (
        PresenceRequest.objects.filter(status='confirmed')
        .exclude(organisation='')
        .values('organisation')
        .annotate(n=Count('id'))
        .order_by('-n')[:5]
    )
    prochaines_reunions = Reunion.objects.filter(status='planned').order_by('date_debut')[:5]
    total_users = CustomUser.objects.count()
    total_reunions = Reunion.objects.count()

    context = {
        'total_users': total_users,
        'total_reunions': total_reunions,
        'reunions_today': reunions_today,
        'reunions_this_week': reunions_this_week,
        'participants_today': participants_today,
        'participants_this_week': participants_this_week,
        'reunions_by_status': reunions_by_status,
        'top_organisations': top_organisations,
        'prochaines_reunions': prochaines_reunions,
        'reunions_ongoing': reunions_by_status['ongoing'],
        'pending_requests': PresenceRequest.objects.filter(status='pending').count(),
    }
    return render(request, 'reunions/admin_dashboard.html', context)

@login_required
def secretary_dashboard(request):
    today = timezone.now().date()
    user = request.user
    mes_reunions = Reunion.objects.filter(secretaire=user)
    reunions_sans_cr = mes_reunions.filter(comptes_rendus__isnull=True, status='finished')
    total_participants = PresenceRequest.objects.filter(
        reunion__secretaire=user, status='confirmed'
    ).count()
    reunions_aujourd_hui = mes_reunions.filter(date_debut__date=today).order_by('date_debut')

    context = {
        'mes_reunions': mes_reunions,
        'reunions_sans_cr': reunions_sans_cr,
        'reunions_sans_cr_count': reunions_sans_cr.count(),
        'total_reunions': mes_reunions.count(),
        'total_participants': total_participants,
        'reunions_aujourd_hui': reunions_aujourd_hui,
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


@login_required
def stats_by_department(request):
    if request.user.role not in ['admin', 'secretary']:
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard')

    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    reunion_id = request.GET.get('reunion_id', '')

    qs = PresenceRequest.objects.filter(status='confirmed')
    if date_debut:
        qs = qs.filter(confirmed_at__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(confirmed_at__date__lte=date_fin)
    if reunion_id:
        try:
            qs = qs.filter(reunion_id=int(reunion_id))
        except (ValueError, TypeError):
            pass

    stats = qs.values('organisation').annotate(total=Count('id')).order_by('-total')
    total_global = qs.count()

    chart_labels = [s['organisation'] or '(Non renseigné)' for s in stats[:15]]
    chart_data = [s['total'] for s in stats[:15]]

    reunions = Reunion.objects.order_by('-date_debut')

    context = {
        'stats': stats,
        'total_global': total_global,
        'reunions': reunions,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'reunion_id': reunion_id,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_data_json': json.dumps(chart_data),
    }
    return render(request, 'reunions/stats_by_department.html', context)


@login_required
def stats_by_department_csv(request):
    if request.user.role not in ['admin', 'secretary']:
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard')

    import csv

    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    reunion_id = request.GET.get('reunion_id', '')

    qs = PresenceRequest.objects.filter(status='confirmed')
    if date_debut:
        qs = qs.filter(confirmed_at__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(confirmed_at__date__lte=date_fin)
    if reunion_id:
        try:
            qs = qs.filter(reunion_id=int(reunion_id))
        except (ValueError, TypeError):
            pass

    stats = qs.values('organisation').annotate(total=Count('id')).order_by('-total')
    total_global = qs.count()

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="stats_directions.csv"'
    response.write('\ufeff')  # BOM pour Excel

    writer = csv.writer(response)
    writer.writerow(['#', 'Direction / Service', 'Participants', '% du total'])
    for i, s in enumerate(stats, start=1):
        org = s['organisation'] or '(Non renseigné)'
        pct = round(s['total'] / total_global * 100, 1) if total_global else 0
        writer.writerow([i, org, s['total'], f"{pct}%"])
    writer.writerow([])
    writer.writerow(['Total', '', total_global, '100%'])

    return response


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
        context['agenda_points'] = self.object.agenda_points.all()
        context['invitations'] = self.object.invitations.all().order_by('-created_at')
        context['diligences'] = self.object.diligences.prefetch_related('commentaires__auteur').select_related(
            'responsable_interne', 'created_by'
        )
        return context

@login_required
def qr_code_image_view(request, pk):
    """
    Génère le QR code PNG à la volée — sans dépendance fichier/media.
    Fonctionne que DEBUG=True ou False, avec ou sans Nginx.
    """
    reunion = get_object_or_404(Reunion, pk=pk)

    site_protocol = getattr(settings, 'SITE_PROTOCOL', 'https://')
    site_address  = getattr(settings, 'SITE_ADDRESS',  'meeting.artci.ci')
    site_port     = getattr(settings, 'SITE_PORT', '')
    base_url = f"{site_protocol}{site_address}:{site_port}" if site_port else f"{site_protocol}{site_address}"
    qr_url = f"{base_url}/presence/{reunion.qr_code_uuid}/"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    response = HttpResponse(buf.getvalue(), content_type='image/png')
    response['Cache-Control'] = 'max-age=3600, private'
    return response


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

    can_edit = (
        request.user.role == 'admin'
        or reunion.organisateur == request.user
        or reunion.secretaire == request.user
    )
    if not can_edit:
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

    # Contenu texte brut (fallback) 👤 Organisateur : {presence_request.reunion.organisateur.first_name} {presence_request.reunion.organisateur.last_name}

    text_content = f"""
Bonjour,

Vous avez demandé à confirmer votre présence à la réunion « {presence_request.reunion.titre} ».

📅 Date : {presence_request.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
📍 Lieu : {presence_request.reunion.lieu}
👤 Organisateur : ARTCI


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
        # sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
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
STATUS_LABELS = {
    'planned': 'Planifiée',
    'ongoing': 'En cours',
    'finished': 'Terminée',
    'cancelled': 'Annulée',
}

@login_required
def update_reunion_status(request, pk):
    """Mise à jour AJAX du statut d'une réunion"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    reunion = get_object_or_404(Reunion, pk=pk)

    # Vérification des permissions
    can_change = (
        request.user.role == 'admin'
        or reunion.organisateur == request.user
        or reunion.secretaire == request.user
    )
    if not can_change:
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)

    new_status = request.POST.get('status')
    if new_status not in STATUS_LABELS:
        return JsonResponse({'success': False, 'error': 'Statut invalide'}, status=400)

    old_status = reunion.status
    reunion.status = new_status
    reunion.save()  # auto_now=True sur updated_at, save() complet requis

    # Notifier les participants si annulation
    if new_status == 'cancelled' and old_status != 'cancelled':
        from .tasks import notify_participants_reunion_annulee
        notify_participants_reunion_annulee.delay(reunion.pk)

    return JsonResponse({
        'success': True,
        'old_status': old_status,
        'new_status': new_status,
        'new_label': STATUS_LABELS[new_status],
    })

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
        # public_ip = '196.216.227.105'
                
        public_ip = 'localhost'  # Pour les tests locaux, sinon utiliser l'IP publique
        port = '8080'  # ou '80' si tu passes Gunicorn sur le port 80
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

        # ender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
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
        # sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))

        
        # Créer l'email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
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

    # Contenu texte brut (fallback) 👤 Organisateur : {presence_request.reunion.organisateur.first_name} {presence_request.reunion.organisateur.last_name}
    text_content = f"""
Bonjour,

Vous avez demandé à confirmer votre présence à la réunion « {presence_request.reunion.titre} ».

📅 Date : {presence_request.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
📍 Lieu : {presence_request.reunion.lieu}
👤 Organisateur : ARTCI

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
        #sender_name = formataddr(("QR Meeting", settings.DEFAULT_FROM_EMAIL))

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
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
    

"""
def presence_form(request, uuid):
    "Formulaire de demande de présence - Version simplifiée"
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)
    
    if request.method == 'POST':
        # Le consentement est déjà donné dans presence_consent.html
        # On récupère directement l'email du POST
        email = request.POST.get('email', '').lower().strip()
        
        if not email:
            messages.error(request, "Adresse email requise.")
            return redirect('presence_qr_redirect', uuid=uuid)
        
        # Vérifier si déjà enregistré
        existing_request = PresenceRequest.objects.filter(
            reunion=reunion, email=email
        ).first()
        
        if existing_request:
            messages.info(request, "Vous êtes déjà enregistré pour cette réunion.")
            return redirect('presence_status', token=existing_request.validation_token)
        
        # Traitement différencié selon le domaine email
        if is_artci_email(email):
            # Email ARTCI : Confirmation directe avec validation par email
            presence_request = PresenceRequest.objects.create(
                reunion=reunion,
                email=email,
                consent_given=True,  # Consentement déjà donné
                status='confirmed',
                confirmed_at=timezone.now()
            )
            
            # Auto-remplir les infos ARTCI
            def format_nom(nom):
                nom = nom.replace("'", "' ")
                return '-'.join(part.capitalize() for part in nom.split('-')).replace("' ", "'")

            email_prefix = email.split('@')[0]
            if '.' in email_prefix:
                parts = email_prefix.split('.')
                presence_request.prenom = format_nom(parts[1]) if len(parts) > 1 else ''
                presence_request.nom = format_nom(parts[0])
            else:
                presence_request.prenom = format_nom(email_prefix)
                presence_request.nom = ''
            presence_request.organisation = 'ARTCI'
            presence_request.save()
            
            # Envoyer email d'annulation avec délai de 5 minutes
            send_cancellation_email(presence_request)
            
            #messages.success(request, 
            #    "Présence confirmée ! Un email d'annulation vous a été envoyé au cas où cette inscription ne serait pas de votre fait.")
            
            return render(request, 'reunions/presence_confirmed_artci.html', {
                'reunion': reunion,
                'presence_request': presence_request,
                'is_artci': True
            })
        else:
            # Email externe : redirection vers formulaire complet
            # Stocker l'email dans la session pour le formulaire complet
            request.session['temp_email'] = email
            request.session['reunion_uuid'] = str(uuid)
            return redirect('presence_external_form', uuid=uuid)
    
    # Si GET, rediriger vers la page de consentement
    return redirect('presence_qr_redirect', uuid=uuid)

"""

def presence_external_form(request, uuid):
    """Formulaire complet pour les utilisateurs externes"""
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)
    
    # Récupérer l'email depuis la session
    temp_email = request.session.get('temp_email')
    if not temp_email or request.session.get('reunion_uuid') != str(uuid):
        messages.error(request, "Session expirée. Veuillez recommencer.")
        return redirect('presence_qr_redirect', uuid=uuid)
    
    # Vérifier que l'email n'est pas ARTCI
    if temp_email.endswith('@artci.ci'):
        messages.error(request, "Les emails ARTCI doivent passer par la validation directe.")
        return redirect('presence_qr_redirect', uuid=uuid)
    
    if request.method == 'POST':
        form = PresenceDirectForm(request.POST)
        if form.is_valid():
            # Vérifier si déjà enregistré
            existing_request = PresenceRequest.objects.filter(
                reunion=reunion, email=temp_email
            ).first()
            
            if existing_request:
                messages.info(request, "Vous êtes déjà enregistré pour cette réunion.")
                return redirect('presence_status', token=existing_request.validation_token)
            
            # Créer la demande avec CONFIRMATION DIRECTE
            presence_request = PresenceRequest.objects.create(
                reunion=reunion,
                email=temp_email,
                nom=form.cleaned_data['nom'],
                prenom=form.cleaned_data['prenom'],
                organisation=form.cleaned_data['organisation'],
                fonction=form.cleaned_data['fonction'],
                contact=form.cleaned_data['contact'],
                consent_given=True,
                status='confirmed',  # CONFIRME DIRECTEMENT
                confirmed_at=timezone.now()
            )
            
            # Envoyer email d'annulation avec délai de 5 minutes
            send_cancellation_email(presence_request)

            # Nettoyer la session
            if 'temp_email' in request.session:
                del request.session['temp_email']
            if 'reunion_uuid' in request.session:
                del request.session['reunion_uuid']

            return redirect('presence_signature', uuid=uuid, token=presence_request.validation_token)
    else:
        # Pré-remplir l'email et le rendre en lecture seule
        form = PresenceDirectForm(initial={'email': temp_email})
        form.fields['email'].widget.attrs['readonly'] = True
        form.fields['email'].widget.attrs['style'] = 'background-color: #f8f9fa;'
    
    return render(request, 'reunions/presence_external_form.html', {
        'form': form,
        'reunion': reunion,
        'email': temp_email
    })


def handle_artci_email_process(request, reunion, email):
    """Gestion pour les emails ARTCI - Processus avec email"""
    
    # Créer la demande de présence
    presence_request = PresenceRequest.objects.create(
        reunion=reunion,
        email=email,
        consent_given=True,
        status='pending',
        auto_confirm_at=timezone.now() + timedelta(minutes=5)  # Confirmation auto dans 5 min
    )
    
    # Envoyer email d'annulation
    success = send_cancellation_email(presence_request)
    
    if success:
        messages.success(request, 
            "Email ARTCI détecté ! Votre inscription est enregistrée. "
            "Un email d'annulation vous a été envoyé. Si vous ne cliquez pas sur 'Annuler' "
            "dans les 5 minutes, votre présence sera automatiquement confirmée.")
    else:
        messages.error(request, 
            "Erreur lors de l'envoi de l'email d'annulation.")
    
    return render(request, 'reunions/presence_pending_confirmation.html', {
        'reunion': reunion,
        'presence_request': presence_request,
        'is_artci': True
    })

"""
def presence_cancel(request, token):
    Vue pour annuler une demande de présence
    presence_request = get_object_or_404(PresenceRequest, cancellation_token=token)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'cancel':
            presence_request.status = 'cancelled'
            presence_request.save()
            messages.success(request, "Votre demande de présence a été annulée avec succès.")
            return render(request, 'reunions/presence_cancelled.html', {
                'reunion': presence_request.reunion
            })
    
    # Vérifier si la demande est encore confirmée
    if presence_request.status != 'confirmed':
        return render(request, 'reunions/presence_cancel_expired.html', {
            'presence_request': presence_request
        })
    
    return render(request, 'reunions/presence_cancel_confirm.html', {
        'presence_request': presence_request
    })

"""

def send_cancellation_email(presence_request):
    """Envoie l'email d'annulation avec bouton"""
    
    subject = f"Confirmation d'inscription - {presence_request.reunion.titre}"
    cancellation_url = build_cancellation_url(presence_request.cancellation_token)
    
    print(f"🔗 URL d'annulation générée: {cancellation_url}")
    
    # Contexte du template
    context = {
        'presence_request': presence_request,
        'cancellation_url': cancellation_url,
        'reunion': presence_request.reunion,
        'is_artci': presence_request.is_artci_email(),
    }
    
    # Essayer de rendre le contenu HTML
    try:
        html_content = render_to_string('reunions/email_cancellation.html', context)
    except Exception as e:
        print(f"⚠️ Erreur lors du rendu du template HTML : {e}")
        html_content = None
    
    # Contenu texte brut
    text_content = f"""
Bonjour,

Votre inscription à la réunion « {presence_request.reunion.titre} » a bien été confirmée.

📅 Date : {presence_request.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
📍 Lieu : {presence_request.reunion.lieu}

⚠️ IMPORTANT : Si cette inscription n'est pas de votre fait, vous avez 1 heure pour l'annuler en cliquant sur le lien ci-dessous :

{cancellation_url}

Si vous souhaitez bien participer à cette réunion, vous n'avez rien à faire.

Merci,
L'équipe QR Meeting

---
Ce message est automatique. Merci de ne pas y répondre.
"""
    
    # Envoi de l'email
    try:
        print(f"📧 Envoi de l'email d'annulation à : {presence_request.email}")
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[presence_request.email]
        )
        
        if html_content:
            email.attach_alternative(html_content, "text/html")
        
        result = email.send()
        print(f"✅ Email d'annulation envoyé avec succès à {presence_request.email} (résultat : {result})")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email d'annulation : {e}")
        return False

def build_cancellation_url(token):
    """Construit l'URL d'annulation"""
    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'
    
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site_url:
        base_url = site_url
    else:
        # Pour les tests locaux
        base_url = f"{protocol}://localhost:8000"
    
    return f"{base_url}/cancel/{token}/"

# Tâche périodique pour la confirmation automatique (à ajouter à une tâche cron ou celery)
def auto_confirm_pending_requests():

    """Confirme automatiquement les demandes en attente après 5 minutes"""
    from django.utils import timezone
    
    pending_requests = PresenceRequest.objects.filter(
        status='pending',
        auto_confirm_at__lte=timezone.now()
    )
    
    confirmed_count = 0
    for request in pending_requests:
        if request.auto_confirm():
            confirmed_count += 1
            print(f"✅ Confirmation automatique: {request.email} pour {request.reunion.titre}")
    
    if confirmed_count > 0:
        print(f"🎯 {confirmed_count} demandes confirmées automatiquement")
    
    return confirmed_count


def presence_cancel_by_token(request, cancel_token):
    """Annulation via le token d'annulation avec notification au secrétaire"""
    try:
        presence_request = get_object_or_404(
            PresenceRequest, 
            cancellation_token=cancel_token,
            status='confirmed'
        )
        
        # Vérifier que la fenêtre d'annulation est encore ouverte (5 minutes)
        if presence_request.confirmed_at:
            time_since_confirmation = timezone.now() - presence_request.confirmed_at
            if time_since_confirmation > timedelta(minutes=60):
                messages.error(request, "La période d'annulation a expiré.")
                return render(request, 'reunions/cancellation_expired.html', {
                    'presence_request': presence_request
                })
        
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'cancel':
                # Annuler la présence
                presence_request.cancel_presence()
                
                # Envoyer notification au secrétaire
                notification_sent = send_cancellation_notification_to_secretary(presence_request)
                
                # Message de succès adapté selon l'envoi de notification
                if notification_sent:
                    messages.success(request, 
                        "Votre présence a été annulée avec succès. "
                        "Le secrétaire de séance a été notifié.")
                else:
                    messages.success(request, 
                        "Votre présence a été annulée avec succès.")
                    messages.warning(request, 
                        "La notification au secrétaire n'a pas pu être envoyée.")
                
                return render(request, 'reunions/presence_cancelled.html', {
                    'presence_request': presence_request,
                    'notification_sent': notification_sent
                })
        
        return render(request, 'reunions/confirm_cancellation.html', {
            'presence_request': presence_request
        })
        
    except:
        messages.error(request, "Lien d'annulation invalide ou expiré.")
        return redirect('dashboard')


def log_cancellation_event(presence_request, notified_email):

    """
    Enregistre l'événement d'annulation dans les logs
    (Optionnel : créer un modèle CancellationLog si besoin de traçabilité complète)
    """
    import logging
    
    logger = logging.getLogger('reunions.cancellations')
    
    logger.info(
        f"ANNULATION - Réunion: {presence_request.reunion.titre} | "
        f"Participant: {presence_request.email} ({presence_request.get_display_name()}) | "
        f"Secrétaire notifié: {notified_email} | "
        f"Timestamp: {timezone.now().isoformat()}"
    )


def get_display_name(self):
    """Retourne le nom d'affichage adapté selon le type"""
    if self.is_artci_email() and not (self.nom or self.prenom):
        # Pour ARTCI sans nom, extraire depuis l'email
        email_prefix = self.email.split('@')[0]
        if '.' in email_prefix:
            parts = email_prefix.split('.')
            return f"{parts[0].capitalize()} {parts[1].capitalize() if len(parts) > 1 else ''}"
        else:
            return email_prefix.capitalize()
    elif self.prenom and self.nom:
        return f"{self.prenom} {self.nom}"
    elif self.prenom:
        return self.prenom
    elif self.nom:
        return self.nom
    else:
        return self.email


def debug_secretary_notification(request):

    """Vue de debug pour tester l'envoi au secrétaire"""
    if not settings.DEBUG:
        return JsonResponse({'error': 'Debug mode only'})
    
    # Test d'envoi rapide
    test_context = {
        'participant_name': 'Test User',
        'participant_email': 'test@example.com',
        'participant_type': 'ARTCI',
        'cancellation_reason': 'Test de notification',
        'secretary_email': getattr(settings, 'SECRETARY_NOTIFICATION_EMAIL', 'qrmeeting@artci.ci'),
        'cancelled_at': timezone.now(),
    }
    
    subject = "🧪 Test notification secrétaire"
    text_content = f"""
TEST DE NOTIFICATION SECRÉTAIRE
===============================

Ceci est un test d'envoi de notification au secrétaire.

Configuration actuelle:
- SECRETARY_NOTIFICATION_EMAIL: {getattr(settings, 'SECRETARY_NOTIFICATION_EMAIL', 'Non défini')}
- DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}
- EMAIL_BACKEND: {settings.EMAIL_BACKEND}
- EMAIL_HOST: {settings.EMAIL_HOST}

Timestamp: {timezone.now().strftime('%d/%m/%Y à %H:%M:%S')}
"""
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[test_context['secretary_email']]
        )
        
        result = email.send()
        
        return JsonResponse({
            'success': True,
            'message': f'Test envoyé à {test_context["secretary_email"]}',
            'result': result,
            'config': {
                'secretary_email': test_context['secretary_email'],
                'from_email': settings.DEFAULT_FROM_EMAIL,
                'backend': settings.EMAIL_BACKEND,
                'host': settings.EMAIL_HOST,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'config': {
                'secretary_email': test_context['secretary_email'],
                'from_email': settings.DEFAULT_FROM_EMAIL,
                'backend': settings.EMAIL_BACKEND,
                'host': settings.EMAIL_HOST,
            }
        })


def presence_cancel(request, token):
    """Vue pour annuler automatiquement une demande de présence"""
    
    print(f"🔍 Tentative d'annulation automatique avec token: {token}")
    
    try:
        presence_request = get_object_or_404(PresenceRequest, cancellation_token=token)
        print(f"✅ PresenceRequest trouvé: {presence_request.email}")
    except:
        print(f"❌ PresenceRequest introuvable pour token: {token}")
        messages.error(request, "Lien d'annulation invalide ou expiré.")
        return redirect('dashboard')
    
    # Vérifier si la demande est encore confirmée
    if presence_request.status != 'confirmed':
        print(f"⚠️ Statut incorrect: {presence_request.status}")
        return render(request, 'reunions/presence_cancel_expired.html', {
            'presence_request': presence_request
        })
    
    # Vérifier la fenêtre de 5 minutes
    if presence_request.confirmed_at:
        time_since_confirmation = timezone.now() - presence_request.confirmed_at
        print(f"⏰ Temps écoulé depuis confirmation: {time_since_confirmation}")
        
        if time_since_confirmation > timedelta(minutes=60):
            print(f"⏰ Délai d'annulation expiré")
            messages.error(request, "La période d'annulation a expiré (50 minutes maximum).")
            return render(request, 'reunions/presence_cancel_expired.html', {
                'presence_request': presence_request
            })
    
    # ANNULATION AUTOMATIQUE - Dès l'accès au lien
    print(f"🚀 ANNULATION AUTOMATIQUE EN COURS")
    
    # Sauvegarder les infos avant annulation pour la notification
    participant_name = get_participant_name(presence_request)
    participant_email = presence_request.email
    participant_type = get_participant_type(presence_request)
    
    print(f"👤 Participant: {participant_name} ({participant_type})")
    
    # Annuler la présence immédiatement
    presence_request.status = 'cancelled'
    presence_request.cancelled_at = timezone.now()
    presence_request.save()
    
    print(f"✅ Statut mis à jour: cancelled")
    
    # Envoyer notification au secrétaire
    try:
        notification_sent = send_cancellation_notification_to_secretary(
            presence_request, 
            reason="Annulation via lien email",  # Raison par défaut
            participant_name=participant_name,
            participant_email=participant_email,
            participant_type=participant_type
        )
        
        if notification_sent:
            print(f"✅ Notification secrétaire envoyée avec succès")
            messages.success(request, 
                "Votre présence a été annulée avec succès. "
                "Le secrétaire de séance a été notifié.")
        else:
            print(f"❌ Échec envoi notification secrétaire")
            messages.success(request, "Votre présence a été annulée avec succès.")
            messages.warning(request, "La notification au secrétaire n'a pas pu être envoyée.")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de la notification secrétaire: {e}")
        messages.success(request, "Votre présence a été annulée avec succès.")
        messages.warning(request, "Erreur lors de l'envoi de la notification au secrétaire.")
    
    # Afficher directement la page de confirmation d'annulation
    return render(request, 'reunions/presence_cancelled.html', {
        'reunion': presence_request.reunion,
        'participant_name': participant_name
    })

# Fonctions utilitaires inchangées
def get_participant_name(presence_request):
    """Extraction du nom du participant avec fallbacks"""
    if hasattr(presence_request, 'get_display_name'):
        return presence_request.get_display_name()
    else:
        if presence_request.prenom and presence_request.nom:
            return f"{presence_request.prenom} {presence_request.nom}"
        elif presence_request.prenom:
            return presence_request.prenom
        elif presence_request.nom:
            return presence_request.nom
        else:
            return presence_request.email


def get_participant_type(presence_request):
    """Détermination du type de participant avec fallbacks"""
    if hasattr(presence_request, 'get_validation_type'):
        return presence_request.get_validation_type()
    else:
        return "ARTCI" if presence_request.email.lower().endswith('@artci.ci') else "Externe"


def send_cancellation_notification_to_secretary(presence_request, reason=None, 
                                               participant_name=None, participant_email=None, 
                                               participant_type=None):
    """Envoie une notification d'annulation au secrétaire de la réunion"""
    reunion = presence_request.reunion
    
    print(f"📧 Début envoi notification secrétaire")
    
    # Identifier le secrétaire avec plusieurs fallbacks
    secretary_email = None
    
    if (hasattr(reunion, 'secretaire') and reunion.secretaire and 
        hasattr(reunion.secretaire, 'email') and reunion.secretaire.email):
        secretary_email = reunion.secretaire.email
        print(f"📧 Secrétaire trouvé dans reunion.secretaire: {secretary_email}")
    
    elif (hasattr(reunion, 'organisateur') and reunion.organisateur and 
          hasattr(reunion.organisateur, 'email') and reunion.organisateur.email):
        secretary_email = reunion.organisateur.email
        print(f"📧 Secrétaire trouvé dans reunion.organisateur: {secretary_email}")
    
    else:
        secretary_email = getattr(settings, 'SECRETARY_NOTIFICATION_EMAIL', 
                                getattr(settings, 'DEFAULT_FROM_EMAIL', 'qrmeeting@artci.ci'))
        print(f"📧 Utilisation email de fallback: {secretary_email}")
    
    if not secretary_email:
        print("❌ Aucun email de secrétaire trouvé")
        return False
    
    print(f"📧 Envoi notification d'annulation au secrétaire: {secretary_email}")
    
    subject = f"🚫 Annulation de présence - {reunion.titre}"
    
    participant_name = participant_name or get_participant_name(presence_request)
    participant_email = participant_email or presence_request.email
    participant_type = participant_type or get_participant_type(presence_request)
    
    text_content = f"""
NOTIFICATION D'ANNULATION DE PRÉSENCE
=====================================


Bonjour, 

Un participant a annulé son inscription à une réunion.

PARTICIPANT CONCERNÉ :
==============================
• Nom : {participant_name}
• Email : {participant_email}  
• Type : {participant_type}
• Organisation : {presence_request.organisation or 'Non spécifiée'}
• Date d'annulation : {timezone.now().strftime('%d/%m/%Y à %H:%M')}
• Méthode : Annulation automatique via lien email"""

    if reason:
        text_content += f"""
• Raison : {reason}"""

    text_content += f"""

RÉUNION CONCERNÉE:
==================
• Titre : {reunion.titre}
• Date : {reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}
• Lieu : {reunion.lieu}

ACTIONS RECOMMANDÉES :
=====================
- Mettre à jour la liste des participants confirmés
- Vérifier si des ajustements logistiques sont nécessaires
- Documenter cette annulation dans vos records

Cette notification a été générée automatiquement par le système QR Meeting.

Cordialement,
Système QR Meeting
"""
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'qrmeeting@artci.ci'),
            to=[secretary_email]
        )
        
        result = email.send()
        print(f"✅ Notification envoyée: {secretary_email} (résultat: {result})")
        return True
        
    except Exception as e:
        print(f"❌ Erreur envoi notification: {e}")
        return False

def debug_secretary_notification(request):

    """Vue de debug pour tester l'envoi au secrétaire"""
    if not settings.DEBUG:
        return JsonResponse({'error': 'Debug mode only'})
    
    print(f"🧪 Test de notification secrétaire")
    
    # Test d'envoi rapide
    secretary_email = getattr(settings, 'SECRETARY_NOTIFICATION_EMAIL', 'qrmeeting@artci.ci')
    
    subject = "🧪 Test notification secrétaire"
    text_content = f"""
TEST DE NOTIFICATION SECRÉTAIRE
===============================

Ceci est un test d'envoi de notification au secrétaire.

Configuration actuelle:
- SECRETARY_NOTIFICATION_EMAIL: {getattr(settings, 'SECRETARY_NOTIFICATION_EMAIL', 'Non défini')}
- DEFAULT_FROM_EMAIL: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'Non défini')}
- EMAIL_BACKEND: {getattr(settings, 'EMAIL_BACKEND', 'Non défini')}
- EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Non défini')}

Timestamp: {timezone.now().strftime('%d/%m/%Y à %H:%M:%S')}
"""
    
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'qrmeeting@artci.ci'),
            to=[secretary_email]
        )
        
        result = email.send()
        
        print(f"✅ Test envoyé avec succès")
        
        return JsonResponse({
            'success': True,
            'message': f'Test envoyé à {secretary_email}',
            'result': result,
            'config': {
                'secretary_email': secretary_email,
                'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Non défini'),
                'backend': getattr(settings, 'EMAIL_BACKEND', 'Non défini'),
                'host': getattr(settings, 'EMAIL_HOST', 'Non défini'),
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur test: {e}")
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'config': {
                'secretary_email': secretary_email,
                'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Non défini'),
                'backend': getattr(settings, 'EMAIL_BACKEND', 'Non défini'),
                'host': getattr(settings, 'EMAIL_HOST', 'Non défini'),
            }
        })
    


def presence_form(request, uuid):
    """
    Formulaire de demande de présence avec intégration Active Directory.
    """
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)

    # Pré-remplissage depuis invitation_accept
    prefill_email = request.session.pop('prefill_email', None)

    if request.method == 'POST':
        # Récupération sécurisée de l'email
        email = (request.POST.get('email') or '').strip().lower()
        if not email:
            messages.error(request, "Adresse email requise.")
            return redirect('presence_qr_redirect', uuid=uuid)

        # Vérifier si déjà enregistré
        existing_request = PresenceRequest.objects.filter(reunion=reunion, email=email).first()
        if existing_request:
            messages.info(request, "Vous êtes déjà enregistré pour cette réunion.")
            return redirect('presence_status', token=existing_request.validation_token)

        # Cas email ARTCI
        if is_artci_email(email):
            try:
                service_ad = ActiveDirectoryService()
                user_info = service_ad.get_user_info(email)

                if not user_info:
                    logger.warning(f"Utilisateur {email} non trouvé dans AD — redirection vers formulaire manuel")
                    log_artci_ad_manquant(email)
                    request.session['artci_fallback_email'] = email
                    request.session['reunion_uuid'] = str(uuid)
                    return redirect('presence_artci_fallback_form', uuid=uuid)

                # Normalisation du nom et du prénom
                prenom = user_info.get('prenom', '').capitalize() if user_info.get('prenom') else ''
                nom = user_info.get('nom', '').upper() if user_info.get('nom') else ''

                # Création de la présence avec données AD
                presence_request = PresenceRequest.objects.create(
                    reunion=reunion,
                    email=user_info['email'],
                    prenom=prenom,
                    nom=nom,
                    organisation=user_info.get('organisation', 'ARTCI'),
                    fonction=user_info.get('fonction', ''),
                    contact=user_info.get('contact', ''),
                    # poste=user_info.get('poste', ''),
                    # departement=user_info.get('departement', ''),
                    # matricule=user_info.get('matricule', ''),
                    consent_given=True,
                    status='confirmed',
                    confirmed_at=timezone.now()
                )

                logger.info(f"Présence créée pour {email} depuis AD")
                send_cancellation_email(presence_request)

                return redirect('presence_signature', uuid=uuid, token=presence_request.validation_token)

            except Exception as e:
                logger.error(f"Erreur connexion AD pour {email}: {str(e)}")
                messages.error(request,
                    "Une erreur est survenue lors de la connexion à Active Directory. "
                    "Veuillez réessayer plus tard ou contacter le support.")
                return redirect('presence_qr_redirect', uuid=uuid)

        # Cas email externe
        else:
            request.session['temp_email'] = email
            request.session['reunion_uuid'] = str(uuid)
            return redirect('presence_external_form', uuid=uuid)

    # GET → redirige vers la page QR / consentement (ou pré-rempli depuis invitation)
    if prefill_email:
        return render(request, 'reunions/presence_consent.html', {
            'reunion': reunion,
            'prefill_email': prefill_email,
        })
    return redirect('presence_qr_redirect', uuid=uuid)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def log_artci_ad_manquant(email):
    """Enregistre l'email ARTCI non trouvé dans l'AD dans un fichier de log dédié."""
    from pathlib import Path
    from django.conf import settings
    import datetime

    log_dir = Path(settings.BASE_DIR) / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'artci_ad_manquants.txt'

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | {email}\n")
    logger.info(f"Email ARTCI non-AD loggé : {email}")


# ─── Vue fallback ARTCI non trouvé dans l'AD ─────────────────────────────────

def presence_artci_fallback_form(request, uuid):
    """
    Formulaire pour les agents ARTCI dont le compte n'existe pas dans l'AD.
    Permet de saisir manuellement les informations. L'email est loggé pour
    mise à jour ultérieure de l'Active Directory.
    """
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)

    artci_email = request.session.get('artci_fallback_email')
    if not artci_email or request.session.get('reunion_uuid') != str(uuid):
        messages.error(request, "Session expirée. Veuillez recommencer.")
        return redirect('presence_qr_redirect', uuid=uuid)

    if request.method == 'POST':
        form = PresenceARTCIFallbackForm(request.POST)
        if form.is_valid():
            existing = PresenceRequest.objects.filter(reunion=reunion, email=artci_email).first()
            if existing:
                messages.info(request, "Vous êtes déjà enregistré pour cette réunion.")
                return redirect('presence_status', token=existing.validation_token)

            presence_request = PresenceRequest.objects.create(
                reunion=reunion,
                email=artci_email,
                nom=form.cleaned_data['nom'],
                prenom=form.cleaned_data['prenom'],
                organisation=form.cleaned_data.get('organisation', 'ARTCI'),
                fonction=form.cleaned_data['fonction'],
                contact=form.cleaned_data['contact'],
                consent_given=True,
                status='confirmed',
                confirmed_at=timezone.now(),
            )

            send_cancellation_email(presence_request)

            # Nettoyage session
            request.session.pop('artci_fallback_email', None)
            request.session.pop('reunion_uuid', None)

            return redirect('presence_signature', uuid=uuid, token=presence_request.validation_token)
    else:
        form = PresenceARTCIFallbackForm(initial={
            'email': artci_email,
            'organisation': 'ARTCI',
        })
        form.fields['email'].widget.attrs['readonly'] = True
        form.fields['email'].widget.attrs['style'] = 'background-color: #f8f9fa;'

    return render(request, 'reunions/presence_artci_fallback_form.html', {
        'form': form,
        'reunion': reunion,
        'email': artci_email,
    })


# ─── Agenda Views ─────────────────────────────────────────────────────────────

def _can_manage_reunion(user, reunion):
    return (
        user.role == 'admin'
        or reunion.organisateur == user
        or reunion.secretaire == user
    )


@login_required
def agenda_point_create(request, reunion_id):
    reunion = get_object_or_404(Reunion, pk=reunion_id)
    if not _can_manage_reunion(request.user, reunion):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_id)

    if request.method == 'POST':
        form = AgendaPointForm(request.POST)
        if form.is_valid():
            point = form.save(commit=False)
            point.reunion = reunion
            point.save()
            messages.success(request, "Point d'agenda ajouté avec succès.")
            return redirect('reunion_detail', pk=reunion_id)
    else:
        # Pré-remplir l'ordre avec le suivant disponible
        next_ordre = (reunion.agenda_points.count() or 0) + 1
        form = AgendaPointForm(initial={'ordre': next_ordre})

    return render(request, 'reunions/agenda_point_form.html', {
        'form': form,
        'reunion': reunion,
        'action': 'Ajouter',
    })


@login_required
def agenda_point_update(request, pk):
    point = get_object_or_404(AgendaPoint, pk=pk)
    reunion = point.reunion
    if not _can_manage_reunion(request.user, reunion):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion.pk)

    if request.method == 'POST':
        form = AgendaPointForm(request.POST, instance=point)
        if form.is_valid():
            form.save()
            messages.success(request, "Point d'agenda mis à jour.")
            return redirect('reunion_detail', pk=reunion.pk)
    else:
        form = AgendaPointForm(instance=point)

    return render(request, 'reunions/agenda_point_form.html', {
        'form': form,
        'reunion': reunion,
        'point': point,
        'action': 'Modifier',
    })


@login_required
def agenda_point_delete(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    point = get_object_or_404(AgendaPoint, pk=pk)
    if not _can_manage_reunion(request.user, point.reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    point.delete()
    return JsonResponse({'success': True})


@login_required
def agenda_point_toggle(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    point = get_object_or_404(AgendaPoint, pk=pk)
    if not _can_manage_reunion(request.user, point.reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    point.est_traite = not point.est_traite
    point.save(update_fields=['est_traite'])
    total = point.reunion.agenda_points.count()
    traites = point.reunion.agenda_points.filter(est_traite=True).count()
    return JsonResponse({
        'success': True,
        'est_traite': point.est_traite,
        'traites': traites,
        'total': total,
    })


@login_required
def agenda_point_reorder(request, reunion_id):
    """AJAX : réorganise les points d'agenda par drag-and-drop."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    reunion = get_object_or_404(Reunion, pk=reunion_id)
    if not _can_manage_reunion(request.user, reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    try:
        items = json.loads(request.body)  # [{'id': pk, 'ordre': new_ordre}, ...]
        for item in items:
            AgendaPoint.objects.filter(pk=item['id'], reunion=reunion).update(ordre=item['ordre'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def agenda_point_notes(request, pk):
    """AJAX : sauvegarde les notes de séance d'un point d'agenda."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    point = get_object_or_404(AgendaPoint, pk=pk)
    if not _can_manage_reunion(request.user, point.reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    try:
        data = json.loads(request.body)
        point.notes_seance = data.get('notes', '')
        point.save(update_fields=['notes_seance'])
        return JsonResponse({'success': True, 'notes': point.notes_seance})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─── Signature numérique ───────────────────────────────────────────────────────

def presence_signature(request, uuid, token):
    """Page de capture de signature numérique après enregistrement de présence."""
    reunion = get_object_or_404(Reunion, qr_code_uuid=uuid)
    presence_request = get_object_or_404(PresenceRequest, validation_token=token, reunion=reunion)

    if request.method == 'POST':
        import base64 as _base64
        from django.core.files.base import ContentFile

        signature_data = request.POST.get('signature_data', '').strip()
        if signature_data and 'base64,' in signature_data:
            _, img_b64 = signature_data.split('base64,', 1)
            try:
                img_bytes = _base64.b64decode(img_b64)
                fname = f"sig_{presence_request.validation_token}.png"
                presence_request.signature.save(fname, ContentFile(img_bytes), save=True)
            except Exception as e:
                logger.warning(f"Erreur sauvegarde signature: {e}")

        if presence_request.is_artci_email():
            return render(request, 'reunions/presence_confirmed_artci.html', {
                'reunion': reunion,
                'presence_request': presence_request,
                'is_artci': True,
                'from_ad': False,
            })
        return render(request, 'reunions/presence_confirmed_external.html', {
            'reunion': reunion,
            'presence_request': presence_request,
            'is_artci': False,
        })

    return render(request, 'reunions/presence_signature.html', {
        'reunion': reunion,
        'presence_request': presence_request,
    })


# ─── Invitation Views ──────────────────────────────────────────────────────────

def _build_site_url(request=None):
    """Construit l'URL de base du site."""
    from django.conf import settings
    if request:
        return f"{request.scheme}://{request.get_host()}"
    protocol = getattr(settings, 'SITE_PROTOCOL', 'https://')
    address = getattr(settings, 'SITE_ADDRESS', 'meeting.artci.ci')
    port = getattr(settings, 'SITE_PORT', '')
    if port:
        return f"{protocol}{address}:{port}"
    return f"{protocol}{address}"


def send_invitation_email(invitation, request=None):
    """Envoie l'email d'invitation à un participant."""
    from django.urls import reverse
    base_url = _build_site_url(request)
    accept_url = base_url + reverse('invitation_accept', args=[str(invitation.token)])
    decline_url = base_url + reverse('invitation_decline', args=[str(invitation.token)])

    subject = f"Invitation — {invitation.reunion.titre}"
    context = {
        'invitation': invitation,
        'reunion': invitation.reunion,
        'accept_url': accept_url,
        'decline_url': decline_url,
    }
    try:
        html_content = render_to_string('reunions/email_invitation.html', context)
    except Exception:
        html_content = None

    text_content = (
        f"Bonjour,\n\n"
        f"Vous êtes invité(e) à participer à la réunion « {invitation.reunion.titre} »\n"
        f"Date : {invitation.reunion.date_debut.strftime('%d/%m/%Y à %H:%M')}\n"
        f"Lieu : {invitation.reunion.lieu}\n\n"
        f"Accepter : {accept_url}\n"
        f"Décliner : {decline_url}\n\n"
        f"Cordialement,\nL'équipe QR Meeting\n"
    )

    try:
        email_msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invitation.email],
        )
        if html_content:
            email_msg.attach_alternative(html_content, "text/html")
        email_msg.send()
        return True
    except Exception as e:
        logger.error(f"Erreur envoi invitation {invitation.email}: {e}")
        return False


@login_required
def invitation_send(request, reunion_id):
    reunion = get_object_or_404(Reunion, pk=reunion_id)
    if not _can_manage_reunion(request.user, reunion):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_id)

    if request.method == 'POST':
        form = InvitationBulkForm(request.POST)
        if form.is_valid():
            emails = form.cleaned_data['emails']
            sent = 0
            already_invited = 0
            errors = 0

            for email_addr in emails:
                invitation, created = Invitation.objects.get_or_create(
                    reunion=reunion,
                    email=email_addr,
                    defaults={'invited_by': request.user},
                )
                if not created and invitation.status in ('sent', 'accepted'):
                    already_invited += 1
                    continue

                success = send_invitation_email(invitation, request)
                if success:
                    invitation.status = 'sent'
                    invitation.sent_at = timezone.now()
                    invitation.invited_by = request.user
                    invitation.save(update_fields=['status', 'sent_at', 'invited_by'])
                    sent += 1
                else:
                    errors += 1

            parts = []
            if sent:
                parts.append(f"{sent} invitation(s) envoyée(s)")
            if already_invited:
                parts.append(f"{already_invited} déjà invité(s)")
            if errors:
                parts.append(f"{errors} erreur(s)")
            messages.success(request, " — ".join(parts) if parts else "Aucune action effectuée.")
            return redirect('reunion_detail', pk=reunion_id)
    else:
        form = InvitationBulkForm()

    return render(request, 'reunions/invitation_form.html', {
        'form': form,
        'reunion': reunion,
    })


def invitation_accept(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    reunion = invitation.reunion

    if reunion.status in ('cancelled', 'finished'):
        messages.error(request, "Cette réunion n'est plus accessible.")
        return redirect('dashboard')

    invitation.status = 'accepted'
    invitation.save(update_fields=['status'])

    # Pré-remplir l'email en session pour le formulaire de présence
    request.session['prefill_email'] = invitation.email
    request.session['reunion_uuid'] = str(reunion.qr_code_uuid)
    messages.success(request, "Invitation acceptée ! Veuillez compléter votre inscription.")
    return redirect('presence_form', uuid=reunion.qr_code_uuid)


def invitation_decline(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    invitation.status = 'declined'
    invitation.save(update_fields=['status'])
    return render(request, 'reunions/invitation_declined.html', {
        'invitation': invitation,
        'reunion': invitation.reunion,
    })


# ─── Diligences ───────────────────────────────────────────────────────────────

@login_required
def diligence_create(request, reunion_id):
    reunion = get_object_or_404(Reunion, pk=reunion_id)
    if not _can_manage_reunion(request.user, reunion):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_id)

    if request.method == 'POST':
        form = DiligenceForm(request.POST)
        if form.is_valid():
            diligence = form.save(commit=False)
            diligence.reunion = reunion
            diligence.created_by = request.user
            diligence.save()
            messages.success(request, "Diligence ajoutée avec succès.")
            return redirect('reunion_detail', pk=reunion_id)
    else:
        form = DiligenceForm()

    return render(request, 'reunions/diligence_form.html', {
        'form': form,
        'reunion': reunion,
        'action': 'Ajouter',
    })


@login_required
def diligence_update(request, pk):
    diligence = get_object_or_404(Diligence, pk=pk)
    reunion = diligence.reunion
    if not _can_manage_reunion(request.user, reunion):
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion.pk)

    if request.method == 'POST':
        form = DiligenceForm(request.POST, instance=diligence)
        if form.is_valid():
            form.save()
            messages.success(request, "Diligence mise à jour.")
            return redirect('reunion_detail', pk=reunion.pk)
    else:
        form = DiligenceForm(instance=diligence)

    return render(request, 'reunions/diligence_form.html', {
        'form': form,
        'reunion': reunion,
        'diligence': diligence,
        'action': 'Modifier',
    })


@login_required
def diligence_delete(request, pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)
    diligence = get_object_or_404(Diligence, pk=pk)
    if not _can_manage_reunion(request.user, diligence.reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)
    diligence.delete()
    return JsonResponse({'success': True})


@login_required
def diligence_update_status(request, pk):
    """Change le statut d'une diligence et enregistre un commentaire optionnel."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    diligence = get_object_or_404(Diligence, pk=pk)
    if not _can_manage_reunion(request.user, diligence.reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Données invalides'}, status=400)

    nouveau_status = data.get('status', '').strip()
    contenu = data.get('commentaire', '').strip()

    valid_statuses = [s[0] for s in Diligence.STATUS]
    if nouveau_status not in valid_statuses:
        return JsonResponse({'success': False, 'error': 'Statut invalide'}, status=400)

    ancien_status = diligence.status
    diligence.status = nouveau_status
    diligence.save(update_fields=['status', 'updated_at'])

    # Enregistrer le changement (et commentaire éventuel) dans l'historique
    DiligenceComment.objects.create(
        diligence=diligence,
        auteur=request.user,
        contenu=contenu,
        ancien_status=ancien_status,
        nouveau_status=nouveau_status,
    )

    total = diligence.reunion.diligences.count()
    terminees = diligence.reunion.diligences.filter(status='completed').count()

    return JsonResponse({
        'success': True,
        'status': nouveau_status,
        'status_display': diligence.get_status_display(),
        'terminees': terminees,
        'total': total,
    })


@login_required
def diligence_add_comment(request, pk):
    """Ajoute un commentaire libre sur une diligence (sans changer le statut)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    diligence = get_object_or_404(Diligence, pk=pk)
    if not _can_manage_reunion(request.user, diligence.reunion):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Données invalides'}, status=400)

    contenu = data.get('commentaire', '').strip()
    if not contenu:
        return JsonResponse({'success': False, 'error': 'Le commentaire est vide'}, status=400)

    comment = DiligenceComment.objects.create(
        diligence=diligence,
        auteur=request.user,
        contenu=contenu,
    )

    auteur_display = (
        f"{comment.auteur.first_name} {comment.auteur.last_name}".strip()
        if comment.auteur else "Inconnu"
    )

    return JsonResponse({
        'success': True,
        'commentaire': {
            'auteur': auteur_display,
            'contenu': contenu,
            'date': comment.created_at.strftime('%d/%m/%Y %H:%M'),
        }
    })


# ─── Tableau de bord personnel "Mes Diligences" ───────────────────────────────

@login_required
def mes_diligences(request):
    """Toutes les diligences assignées à l'utilisateur connecté, toutes réunions confondues."""
    from django.utils import timezone

    qs = Diligence.objects.filter(
        responsable_interne=request.user
    ).select_related('reunion', 'created_by').prefetch_related('commentaires')

    # Filtres
    status_filtre = request.GET.get('status', '')
    if status_filtre:
        qs = qs.filter(status=status_filtre)

    today = timezone.now().date()

    # Statistiques résumé
    total          = Diligence.objects.filter(responsable_interne=request.user).count()
    en_retard      = Diligence.objects.filter(
        responsable_interne=request.user,
        echeance__lt=today,
        status__in=['open', 'in_progress'],
    ).count()
    en_cours       = Diligence.objects.filter(responsable_interne=request.user, status='in_progress').count()
    terminees      = Diligence.objects.filter(responsable_interne=request.user, status='completed').count()
    a_faire        = Diligence.objects.filter(responsable_interne=request.user, status='open').count()

    # Tri : urgentes et en retard en premier
    diligences = qs.order_by(
        'status',          # open < in_progress avant completed/cancelled
        'echeance',
        '-priorite',
    )

    return render(request, 'reunions/mes_diligences.html', {
        'diligences': diligences,
        'status_filtre': status_filtre,
        'status_choices': Diligence.STATUS,
        'today': today,
        'stats': {
            'total': total,
            'en_retard': en_retard,
            'en_cours': en_cours,
            'terminees': terminees,
            'a_faire': a_faire,
        },
    })


# ─── Taux de réalisation des diligences par direction ─────────────────────────

@login_required
def stats_diligences_directions(request):
    """Statistiques de réalisation des diligences groupées par direction/service."""
    if request.user.role not in ['admin', 'secretary']:
        messages.error(request, "Accès non autorisé.")
        return redirect('dashboard')

    from django.utils import timezone
    from django.db.models import Case, When, IntegerField, FloatField

    today = timezone.now().date()

    # Filtres
    date_debut = request.GET.get('date_debut', '')
    date_fin   = request.GET.get('date_fin', '')

    qs = Diligence.objects.filter(
        responsable_interne__isnull=False
    ).select_related('responsable_interne')

    if date_debut:
        qs = qs.filter(created_at__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(created_at__date__lte=date_fin)

    # Grouper par direction
    from django.db.models import Count, Q as DQ
    stats_raw = (
        qs.values('responsable_interne__direction')
        .annotate(
            total=Count('id'),
            terminees=Count('id', filter=DQ(status='completed')),
            en_cours=Count('id', filter=DQ(status='in_progress')),
            a_faire=Count('id', filter=DQ(status='open')),
            en_retard=Count('id', filter=DQ(
                status__in=['open', 'in_progress'],
                echeance__lt=today,
            )),
        )
        .order_by('-total')
    )

    # Calcul du taux de réalisation
    stats = []
    for s in stats_raw:
        direction = s['responsable_interne__direction'] or '(Direction non renseignée)'
        taux = round(s['terminees'] / s['total'] * 100) if s['total'] else 0
        stats.append({
            'direction': direction,
            'total': s['total'],
            'terminees': s['terminees'],
            'en_cours': s['en_cours'],
            'a_faire': s['a_faire'],
            'en_retard': s['en_retard'],
            'taux': taux,
        })

    # Données pour Chart.js
    chart_labels = [s['direction'] for s in stats[:12]]
    chart_terminees = [s['terminees'] for s in stats[:12]]
    chart_en_cours  = [s['en_cours']  for s in stats[:12]]
    chart_a_faire   = [s['a_faire']   for s in stats[:12]]

    return render(request, 'reunions/stats_diligences_directions.html', {
        'stats': stats,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'chart_labels_json':    json.dumps(chart_labels),
        'chart_terminees_json': json.dumps(chart_terminees),
        'chart_en_cours_json':  json.dumps(chart_en_cours),
        'chart_a_faire_json':   json.dumps(chart_a_faire),
    })


@login_required
def export_diligences_view(request, reunion_id):
    """Export des diligences d'une réunion en PDF ou Excel."""
    reunion = get_object_or_404(Reunion, pk=reunion_id)

    # Vérification des permissions
    is_authorized = (
        request.user.role in ['admin', 'secretary']
        or reunion.organisateur == request.user
        or reunion.secretaire == request.user
    )
    if not is_authorized:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('reunion_detail', pk=reunion_id)

    format_type = request.GET.get('format', 'pdf')
    if format_type not in ('pdf', 'excel'):
        format_type = 'pdf'

    from .utils import export_diligences
    return export_diligences(reunion, format_type)