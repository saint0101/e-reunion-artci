# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    #path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),


    # User Management
    path('profile/', views.profile, name='profile'),
    path('users/', views.user_list, name='user_list'),
    path('user/<int:pk>/', views.user_detail, name='user_detail'),  # CORRIGÉ: URL différente de user_list
    path('user/create/', views.user_create, name='user_create'),
    path('user/<int:pk>/edit/', views.user_update, name='user_update'),
    path('user/<int:pk>/delete/', views.user_delete, name='user_delete'),

]