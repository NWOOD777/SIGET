from django.urls import path
from usuarios import views

app_name = "usuarios"

urlpatterns = [
    # Autenticación y recuperación
    path("auth/login/", views.auth_login, name="auth_login"),
    path("auth/callback/", views.auth_callback, name="auth_callback"),
    path("auth/logout/", views.auth_logout, name="auth_logout"),
    path("auth/recover/", views.auth_recover, name="auth_recover"),
]

