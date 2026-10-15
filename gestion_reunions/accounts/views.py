# accounts/views.py
import hmac
import logging
import secrets

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from django.core.exceptions import ValidationError

from reunions.forms import CustomUserCreationForm, validate_account_email
from reunions.models import CustomUser

logger = logging.getLogger(__name__)


# ── Helpers OTP ───────────────────────────────────────────────────────────────

def _generate_otp():
    # secrets (CSPRNG) et non random : un OTP ne doit pas être prédictible
    return f"{secrets.randbelow(900000) + 100000}"


def _mask_email(email):
    """Masque partiellement l'email : ab***@artci.ci"""
    try:
        local, domain = email.split('@')
        visible = local[:2] if len(local) >= 2 else local[0]
        return f"{visible}***@{domain}"
    except Exception:
        return "***"


def _send_otp_email(user, otp_code):
    from django.conf import settings
    expiry_min = getattr(settings, 'OTP_EXPIRY_SECONDS', 600) // 60

    subject = "Code de vérification QR Meeting"

    text_body = f"""
Bonjour {user.first_name or user.username},

Votre code de vérification à usage unique est :

    {otp_code}

Ce code est valable {expiry_min} minutes.

Si vous n'êtes pas à l'origine de cette connexion, ignorez ce message et
changez votre mot de passe immédiatement.

— QR Meeting ARTCI
"""

    try:
        html_body = render_to_string('registration/otp_email.html', {
            'user': user,
            'otp_code': otp_code,
            'expiry_min': expiry_min,
        })
    except Exception:
        html_body = None

    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    if html_body:
        email_msg.attach_alternative(html_body, 'text/html')
    email_msg.send()


# ── Étape 1 : Identifiants ────────────────────────────────────────────────────

def login_view(request):
    """Vérifie identifiants puis envoie un OTP par email (étape 1 du 2FA)."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
            return render(request, 'registration/login.html', {'username': username})

        if not user.is_active:
            messages.error(request, "Ce compte est désactivé. Contactez l'administrateur.")
            return render(request, 'registration/login.html', {})

        if not user.email:
            messages.error(request, "Aucun email associé à ce compte. Contactez l'administrateur.")
            return render(request, 'registration/login.html', {})

        # Générer et stocker l'OTP en cache Redis
        from django.conf import settings
        otp_code = _generate_otp()
        cache.set(f'otp_{user.pk}', {'code': otp_code, 'attempts': 0},
                  timeout=getattr(settings, 'OTP_EXPIRY_SECONDS', 600))

        # Stocker l'ID utilisateur en session (pas encore authentifié)
        request.session['otp_user_id'] = user.pk
        request.session['otp_email_masked'] = _mask_email(user.email)

        try:
            _send_otp_email(user, otp_code)
            messages.success(request,
                f"Un code de vérification a été envoyé à {_mask_email(user.email)}.")
        except Exception:
            logger.exception("Échec d'envoi de l'OTP à l'utilisateur %s", user.pk)
            messages.error(request, "Impossible d'envoyer le code de vérification. Réessayez plus tard.")
            cache.delete(f'otp_{user.pk}')
            return render(request, 'registration/login.html', {})

        return redirect('otp_verify')

    return render(request, 'registration/login.html', {})


# ── Étape 2 : Vérification OTP ────────────────────────────────────────────────

def otp_verify_view(request):
    """Vérifie le code OTP (étape 2 du 2FA) et connecte l'utilisateur."""
    user_id = request.session.get('otp_user_id')
    if not user_id:
        return redirect('login')

    email_masked = request.session.get('otp_email_masked', '***')

    if request.method == 'POST':
        from django.conf import settings
        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        entered = request.POST.get('otp_code', '').strip()
        cache_key = f'otp_{user_id}'
        otp_data = cache.get(cache_key)

        if not otp_data:
            messages.error(request, "Le code a expiré. Veuillez vous reconnecter.")
            _clear_otp_session(request)
            return redirect('login')

        if otp_data['attempts'] >= max_attempts:
            cache.delete(cache_key)
            _clear_otp_session(request)
            messages.error(request, "Trop de tentatives incorrectes. Veuillez vous reconnecter.")
            return redirect('login')

        # Comparaison sécurisée (résistante aux timing attacks)
        if hmac.compare_digest(entered, otp_data['code']):
            cache.delete(cache_key)
            _clear_otp_session(request)

            try:
                user = CustomUser.objects.get(pk=user_id)
            except CustomUser.DoesNotExist:
                messages.error(request, "Erreur interne. Veuillez réessayer.")
                return redirect('login')

            # Plusieurs backends (axes) : préciser celui qui a validé l'identité
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            next_url = request.GET.get('next')
            if not next_url or not url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()},
                    require_https=request.is_secure()):
                next_url = 'dashboard'
            return redirect(next_url)

        # Code incorrect
        otp_data['attempts'] += 1
        cache.set(cache_key, otp_data,
                  timeout=getattr(settings, 'OTP_EXPIRY_SECONDS', 600))
        remaining = max_attempts - otp_data['attempts']
        messages.error(request,
            f"Code incorrect. {remaining} tentative(s) restante(s).")

    return render(request, 'registration/otp_verify.html', {
        'email_masked': email_masked,
    })


