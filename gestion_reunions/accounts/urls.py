# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication (2FA)
    path('login/', views.login_view, name='login'),
    path('otp/verify/', views.otp_verify_view, name='otp_verify'),
    path('otp/resend/', views.otp_resend_view, name='otp_resend'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),

    # Changement de mot de passe obligatoire (1ère connexion)
    path('password-change-required/', views.password_change_required, name='password_change_required'),

    # Mot de passe oublié — vues Django intégrées
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.txt',
             subject_template_name='registration/password_reset_subject.txt',
             success_url='/accounts/password-reset/done/',
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/accounts/password-reset/complete/',
         ),
         name='password_reset_confirm'),
    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),

    # Sauvegardes (admin)
    path('backups/', views.backup_list_view, name='backup_list'),
    path('backups/create/', views.backup_create_view, name='backup_create_view'),
    path('backups/download/<str:filename>/', views.backup_download, name='backup_download'),
    path('backups/delete/<str:filename>/', views.backup_delete, name='backup_delete'),

    # User Management
    path('profile/', views.profile, name='profile'),
    path('users/', views.user_list, name='user_list'),
    path('user/<int:pk>/', views.user_detail, name='user_detail'),
    path('user/create/', views.user_create, name='user_create'),
    path('user/<int:pk>/edit/', views.user_update, name='user_update'),
    path('user/<int:pk>/delete/', views.user_delete, name='user_delete'),
]