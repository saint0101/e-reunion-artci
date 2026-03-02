# accounts/views.py (version complète)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from reunions.models import CustomUser
from reunions.forms import CustomUserCreationForm

from django.contrib.auth import logout

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


def register(request):
    """Inscription d'un nouvel utilisateur"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Compte créé avec succès! Bienvenue {user.first_name}')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/register.html', {'form': form})

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
        if not user.first_name or not user.last_name or not user.email:
            messages.error(request, 'Les champs nom, prénom et email sont obligatoires.')
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