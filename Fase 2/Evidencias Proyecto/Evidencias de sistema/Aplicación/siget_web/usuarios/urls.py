from django.urls import path

from usuarios import portal, views

app_name = "usuarios"

urlpatterns = [
    path("mis-equipos/", portal.mis_equipos, name="mis_equipos"),
    path("mis-equipos/<int:pk>/", portal.detalle_equipo, name="detalle_equipo"),
    path("perfil/", portal.perfil, name="perfil"),
    # Autenticación y recuperación
    path("auth/login/", views.auth_login, name="auth_login"),
    path("auth/callback/", views.auth_callback, name="auth_callback"),
    path("auth/logout/", views.auth_logout, name="auth_logout"),
    path("auth/recover/", views.auth_recover, name="auth_recover"),
]

