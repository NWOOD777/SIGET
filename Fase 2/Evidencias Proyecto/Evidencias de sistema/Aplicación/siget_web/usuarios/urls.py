from django.urls import path

from notificaciones import web_views as notificaciones_views
from usuarios import portal, views

app_name = "usuarios"

urlpatterns = [
    path("mis-equipos/", portal.mis_equipos, name="mis_equipos"),
    path("mis-equipos/<int:pk>/", portal.detalle_equipo, name="detalle_equipo"),
    path("notificaciones/", notificaciones_views.bandeja_notificaciones, name="notificaciones"),
    path("notificaciones/<int:pk>/", notificaciones_views.detalle_notificacion, name="detalle_notificacion"),
    path("notificaciones/<int:pk>/leer/", notificaciones_views.marcar_notificacion_leida, name="marcar_notificacion_leida"),
    path("notificaciones/<int:pk>/abrir/", notificaciones_views.abrir_notificacion, name="abrir_notificacion"),
    path("perfil/", portal.perfil, name="perfil"),
    # Autenticación y recuperación
    path("auth/login/", views.auth_login, name="auth_login"),
    path("auth/callback/", views.auth_callback, name="auth_callback"),
    path("auth/logout/", views.auth_logout, name="auth_logout"),
    path("auth/recover/", views.auth_recover, name="auth_recover"),
]

