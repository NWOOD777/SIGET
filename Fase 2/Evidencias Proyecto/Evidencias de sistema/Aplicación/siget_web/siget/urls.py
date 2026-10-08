"""
URL configuration for siget project.
"""
from django.contrib import admin
from django.urls import include, path
from usuarios.views import inicio

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("usuarios.urls")),
    path("api/usuarios/", include("usuarios.api_urls")),
    path("api/activos/", include("activos.urls")),
    path("", inicio, name="inicio"),
]
