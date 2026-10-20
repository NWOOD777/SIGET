"""
URL configuration for siget project.
"""
from django.contrib import admin
from django.urls import include, path

from usuarios.views import inicio

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("usuarios.urls")),
    path("solicitudes/", include("asignaciones.web_urls")),
    path("tickets/", include("tickets.web_urls")),
    path("api/usuarios/", include("usuarios.api_urls")),
    path("api/activos/", include("activos.urls")),
    path("api/solicitudes-asignacion/", include("asignaciones.urls_solicitudes")),
    path("api/asignaciones/", include("asignaciones.urls")),
    path("api/tickets/", include("tickets.urls")),
    path("", inicio, name="inicio"),
]
