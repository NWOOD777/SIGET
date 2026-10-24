"""
Rutas URL para la API REST de auditoría interna.
Consumidas por la aplicación de escritorio PySide6 para consulta histórica protegida.
"""

from django.urls import path

from . import auditoria_views

app_name = "auditoria_api"

urlpatterns = [
    path("opciones/", auditoria_views.AuditoriaOpcionesAPIView.as_view(), name="auditoria_opciones"),
    path("", auditoria_views.AuditoriaListAPIView.as_view(), name="auditoria_list"),
    path("<int:pk>/", auditoria_views.AuditoriaDetailAPIView.as_view(), name="auditoria_detail"),
]
