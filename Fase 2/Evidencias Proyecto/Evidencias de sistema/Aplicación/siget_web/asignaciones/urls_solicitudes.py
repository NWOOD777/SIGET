"""
Rutas URL para la API REST de Solicitudes de Asignación.
Contratos oficiales según Anexo B de Arquitectura: /api/solicitudes-asignacion/*
"""
from django.urls import path

from asignaciones.views import (
    EstadoSolicitudListView,
    SolicitudAsignacionAprobarView,
    SolicitudAsignacionDetailView,
    SolicitudAsignacionEntregarView,
    SolicitudAsignacionListCreateView,
    SolicitudAsignacionRechazarView,
)

urlpatterns = [
    path("", SolicitudAsignacionListCreateView.as_view(), name="solicitud-list-create"),
    path("<int:pk>/", SolicitudAsignacionDetailView.as_view(), name="solicitud-detail"),
    path("<int:pk>/aprobar/", SolicitudAsignacionAprobarView.as_view(), name="solicitud-aprobar"),
    path("<int:pk>/rechazar/", SolicitudAsignacionRechazarView.as_view(), name="solicitud-rechazar"),
    path("<int:pk>/entregar/", SolicitudAsignacionEntregarView.as_view(), name="solicitud-entregar"),
    path("estados/", EstadoSolicitudListView.as_view(), name="solicitud-estados"),
]
