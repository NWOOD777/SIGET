"""
Rutas URL para la API REST de Asignaciones y Devoluciones.
Contratos oficiales según Anexo B de Arquitectura: /api/asignaciones/*
"""
from django.urls import path

from asignaciones.views import (
    AsignacionDetailView,
    AsignacionDevolucionView,
    AsignacionListCreateView,
    EstadoAsignacionListView,
)

urlpatterns = [
    path("", AsignacionListCreateView.as_view(), name="asignacion-list-create"),
    path("<int:pk>/", AsignacionDetailView.as_view(), name="asignacion-detail"),
    path("<int:pk>/devolucion/", AsignacionDevolucionView.as_view(), name="asignacion-devolucion"),
    path("estados/", EstadoAsignacionListView.as_view(), name="asignacion-estados"),
]