def otp_resend_view(request):
    """Renvoie un nouveau code OTP."""
    user_id = request.session.get('otp_user_id')
    if not user_id:
        return redirect('login')

    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return redirect('login')

    from django.conf import settings

    # Un renvoi par minute au plus (P7.4 / R3) : sinon chaque renvoi remet le
    # compteur de tentatives à zéro et permet de deviner le code.
    cooldown_key = f'otp_resend_{user.pk}'
    if not cache.add(cooldown_key, True, timeout=getattr(settings, 'OTP_RESEND_COOLDOWN', 60)):
        messages.error(request, "Veuillez patienter une minute avant de demander un nouveau code.")
        return redirect('otp_verify')

    otp_code = _generate_otp()
    cache.set(f'otp_{user.pk}', {'code': otp_code, 'attempts': 0},
              timeout=getattr(settings, 'OTP_EXPIRY_SECONDS', 600))

    try:
        _send_otp_email(user, otp_code)
        messages.success(request, "Un nouveau code a été envoyé.")
    except Exception:
        logger.exception("Échec du renvoi de l'OTP à l'utilisateur %s", user.pk)
        messages.error(request, "Erreur lors de l'envoi du code. Réessayez plus tard.")

    return redirect('otp_verify')


def _clear_otp_session(request):
    request.session.pop('otp_user_id', None)
    request.session.pop('otp_email_masked', None)

@login_required
def password_change_required(request):
    """
    Changement de mot de passe obligatoire à la première connexion.
    Appelé automatiquement par ForcePasswordChangeMiddleware.
    """
    if not request.user.must_change_password:
        return redirect('dashboard')

    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=['must_change_password'])
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été mis à jour avec succès.")
            return redirect('dashboard')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'accounts/password_change_required.html', {'form': form})


@login_required
def logout_view(request):
    """
    Vue de déconnexion simple
    """
    logout(request)
    return render(request, 'registration/logged_out.html')


@login_required
def profile(request):
    """Profil utilisateur"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.save()
        
        messages.success(request, 'Profil mis à jour avec succès!')
        return redirect('profile')
    
    return render(request, 'accounts/profile.html', {'user': request.user})

@login_required
def user_list(request):
    """Liste des utilisateurs (admin seulement)"""
    if request.user.role != 'admin':
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    # Recherche
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    
    users = CustomUser.objects.all().order_by('-date_joined')
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Pagination
    paginator = Paginator(users, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Comptages par rôle
    total_users = CustomUser.objects.count()
    total_admins = CustomUser.objects.filter(role='admin').count()
    total_secretaires = CustomUser.objects.filter(role='secretary').count()
    total_participants = CustomUser.objects.filter(role='participant').count()

    context = {
        'users': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'roles': CustomUser.ROLES,
        'total_users': total_users,
        'total_admins': total_admins,
        'total_secretaires': total_secretaires,
        'total_participants': total_participants,
    }

    """
    
    context = {
        'users': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'roles': CustomUser.ROLES,
        'total_users': CustomUser.objects.count(),
    }
    """
    
    return render(request, 'accounts/user_list.html', context)

@login_required
def user_create(request):
    """Création d'un utilisateur (admin seulement)"""
    if request.user.role != 'admin':
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.must_change_password = True
            user.save()
            form.save_m2m()
            messages.success(request, f'Utilisateur {user.username} créé avec succès. Il devra changer son mot de passe à la première connexion.')
            return redirect('user_list')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Créer un Utilisateur',
        'submit_text': 'Créer'
    })

@login_required
def user_update(request, pk):
    """Modification d'un utilisateur (admin seulement)"""
    if request.user.role != 'admin':
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    user = get_object_or_404(CustomUser, pk=pk)
    
    if request.method == 'POST':
        # Mise à jour manuelle des champs (sans mot de passe)
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)
        user.role = request.POST.get('role', user.role)
        user.is_active = request.POST.get('is_active') == 'on'
        
        # Validation
        email_error = None
        if user.email:
            try:
                validate_account_email(user.email)
            except ValidationError as exc:
                email_error = exc.messages[0]

        if not user.first_name or not user.last_name or not user.email:
            messages.error(request, 'Les champs nom, prénom et email sont obligatoires.')
        elif email_error:
            messages.error(request, email_error)
        else:
            user.save()
            messages.success(request, f'Utilisateur {user.username} mis à jour avec succès!')
            return redirect('user_list')
    
    return render(request, 'accounts/user_form.html', {
        'form_user': user,
        'title': 'Modifier l\'Utilisateur',
        'submit_text': 'Mettre à Jour'
    })

@login_required
def user_delete(request, pk):
    """Suppression d'un utilisateur (admin seulement)"""
    if request.user.role != 'admin':
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    user = get_object_or_404(CustomUser, pk=pk)
    
    # Empêcher la suppression de son propre compte
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('user_list')
    
    if request.method == 'POST':
        username = user.username
        # Vérifier s'il a des réunions associées
        reunions_count = user.reunions_organisees.count()
        if reunions_count > 0:
            messages.error(request, f'Impossible de supprimer cet utilisateur. Il a {reunions_count} réunion(s) associée(s).')
            return redirect('user_list')
        
        user.delete()
        messages.success(request, f'Utilisateur {username} supprimé avec succès!')
        return redirect('user_list')
    
    return render(request, 'accounts/user_confirm_delete.html', {'form_user': user})

@login_required
def user_detail(request, pk):
    """Détail d'un utilisateur"""
    if request.user.role != 'admin' and request.user.pk != pk:
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard')
    
    user = get_object_or_404(CustomUser, pk=pk)
    
    context = {
        'form_user': user,
        'reunions_organisees': user.reunions_organisees.all()[:5],
        'reunions_secretaire': user.reunion_set.all()[:5] if hasattr(user, 'reunion_set') else [],
    }
    
    return render(request, 'accounts/user_detail.html', context)